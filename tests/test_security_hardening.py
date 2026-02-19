import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from werkzeug.datastructures import FileStorage

TEST_DB_PATH = Path(__file__).resolve().parent / "test_security_hardening.sqlite3"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"
os.environ["SECRET_KEY"] = "test-secret-key"

from app import app  # noqa: E402
from app.upload_security import UploadValidationError, resolve_upload_path, save_uploaded_file  # noqa: E402


class UploadSecurityTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        if TEST_DB_PATH.exists():
            TEST_DB_PATH.unlink()

    def setUp(self):
        self._temp_upload_dir = tempfile.TemporaryDirectory()
        self._original_config = {
            "UPLOAD_ROOT": app.config.get("UPLOAD_ROOT"),
            "UPLOAD_PATH_IMAGE": app.config.get("UPLOAD_PATH_IMAGE"),
            "UPLOAD_PATH_PDF": app.config.get("UPLOAD_PATH_PDF"),
            "MAX_UPLOAD_FILE_BYTES": app.config.get("MAX_UPLOAD_FILE_BYTES"),
            "VIRUS_SCAN_ENABLED": app.config.get("VIRUS_SCAN_ENABLED"),
            "WTF_CSRF_ENABLED": app.config.get("WTF_CSRF_ENABLED"),
            "TESTING": app.config.get("TESTING"),
        }

        upload_root = Path(self._temp_upload_dir.name)
        app.config.update(
            TESTING=True,
            WTF_CSRF_ENABLED=False,
            UPLOAD_ROOT=str(upload_root),
            UPLOAD_PATH_IMAGE=str(upload_root / "images"),
            UPLOAD_PATH_PDF=str(upload_root / "pdf"),
            MAX_UPLOAD_FILE_BYTES=1024,
            VIRUS_SCAN_ENABLED=False,
        )
        Path(app.config["UPLOAD_PATH_IMAGE"]).mkdir(parents=True, exist_ok=True)
        Path(app.config["UPLOAD_PATH_PDF"]).mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        app.config.update(self._original_config)
        self._temp_upload_dir.cleanup()

    def _file(self, filename, content):
        return FileStorage(
            stream=BytesIO(content),
            filename=filename,
            content_type="application/octet-stream",
        )

    def test_save_valid_pdf_and_resolve_private_path(self):
        with app.app_context():
            stored_path = save_uploaded_file(self._file("orden.pdf", b"%PDF-1.4\n1 0 obj\n"), "pdf")
            resolved = resolve_upload_path(stored_path)

        self.assertTrue(stored_path.startswith("pdf/"))
        self.assertIsNotNone(resolved)
        self.assertTrue(resolved.exists())
        self.assertIn(Path(app.config["UPLOAD_ROOT"]).resolve(), resolved.parents)

    def test_reject_mismatched_extension_and_content(self):
        with app.app_context():
            with self.assertRaises(UploadValidationError):
                save_uploaded_file(self._file("malicioso.pdf", b"\x89PNG\r\n\x1a\npayload"), "pdf")

    def test_reject_oversized_file(self):
        oversized_pdf = b"%PDF-1.7\n" + (b"A" * 5000)
        with app.app_context():
            with self.assertRaises(UploadValidationError):
                save_uploaded_file(self._file("grande.pdf", oversized_pdf), "pdf")

    def test_resolve_upload_path_blocks_traversal(self):
        with app.app_context():
            self.assertIsNone(resolve_upload_path("../secreto.txt"))
            self.assertIsNone(resolve_upload_path("images/../../secreto.txt"))


class SessionAndCsrfHardeningTests(unittest.TestCase):
    def test_csrf_is_registered_globally(self):
        self.assertIn("csrf", app.extensions)

    def test_session_cookie_flags_are_hardened(self):
        self.assertTrue(app.config["SESSION_COOKIE_HTTPONLY"])
        self.assertIn(app.config["SESSION_COOKIE_SAMESITE"], {"Lax", "Strict"})
        if not app.config.get("IS_DEVELOPMENT", False):
            self.assertTrue(app.config["SESSION_COOKIE_SECURE"])
            self.assertEqual(app.config["SESSION_COOKIE_SAMESITE"], "Strict")

    def test_post_without_csrf_token_is_rejected(self):
        original_testing = app.config.get("TESTING")
        original_csrf = app.config.get("WTF_CSRF_ENABLED")
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=True)
        try:
            with app.test_client() as client:
                response = client.post("/login", data={"email": "x", "password": "y"})
            self.assertEqual(response.status_code, 400)
        finally:
            app.config.update(TESTING=original_testing, WTF_CSRF_ENABLED=original_csrf)


if __name__ == "__main__":
    unittest.main()
