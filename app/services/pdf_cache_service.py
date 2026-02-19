import hashlib
import os
from pathlib import Path


def _cache_dir():
    return Path(os.environ.get("PDF_CACHE_DIR", "app/static/pdf_cache"))


def _sanitize(value):
    raw = str(value or "")
    cleaned = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in raw).strip("_")
    if len(cleaned) > 80:
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
    return cleaned or "unknown"


def _updated_at_token(updated_at):
    if updated_at is None:
        return "none"
    raw = updated_at.isoformat() if hasattr(updated_at, "isoformat") else str(updated_at)
    # Keep token deterministic and filename-safe while still reflecting updated_at value.
    return _sanitize(raw)


def _cache_file_path(entity_type, entity_id, updated_at):
    safe_entity_type = _sanitize(entity_type)
    safe_entity_id = _sanitize(entity_id)
    updated_at_timestamp = _updated_at_token(updated_at)
    filename = f"{safe_entity_type}_{safe_entity_id}_{updated_at_timestamp}.pdf"
    return _cache_dir() / filename


def get_cached_pdf(entity_type, entity_id, updated_at):
    cache_path = _cache_file_path(entity_type, entity_id, updated_at)
    return str(cache_path) if cache_path.exists() else None


def save_pdf_to_cache(entity_type, entity_id, updated_at, pdf_bytes):
    cache_path = _cache_file_path(entity_type, entity_id, updated_at)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(pdf_bytes)
    return str(cache_path)


def invalidate_cached_pdf(entity_type, entity_id):
    cache_root = _cache_dir()
    if not cache_root.exists():
        return

    safe_entity_type = _sanitize(entity_type)
    safe_entity_id = _sanitize(entity_id)
    pattern = f"{safe_entity_type}_{safe_entity_id}_*.pdf"
    for file_path in cache_root.glob(pattern):
        try:
            file_path.unlink()
        except OSError:
            continue
