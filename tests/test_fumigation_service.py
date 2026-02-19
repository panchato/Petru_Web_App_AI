import os
import unittest
from datetime import date, time
from pathlib import Path

TEST_DB_PATH = Path(__file__).resolve().parent / "test_fumigation_service.sqlite3"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"
os.environ["SECRET_KEY"] = "test-secret-key"

from app import app, db
from app.models import Fumigation, Lot, RawMaterialPackaging, RawMaterialReception, Variety
from app.services.fumigation_service import FumigationService, FumigationTransitionError


class FumigationServiceTests(unittest.TestCase):
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
            self.lot_ids = self._create_lots()
            db.session.commit()

    def _create_reference_data(self):
        variety = Variety(name="SERR", is_active=True)
        packaging = RawMaterialPackaging(name="Bins QA", tare=1.0, is_active=True)
        db.session.add_all([variety, packaging])
        db.session.flush()
        return variety.id, packaging.id

    def _create_reception(self):
        reception = RawMaterialReception(
            waybill=1000,
            date=date.today(),
            time=time(9, 0),
            truck_plate="AA1111",
            trucker_name="Chofer",
            observations="",
            is_open=False,
        )
        db.session.add(reception)
        db.session.flush()
        return reception.id

    def _create_lots(self):
        lot_1 = Lot(
            lot_number=1,
            packagings_quantity=10,
            net_weight=0,
            has_qc=False,
            fumigation_status="1",
            on_warehouse=True,
            rawmaterialreception_id=self.reception_id,
            variety_id=self.variety_id,
            rawmaterialpackaging_id=self.packaging_id,
        )
        lot_2 = Lot(
            lot_number=2,
            packagings_quantity=10,
            net_weight=0,
            has_qc=False,
            fumigation_status="1",
            on_warehouse=True,
            rawmaterialreception_id=self.reception_id,
            variety_id=self.variety_id,
            rawmaterialpackaging_id=self.packaging_id,
        )
        db.session.add_all([lot_1, lot_2])
        db.session.flush()
        return [lot_1.id, lot_2.id]

    def test_assign_start_complete_fumigation_transitions(self):
        with app.app_context():
            fumigation = FumigationService.assign_fumigation("OT-100", self.lot_ids)
            self.assertIsNotNone(fumigation.id)

            lots = Lot.query.filter(Lot.id.in_(self.lot_ids)).all()
            self.assertTrue(all(lot.fumigation_status == "2" for lot in lots))

            FumigationService.start_fumigation(
                fumigation=fumigation,
                real_start_date=date.today(),
                real_start_time=time(10, 0),
            )
            lots = Lot.query.filter(Lot.id.in_(self.lot_ids)).all()
            self.assertTrue(all(lot.fumigation_status == "3" for lot in lots))

            FumigationService.complete_fumigation(
                fumigation=fumigation,
                real_end_date=date.today(),
                real_end_time=time(12, 0),
            )
            lots = Lot.query.filter(Lot.id.in_(self.lot_ids)).all()
            self.assertTrue(all(lot.fumigation_status == "4" for lot in lots))

    def test_reject_skip_transition_from_assigned_to_completed(self):
        with app.app_context():
            fumigation = FumigationService.assign_fumigation("OT-200", self.lot_ids)
            with self.assertRaises(FumigationTransitionError):
                FumigationService.complete_fumigation(
                    fumigation=fumigation,
                    real_end_date=date.today(),
                    real_end_time=time(12, 0),
                )

    def test_reject_assign_when_lot_not_available(self):
        with app.app_context():
            lot = Lot.query.get(self.lot_ids[0])
            lot.fumigation_status = "3"
            db.session.add(lot)
            db.session.commit()

            with self.assertRaises(FumigationTransitionError):
                FumigationService.assign_fumigation("OT-300", self.lot_ids)

            self.assertEqual(Fumigation.query.filter_by(work_order="OT-300").count(), 0)


if __name__ == "__main__":
    unittest.main()
