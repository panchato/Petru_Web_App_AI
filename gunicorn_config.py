import os

bind = "0.0.0.0:8080"
workers = 2
max_request_body_bytes = int(os.environ.get("MAX_CONTENT_LENGTH_BYTES", str(16 * 1024 * 1024)))


def pre_request(worker, req):
    content_length = req.headers.get("content-length")
    if not content_length:
        return
    try:
        request_size = int(content_length)
    except (TypeError, ValueError):
        return

    if request_size > max_request_body_bytes:
        worker.log.warning("Rejected request body size %s > %s bytes", request_size, max_request_body_bytes)
        raise RuntimeError("Request body too large")
