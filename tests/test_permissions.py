import os
import unittest
from pathlib import Path

TEST_DB_PATH = Path(__file__).resolve().parent / "test_permissions.sqlite3"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"
os.environ["SECRET_KEY"] = "test-secret-key"

from app import app, db
from app.permissions import (
    can_access_lot_lists,
    can_execute_operational_actions,
    can_view_operational_dashboard,
    has_area_role,
    is_admin,
)


class DummyUser:
    def __init__(
        self,
        authenticated=True,
        active=True,
        external=False,
        roles=None,
        areas=None,
    ):
        self.is_authenticated = authenticated
        self.is_active = active
        self.is_external = external
        self._roles = set(roles or [])
        self._areas = set(areas or [])

    def has_role(self, role_name):
        return role_name in self._roles

    def from_area(self, area_name):
        return area_name in self._areas


class PermissionTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        with app.app_context():
            db.session.remove()
            db.engine.dispose()
        if TEST_DB_PATH.exists():
            TEST_DB_PATH.unlink()

    def test_is_admin(self):
        user = DummyUser(roles=["Admin"])
        self.assertTrue(is_admin(user))
        self.assertFalse(is_admin(DummyUser(roles=["Contribuidor"])))

    def test_has_area_role(self):
        user = DummyUser(roles=["Contribuidor"], areas=["Materia Prima"])
        self.assertTrue(has_area_role(user, "Materia Prima", ["Contribuidor", "Lector"]))
        self.assertFalse(has_area_role(user, "Calidad", ["Contribuidor"]))

    def test_operational_dashboard_permissions(self):
        admin = DummyUser(roles=["Admin"])
        viewer = DummyUser(roles=["Dashboard"])
        blocked_external = DummyUser(roles=["Admin"], external=True)
        blocked_inactive = DummyUser(roles=["Admin"], active=False)
        self.assertTrue(can_view_operational_dashboard(admin))
        self.assertTrue(can_view_operational_dashboard(viewer))
        self.assertFalse(can_view_operational_dashboard(blocked_external))
        self.assertFalse(can_view_operational_dashboard(blocked_inactive))

    def test_lot_and_action_permissions(self):
        reader = DummyUser(roles=["Lector"], areas=["Materia Prima"])
        contributor = DummyUser(roles=["Contribuidor"], areas=["Materia Prima"])
        self.assertTrue(can_access_lot_lists(reader))
        self.assertTrue(can_access_lot_lists(contributor))
        self.assertFalse(can_execute_operational_actions(reader))
        self.assertTrue(can_execute_operational_actions(contributor))


if __name__ == "__main__":
    unittest.main()
