import os
import unittest
from pathlib import Path

from werkzeug.routing import BuildError

TEST_DB_PATH = Path(__file__).resolve().parent / "test_endpoint_resolution.sqlite3"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"
os.environ["SECRET_KEY"] = "test-secret-key"

from app import app, db  # noqa: E402
from flask import url_for  # noqa: E402


class EndpointResolutionTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        with app.app_context():
            db.session.remove()
            db.engine.dispose()
        if TEST_DB_PATH.exists():
            TEST_DB_PATH.unlink()

    def test_representative_endpoints_resolve_without_builder_errors(self):
        endpoints = [
            ("dashboard.index", {}),
            ("auth.login", {}),
            ("auth.logout", {}),
            ("dashboard.healthz", {}),
            ("dashboard.index_summary_api", {}),
            ("dashboard.dashboard_tv", {}),
            ("dashboard.dashboard_summary_api", {}),
            ("admin.add_user", {}),
            ("admin.list_users", {}),
            ("admin.edit_user", {"user_id": 1}),
            ("admin.toggle_user", {"user_id": 1}),
            ("admin.add_role", {}),
            ("admin.assign_role", {}),
            ("admin.list_roles", {}),
            ("admin.edit_role", {"role_id": 1}),
            ("admin.toggle_role", {"role_id": 1}),
            ("admin.add_area", {}),
            ("admin.assign_area", {}),
            ("admin.list_areas", {}),
            ("admin.edit_area", {"area_id": 1}),
            ("admin.toggle_area", {"area_id": 1}),
            ("admin.add_client", {}),
            ("admin.list_clients", {}),
            ("admin.edit_client", {"client_id": 1}),
            ("admin.toggle_client", {"client_id": 1}),
            ("admin.add_grower", {}),
            ("admin.list_growers", {}),
            ("admin.edit_grower", {"grower_id": 1}),
            ("admin.toggle_grower", {"grower_id": 1}),
            ("admin.add_variety", {}),
            ("admin.list_varieties", {}),
            ("admin.edit_variety", {"variety_id": 1}),
            ("admin.toggle_variety", {"variety_id": 1}),
            ("admin.add_raw_material_packaging", {}),
            ("admin.list_raw_material_packagings", {}),
            ("admin.edit_raw_material_packaging", {"rmp_id": 1}),
            ("admin.toggle_raw_material_packaging", {"rmp_id": 1}),
            ("materiaprima.create_raw_material_reception", {}),
            ("materiaprima.list_rmrs", {}),
            ("materiaprima.create_lot", {"reception_id": 1}),
            ("materiaprima.list_lots", {}),
            ("materiaprima.register_full_truck_weight", {"lot_id": 1}),
            ("materiaprima.update_lot_weight_inline", {"lot_id": 1}),
            ("materiaprima.generate_qr", {"reception_id": 1}),
            ("materiaprima.lot_labels_pdf", {"lot_id": 1}),
            ("qc.create_lot_qc", {}),
            ("qc.create_sample_qc", {}),
            ("qc.list_lot_qc_reports", {}),
            ("qc.list_sample_qc_reports", {}),
            ("qc.view_lot_qc_report", {"report_id": 1}),
            ("qc.view_lot_qc_report_image", {"report_id": 1, "image_kind": "inshell"}),
            ("qc.view_lot_qc_report_pdf", {"report_id": 1}),
            ("qc.view_sample_qc_report", {"report_id": 1}),
            ("qc.view_sample_qc_report_image", {"report_id": 1, "image_kind": "shelled"}),
            ("qc.view_sample_qc_report_pdf", {"report_id": 1}),
            ("fumigation.create_fumigation", {}),
            ("fumigation.list_fumigations", {}),
            ("fumigation.view_fumigation_document", {"fumigation_id": 1, "document_kind": "sign"}),
            ("fumigation.start_fumigation", {"fumigation_id": 1}),
            ("fumigation.complete_fumigation", {"fumigation_id": 1}),
            ("static", {"filename": "css/main.css"}),
        ]

        with app.test_request_context():
            for endpoint, kwargs in endpoints:
                with self.subTest(endpoint=endpoint):
                    try:
                        built = url_for(endpoint, **kwargs)
                    except BuildError as exc:
                        self.fail(f"Endpoint '{endpoint}' failed to resolve: {exc}")
                    self.assertTrue(isinstance(built, str) and built.startswith("/"))


if __name__ == "__main__":
    unittest.main()
