from __future__ import annotations

import hmac
import json
import os
import re
import sys
import traceback
from typing import Optional

MAX_BODY_BYTES = 64 * 1024
_DEVICE_ID_RE = re.compile(r"^[A-Za-z0-9-]{1,64}$")


class HttpError(Exception):
    """A client-facing error: the message is safe to return in the response."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def device_id_from_headers(headers) -> str:
    device_id = (headers.get("X-Device-Id") or "").strip()
    if not device_id:
        raise HttpError(400, "Missing X-Device-Id header")
    if not _DEVICE_ID_RE.match(device_id):
        raise HttpError(400, "Invalid X-Device-Id header")
    return device_id


def read_json_object(handler) -> dict:
    raw_length = (handler.headers.get("Content-Length") or "0").strip()
    try:
        length = int(raw_length)
    except ValueError:
        raise HttpError(400, "Invalid Content-Length header") from None
    if length < 0:
        raise HttpError(400, "Invalid Content-Length header")
    if length > MAX_BODY_BYTES:
        # Refuse before reading so an oversized body never lands in memory.
        raise HttpError(413, f"Request body exceeds {MAX_BODY_BYTES} bytes")

    raw = handler.rfile.read(length) if length else b""
    try:
        body = json.loads(raw or b"{}")
    except (ValueError, RecursionError):
        # RecursionError: pathologically nested JSON that still fits the size cap.
        raise HttpError(400, "Request body must be valid JSON") from None
    if not isinstance(body, dict):
        raise HttpError(400, "Request body must be a JSON object")
    return body


def allowed_origin(request_origin: Optional[str]) -> Optional[str]:
    """The SPA is served from the same origin as the API, so no CORS header
    is needed by default. Cross-origin callers must be listed explicitly in
    ALLOWED_ORIGINS (comma-separated, exact match)."""
    configured = {o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()}
    if request_origin and request_origin in configured:
        return request_origin
    return None


def internal_error(exc: BaseException) -> dict:
    # Full detail goes to the server log (Vercel function logs), never to the client.
    traceback.print_exception(exc, file=sys.stderr)
    return {"error": "Internal server error"}


def _send_cors_headers(handler) -> None:
    origin = allowed_origin(handler.headers.get("Origin"))
    if origin:
        handler.send_header("Access-Control-Allow-Origin", origin)
        handler.send_header("Access-Control-Allow-Headers", "X-Device-Id, Content-Type")
        handler.send_header("Vary", "Origin")


def send_json(handler, status: int, payload: Optional[dict]) -> None:
    body = b"" if status == 204 or payload is None else json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    if body:
        handler.send_header("Content-Type", "application/json; charset=utf-8")
    _send_cors_headers(handler)
    handler.end_headers()
    if body:
        handler.wfile.write(body)


def send_text(handler, status: int, text: str) -> None:
    handler.send_response(status)
    handler.send_header("Content-Type", "text/plain; charset=utf-8")
    _send_cors_headers(handler)
    handler.end_headers()
    handler.wfile.write(text.encode("utf-8"))


def bearer_token_matches(headers, secret: str) -> bool:
    supplied = (headers.get("Authorization") or "").encode("utf-8")
    expected = f"Bearer {secret}".encode("utf-8")
    return hmac.compare_digest(supplied, expected)
