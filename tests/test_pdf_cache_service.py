import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

TEST_DB_PATH = Path(__file__).resolve().parent / "test_pdf_cache_service.sqlite3"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"
os.environ["SECRET_KEY"] = "test-secret-key"

from app.services.pdf_cache_service import (
    get_cached_pdf,
    invalidate_cached_pdf,
    save_pdf_to_cache,
)


class PDFCacheServiceTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        if TEST_DB_PATH.exists():
            TEST_DB_PATH.unlink()

    def setUp(self):
        self._original_pdf_cache_dir = os.environ.get("PDF_CACHE_DIR")
        self._temp_dir = tempfile.mkdtemp()
        os.environ["PDF_CACHE_DIR"] = self._temp_dir

    def tearDown(self):
        if self._original_pdf_cache_dir is None:
            os.environ.pop("PDF_CACHE_DIR", None)
        else:
            os.environ["PDF_CACHE_DIR"] = self._original_pdf_cache_dir
        shutil.rmtree(self._temp_dir, ignore_errors=True)

    def test_cache_miss_returns_none(self):
        updated_at = datetime(2026, 2, 19, 12, 0, 0, tzinfo=timezone.utc)
        cached_path = get_cached_pdf("lot_labels", 1001, updated_at)
        self.assertIsNone(cached_path)

    def test_save_then_get_returns_correct_bytes(self):
        updated_at = datetime(2026, 2, 19, 12, 0, 0, tzinfo=timezone.utc)
        pdf_bytes = b"%PDF-1.4 test payload"

        saved_path = save_pdf_to_cache("lot_labels", 1002, updated_at, pdf_bytes)
        cached_path = get_cached_pdf("lot_labels", 1002, updated_at)

        self.assertEqual(saved_path, cached_path)
        self.assertEqual(Path(cached_path).read_bytes(), pdf_bytes)

    def test_invalidate_removes_cached_file(self):
        updated_at = datetime(2026, 2, 19, 12, 0, 0, tzinfo=timezone.utc)
        pdf_bytes = b"%PDF-1.4 to be deleted"

        save_pdf_to_cache("lot_qc_report", 2001, updated_at, pdf_bytes)
        self.assertIsNotNone(get_cached_pdf("lot_qc_report", 2001, updated_at))

        invalidate_cached_pdf("lot_qc_report", 2001)
        self.assertIsNone(get_cached_pdf("lot_qc_report", 2001, updated_at))

    def test_different_updated_at_is_cache_miss(self):
        updated_at = datetime(2026, 2, 19, 12, 0, 0, tzinfo=timezone.utc)
        newer_updated_at = updated_at + timedelta(minutes=1)
        pdf_bytes = b"%PDF-1.4 stale check"

        save_pdf_to_cache("sample_qc_report", 3001, updated_at, pdf_bytes)

        self.assertIsNone(get_cached_pdf("sample_qc_report", 3001, newer_updated_at))
        self.assertIsNotNone(get_cached_pdf("sample_qc_report", 3001, updated_at))


if __name__ == "__main__":
    unittest.main()
