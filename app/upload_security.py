import os
import secrets
import shlex
import subprocess
from pathlib import Path

from flask import current_app


class UploadValidationError(ValueError):
    """Raised when an uploaded file does not pass security validation."""


_UPLOAD_POLICIES = {
    "image": {
        "subdir": "images",
        "extensions": {"jpg", "jpeg", "png"},
        "mime_types": {"image/jpeg", "image/png"},
        "extensions_by_mime": {
            "image/jpeg": {"jpg", "jpeg"},
            "image/png": {"png"},
        },
        "canonical_extensions": {
            "image/jpeg": "jpg",
            "image/png": "png",
        },
    },
    "pdf": {
        "subdir": "pdf",
        "extensions": {"pdf"},
        "mime_types": {"application/pdf"},
        "extensions_by_mime": {
            "application/pdf": {"pdf"},
        },
        "canonical_extensions": {
            "application/pdf": "pdf",
        },
    },
}


def _normalize_upload_path(stored_path):
    if not stored_path:
        return None
    normalized = stored_path.replace("\\", "/").lstrip("/")
    return normalized or None


def _detect_mime_type(file_path):
    with file_path.open("rb") as f:
        header = f.read(16)

    if header.startswith(b"%PDF-"):
        return "application/pdf"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    return None


def _run_virus_scan(file_path):
    if not current_app.config.get("VIRUS_SCAN_ENABLED", False):
        return

    scan_command = current_app.config.get("VIRUS_SCAN_COMMAND", "").strip()
    if not scan_command:
        raise UploadValidationError("El escaneo antivirus está habilitado pero no tiene comando configurado.")

    timeout_seconds = int(current_app.config.get("VIRUS_SCAN_TIMEOUT_SECONDS", 30))
    command_parts = shlex.split(scan_command, posix=(os.name != "nt"))
    if not command_parts:
        raise UploadValidationError("Comando de antivirus inválido.")

    try:
        completed = subprocess.run(
            [*command_parts, str(file_path)],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        current_app.logger.error("Error en escaneo antivirus: %s", exc)
        raise UploadValidationError("No se pudo completar el escaneo antivirus.") from exc

    if completed.returncode != 0:
        current_app.logger.warning(
            "Archivo bloqueado por antivirus. rc=%s stdout=%s stderr=%s",
            completed.returncode,
            completed.stdout.strip(),
            completed.stderr.strip(),
        )
        raise UploadValidationError("El archivo no superó el escaneo antivirus.")


def save_uploaded_file(uploaded_file, kind):
    if not uploaded_file or not getattr(uploaded_file, "filename", None):
        raise UploadValidationError("No se recibió archivo.")

    policy = _UPLOAD_POLICIES.get(kind)
    if policy is None:
        raise UploadValidationError("Tipo de archivo no soportado.")

    original_extension = Path(uploaded_file.filename).suffix.lower().lstrip(".")
    if original_extension not in policy["extensions"]:
        raise UploadValidationError("Tipo de archivo no permitido.")

    upload_root = Path(current_app.config["UPLOAD_ROOT"]).resolve()
    destination_dir = upload_root / policy["subdir"]
    temp_dir = upload_root / "tmp"
    destination_dir.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    temp_path = temp_dir / f"upload_{secrets.token_hex(16)}.tmp"
    uploaded_file.save(temp_path)

    try:
        max_bytes = int(current_app.config.get("MAX_UPLOAD_FILE_BYTES", 0))
        if max_bytes and temp_path.stat().st_size > max_bytes:
            raise UploadValidationError("El archivo supera el tamaño máximo permitido.")

        detected_mime = _detect_mime_type(temp_path)
        if detected_mime not in policy["mime_types"]:
            raise UploadValidationError("El contenido del archivo no coincide con un tipo permitido.")

        if original_extension not in policy["extensions_by_mime"][detected_mime]:
            raise UploadValidationError("La extensión del archivo no coincide con su contenido.")

        canonical_extension = policy["canonical_extensions"][detected_mime]
        _run_virus_scan(temp_path)

        generated_name = f"{secrets.token_hex(24)}.{canonical_extension}"
        destination_path = destination_dir / generated_name
        os.replace(temp_path, destination_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()

    return f"{policy['subdir']}/{generated_name}"


def resolve_upload_path(stored_path):
    normalized = _normalize_upload_path(stored_path)
    if not normalized:
        return None

    relative_path = Path(normalized)
    if relative_path.is_absolute() or len(relative_path.parts) != 2:
        return None

    if relative_path.parts[0] not in {"images", "pdf"}:
        return None

    upload_root = Path(current_app.config["UPLOAD_ROOT"]).resolve()
    absolute_path = (upload_root / relative_path).resolve()
    if upload_root != absolute_path and upload_root not in absolute_path.parents:
        return None

    if not absolute_path.exists() or not absolute_path.is_file():
        return None
    return absolute_path
