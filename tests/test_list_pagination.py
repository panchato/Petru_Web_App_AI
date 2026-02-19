import os
import unittest
from datetime import date, time
from pathlib import Path

TEST_DB_PATH = Path(__file__).resolve().parent / "test_list_pagination.sqlite3"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"
os.environ["SECRET_KEY"] = "test-secret-key"

from app import app, bcrypt, db
from app.models import (
    Client,
    Grower,
    Lot,
    RawMaterialPackaging,
    RawMaterialReception,
    Role,
    User,
    Variety,
)


class ListPaginationTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        with app.app_context():
            db.session.remove()
            db.engine.dispose()
        if TEST_DB_PATH.exists():
            TEST_DB_PATH.unlink()

    def setUp(self):
        app.config.update(
            TESTING=True,
            WTF_CSRF_ENABLED=False,
            DEFAULT_PAGE_SIZE=2,
            MAX_PAGE_SIZE=5,
        )
        self.client = app.test_client()

        with app.app_context():
            db.drop_all()
            db.create_all()
            self.user_id = self._create_admin_user()
            self.variety_id, self.packaging_id = self._create_reference_data()
            self._create_lot_data()
            db.session.commit()

    def _create_admin_user(self):
        admin_role = Role(name="Admin", description="Administrador", is_active=True)
        user = User(
            name="Admin",
            last_name="Perf",
            email="admin@perf.local",
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
        packaging = RawMaterialPackaging(name="Bins", tare=1.0, is_active=True)
        db.session.add_all([variety, packaging])
        db.session.flush()
        return variety.id, packaging.id

    def _create_lot_data(self):
        client_a = Client(name="Cliente A", tax_id="900000001", address="Dir A", comuna="Comuna A", is_active=True)
        client_b = Client(name="Cliente B", tax_id="900000002", address="Dir B", comuna="Comuna B", is_active=True)
        grower_a = Grower(name="Productor A", tax_id="910000001", csg_code="CSG001", is_active=True)
        grower_b = Grower(name="Productor B", tax_id="910000002", csg_code="CSG002", is_active=True)
        db.session.add_all([client_a, client_b, grower_a, grower_b])
        db.session.flush()

        reception_a = RawMaterialReception(
            waybill=1001,
            date=date(2026, 2, 19),
            time=time(8, 0),
            truck_plate="AA1111",
            trucker_name="Chofer A",
            observations="",
            is_open=False,
        )
        reception_a.clients.append(client_a)
        reception_a.growers.append(grower_a)

        reception_b = RawMaterialReception(
            waybill=1002,
            date=date(2026, 2, 19),
            time=time(9, 0),
            truck_plate="BB2222",
            trucker_name="Chofer B",
            observations="",
            is_open=False,
        )
        reception_b.clients.append(client_b)
        reception_b.growers.append(grower_b)
        db.session.add_all([reception_a, reception_b])
        db.session.flush()

        lots = [
            Lot(
                lot_number=1,
                packagings_quantity=10,
                net_weight=10.0,
                has_qc=False,
                fumigation_status="3",
                on_warehouse=True,
                rawmaterialreception_id=reception_a.id,
                variety_id=self.variety_id,
                rawmaterialpackaging_id=self.packaging_id,
            ),
            Lot(
                lot_number=2,
                packagings_quantity=10,
                net_weight=10.0,
                has_qc=False,
                fumigation_status="1",
                on_warehouse=True,
                rawmaterialreception_id=reception_a.id,
                variety_id=self.variety_id,
                rawmaterialpackaging_id=self.packaging_id,
            ),
            Lot(
                lot_number=3,
                packagings_quantity=10,
                net_weight=10.0,
                has_qc=False,
                fumigation_status="3",
                on_warehouse=True,
                rawmaterialreception_id=reception_b.id,
                variety_id=self.variety_id,
                rawmaterialpackaging_id=self.packaging_id,
            ),
        ]
        db.session.add_all(lots)

    def _login(self):
        with self.client.session_transaction() as session:
            session["_user_id"] = str(self.user_id)
            session["_fresh"] = True

    def test_admin_list_users_is_paginated(self):
        with app.app_context():
            admin_role = Role.query.filter_by(name="Admin").first()
            for idx in range(4):
                user = User(
                    name=f"User {idx}",
                    last_name="Test",
                    email=f"user{idx}@perf.local",
                    phone_number=f"99900000{idx}",
                    password_hash=bcrypt.generate_password_hash("secret").decode("utf-8"),
                    is_active=True,
                    is_external=False,
                )
                user.roles.append(admin_role)
                db.session.add(user)
            db.session.commit()

        self._login()
        response = self.client.get("/list_users")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Mostrando 1-2 de 5", html)

    def test_lots_list_preserves_filters_and_pagination(self):
        self._login()
        response = self.client.get("/list_lots?status=en_fumigacion&per_page=1")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("001", html)
        self.assertNotIn("002", html)
        self.assertIn("status=en_fumigacion", html)
        self.assertIn("per_page=1", html)


if __name__ == "__main__":
    unittest.main()
