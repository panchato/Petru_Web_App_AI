from datetime import datetime
from urllib.parse import urljoin, urlparse

from flask import abort, current_app, request, send_file

from app.upload_security import resolve_upload_path


def is_safe_redirect_url(target):
    base_url = urlparse(request.host_url)
    target_url = urlparse(urljoin(request.host_url, target))
    return base_url.scheme == target_url.scheme and base_url.netloc == target_url.netloc


def _parse_date_arg(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _paginate_query(query):
    default_per_page = int(current_app.config.get("DEFAULT_PAGE_SIZE", 50))
    max_per_page = int(current_app.config.get("MAX_PAGE_SIZE", 200))

    page = request.args.get("page", default=1, type=int) or 1
    requested_per_page = request.args.get("per_page", type=int)
    per_page = requested_per_page if requested_per_page and requested_per_page > 0 else default_per_page
    per_page = min(per_page, max_per_page)

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    page_args = request.args.to_dict(flat=True)
    page_args.pop("page", None)
    if requested_per_page:
        page_args["per_page"] = str(per_page)
    else:
        page_args.pop("per_page", None)
    return pagination.items, pagination, page_args


def _upload_path_to_file_uri(stored_path):
    upload_path = resolve_upload_path(stored_path)
    if not upload_path:
        return None
    return upload_path.resolve().as_uri()


def _upload_mimetype_for_path(upload_path):
    suffix = upload_path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".pdf":
        return "application/pdf"
    return "application/octet-stream"


def _send_private_upload(stored_path):
    upload_path = resolve_upload_path(stored_path)
    if not upload_path:
        abort(404)
    return send_file(upload_path, mimetype=_upload_mimetype_for_path(upload_path), as_attachment=False)
