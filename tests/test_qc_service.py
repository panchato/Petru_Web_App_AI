import os
import unittest
from datetime import date, time
from pathlib import Path

TEST_DB_PATH = Path(__file__).resolve().parent / "test_qc_service.sqlite3"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"
os.environ["SECRET_KEY"] = "test-secret-key"

from app import app, db
from app.models import Lot, RawMaterialPackaging, RawMaterialReception, Variety
from app.services.qc_service import QCService, QCValidationError


def _base_qc_payload():
    return {
        "analyst": "Ana",
        "date": date.today(),
        "time": time(8, 0),
        "inshell_weight": 100.0,
        "lessthan30": 20,
        "between3032": 20,
        "between3234": 20,
        "between3436": 20,
        "morethan36": 20,
        "broken_walnut": 0,
        "split_walnut": 0,
        "light_stain": 0,
        "serious_stain": 0,
        "adhered_hull": 0,
        "shrivel": 0,
        "empty": 0,
        "insect_damage": 0,
        "inactive_fungus": 0,
        "active_fungus": 0,
        "extra_light": 10.0,
        "light": 15.0,
        "light_amber": 12.0,
        "amber": 13.0,
        "yellow": 0.0,
    }


class QCServiceTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        with app.app_context():
            db.session.remove()
            db.engine.dispose()
        if TEST_DB_PATH.exists():
            TEST_DB_PATH.unlink()

    def setUp(self):
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        with app.app_context():
            db.drop_all()
            db.create_all()
            self.variety_id, self.packaging_id = self._create_reference_data()
            self.reception_id = self._create_reception()
            self.lot_id = self._create_lot()
            db.session.commit()

    def _create_reference_data(self):
        variety = Variety(name="MIX", is_active=True)
        packaging = RawMaterialPackaging(name="Bins QC", tare=1.0, is_active=True)
        db.session.add_all([variety, packaging])
        db.session.flush()
        return variety.id, packaging.id

    def _create_reception(self):
        reception = RawMaterialReception(
            waybill=2000,
            date=date.today(),
            time=time(7, 0),
            truck_plate="BB2222",
            trucker_name="Chofer",
            observations="",
            is_open=False,
        )
        db.session.add(reception)
        db.session.flush()
        return reception.id

    def _create_lot(self):
        lot = Lot(
            lot_number=900,
            packagings_quantity=10,
            net_weight=0,
            has_qc=False,
            fumigation_status="1",
            on_warehouse=True,
            rawmaterialreception_id=self.reception_id,
            variety_id=self.variety_id,
            rawmaterialpackaging_id=self.packaging_id,
        )
        db.session.add(lot)
        db.session.flush()
        return lot.id

    def test_validate_payload_rejects_invalid_breakdown(self):
        payload = _base_qc_payload()
        payload["morethan36"] = 19

        with self.assertRaises(QCValidationError):
            QCService.validate_payload(payload)

    def test_validate_payload_calculates_yield_from_business_logic(self):
        payload = _base_qc_payload()
        metrics = QCService.validate_payload(payload)
        self.assertEqual(metrics["units"], 100)
        self.assertEqual(metrics["shelled_weight"], 50.0)
        self.assertEqual(metrics["yieldpercentage"], 50.0)

    def test_create_lot_qc_marks_lot_as_qc_completed(self):
        with app.app_context():
            payload = _base_qc_payload()
            payload["lot_id"] = self.lot_id
            QCService.create_lot_qc(
                payload=payload,
                inshell_image_path="images/test1.jpg",
                shelled_image_path="images/test2.jpg",
            )
            lot = Lot.query.get(self.lot_id)
            self.assertTrue(lot.has_qc)


if __name__ == "__main__":
    unittest.main()
