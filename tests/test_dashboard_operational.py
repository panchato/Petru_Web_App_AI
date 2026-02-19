import os
import unittest
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

TEST_DB_PATH = Path(__file__).resolve().parent / "test_dashboard_operational.sqlite3"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"
os.environ["SECRET_KEY"] = "test-secret-key"

from app import app, db, bcrypt, cache  # noqa: E402
from app.models import Lot, LotQC, RawMaterialPackaging, RawMaterialReception, Role, User, Variety  # noqa: E402


class DashboardOperationalTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        with app.app_context():
            db.session.remove()
            db.engine.dispose()
        if TEST_DB_PATH.exists():
            TEST_DB_PATH.unlink()

    def setUp(self):
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        self.client = app.test_client()
        self._lot_number = 1
        self._waybill = 1000

        with app.app_context():
            cache.clear()
            db.drop_all()
            db.create_all()
            self.user_id = self._create_admin_user()
            self.variety_id, self.packaging_id = self._create_reference_data()
            db.session.commit()

    def _create_admin_user(self):
        admin_role = Role(name="Admin", description="Administrador", is_active=True)
        user = User(
            name="Admin",
            last_name="Test",
            email="admin@test.local",
            phone_number="123456789",
            password_hash=bcrypt.generate_password_hash("secret").decode("utf-8"),
            is_active=True,
            is_external=False,
        )
        user.roles.append(admin_role)
        db.session.add_all([admin_role, user])
        db.session.flush()
        return user.id

    def _create_reference_data(self):
        variety = Variety(name="CHANDLER", is_active=True)
        packaging = RawMaterialPackaging(name="Bins Test", tare=1.0, is_active=True)
        db.session.add_all([variety, packaging])
        db.session.flush()
        return variety.id, packaging.id

    def _login(self):
        with self.client.session_transaction() as session:
            session["_user_id"] = str(self.user_id)
            session["_fresh"] = True

    def _create_reception(self, reception_date):
        self._waybill += 1
        reception = RawMaterialReception(
            waybill=self._waybill,
            date=reception_date,
            time=time(8, 0),
            truck_plate=f"T{self._waybill}"[:6],
            trucker_name="Chofer",
            observations="",
            is_open=False,
        )
        db.session.add(reception)
        db.session.flush()
        return reception

    def _create_lot(self, reception_id, created_at_utc_naive, status="1", net_weight=0.0, with_qc=False):
        lot = Lot(
            lot_number=self._lot_number,
            packagings_quantity=10,
            net_weight=net_weight,
            has_qc=with_qc,
            fumigation_status=status,
            on_warehouse=True,
            rawmaterialreception_id=reception_id,
            variety_id=self.variety_id,
            rawmaterialpackaging_id=self.packaging_id,
        )
        lot.created_at = created_at_utc_naive
        self._lot_number += 1
        db.session.add(lot)
        db.session.flush()
        if with_qc:
            self._add_qc(lot.id)
            lot.has_qc = True
        return lot

    def _add_qc(self, lot_id):
        db.session.add(
            LotQC(
                lot_id=lot_id,
                analyst="Analista",
                date=date.today(),
                time=time(10, 0),
                units=100,
                inshell_weight=100.0,
                shelled_weight=50.0,
                yieldpercentage=50.0,
                lessthan30=20,
                between3032=20,
                between3234=20,
                between3436=20,
                morethan36=20,
                broken_walnut=0,
                split_walnut=0,
                light_stain=0,
                serious_stain=0,
                adhered_hull=0,
                shrivel=0,
                empty=0,
                insect_damage=0,
                inactive_fungus=0,
                active_fungus=0,
                extra_light=10.0,
                light=10.0,
                light_amber=15.0,
                amber=15.0,
                yellow=0.0,
            )
        )

    @staticmethod
    def _to_utc_naive(local_dt):
        return local_dt.astimezone(timezone.utc).replace(tzinfo=None)

    def test_today_metrics_use_local_day(self):
        fixed_now_local = datetime(2026, 2, 19, 10, 0, tzinfo=timezone(timedelta(hours=-3)))
        with app.app_context():
            reception = self._create_reception(fixed_now_local.date())
            self._create_lot(
                reception.id,
                self._to_utc_naive(datetime(2026, 2, 19, 1, 0, tzinfo=fixed_now_local.tzinfo)),
                status="1",
                net_weight=100.0,
                with_qc=True,
            )
            self._create_lot(
                reception.id,
                self._to_utc_naive(datetime(2026, 2, 19, 8, 30, tzinfo=fixed_now_local.tzinfo)),
                status="3",
                net_weight=None,
                with_qc=True,
            )
            self._create_lot(
                reception.id,
                self._to_utc_naive(datetime(2026, 2, 18, 23, 30, tzinfo=fixed_now_local.tzinfo)),
                status="4",
                net_weight=88.0,
                with_qc=True,
            )
            db.session.commit()

        self._login()
        with patch("app.blueprints.dashboard.services._server_now_local", return_value=fixed_now_local):
            response = self.client.get("/api/dashboard/summary")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()

        self.assertEqual(payload["today"]["lots_received"], 2)
        self.assertEqual(payload["today"]["kilograms_received"], 100.0)

        status_map = {item["key"]: item["count"] for item in payload["fumigation_status"]}
        self.assertEqual(status_map["AVAILABLE"], 1)
        self.assertEqual(status_map["ASSIGNED"], 0)
        self.assertEqual(status_map["STARTED"], 1)
        self.assertEqual(status_map["COMPLETED"], 1)

    def test_alert_thresholds_are_strictly_greater_than(self):
        fixed_now_local = datetime(2026, 2, 19, 12, 0, tzinfo=timezone.utc)
        with app.app_context():
            reception = self._create_reception(fixed_now_local.date())

            self._create_lot(reception.id, self._to_utc_naive(fixed_now_local - timedelta(hours=24)), status="2", net_weight=30.0, with_qc=False)
            lot_no_qc = self._create_lot(reception.id, self._to_utc_naive(fixed_now_local - timedelta(hours=24, seconds=1)), status="2", net_weight=30.0, with_qc=False)

            self._create_lot(reception.id, self._to_utc_naive(fixed_now_local - timedelta(hours=12)), status="2", net_weight=0.0, with_qc=True)
            lot_no_weight = self._create_lot(reception.id, self._to_utc_naive(fixed_now_local - timedelta(hours=12, seconds=1)), status="2", net_weight=0.0, with_qc=True)

            self._create_lot(reception.id, self._to_utc_naive(fixed_now_local - timedelta(hours=48)), status="1", net_weight=30.0, with_qc=True)
            lot_no_fum = self._create_lot(reception.id, self._to_utc_naive(fixed_now_local - timedelta(hours=48, seconds=1)), status="1", net_weight=30.0, with_qc=True)
            db.session.commit()

            no_qc_number = f"{lot_no_qc.lot_number:03d}"
            no_weight_number = f"{lot_no_weight.lot_number:03d}"
            no_fum_number = f"{lot_no_fum.lot_number:03d}"

        self._login()
        with patch("app.blueprints.dashboard.services._server_now_local", return_value=fixed_now_local):
            response = self.client.get("/api/dashboard/summary")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        alerts = {item["key"]: item for item in payload["alerts"]}

        self.assertEqual(alerts["no_qc_over_24h"]["count"], 1)
        self.assertEqual(alerts["missing_net_weight_over_12h"]["count"], 1)
        self.assertEqual(alerts["no_fumigation_over_48h"]["count"], 1)
        self.assertIn("alert=no_qc_over_24h", alerts["no_qc_over_24h"]["link"])
        self.assertIn("alert=missing_net_weight_over_12h", alerts["missing_net_weight_over_12h"]["link"])
        self.assertIn("alert=no_fumigation_over_48h", alerts["no_fumigation_over_48h"]["link"])

        page = self.client.get(alerts["no_qc_over_24h"]["link"])
        self.assertEqual(page.status_code, 200)
        html = page.get_data(as_text=True)
        self.assertIn(no_qc_number, html)
        self.assertNotIn(no_weight_number, html)
        self.assertNotIn(no_fum_number, html)


if __name__ == "__main__":
    unittest.main()
