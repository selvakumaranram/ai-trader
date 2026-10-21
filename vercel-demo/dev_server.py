"""Local-only stand-in for Vercel's /api routing. Never deployed or used in production.

Run:  python vercel-demo/dev_server.py      (serves http://127.0.0.1:3001)
Then: cd vercel-demo && npm run dev           (Vite proxies /api here)

Each /api/<name> request is answered by the unmodified handler class in
api/<name>.py, so local behaviour matches the deployed functions.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import List, Optional
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
API_DIR = os.path.join(HERE, "api")
REPO_ROOT = os.path.dirname(HERE)
HOST, PORT = "127.0.0.1", 3001

# Only plain lower-case segments: no dots, so no path traversal.
_ROUTE_RE = re.compile(r"^/api/([a-z_]+)(?:/([a-z_]+))?$")
_handler_cache: dict = {}

if HERE not in sys.path:
    sys.path.insert(0, HERE)


def load_env_file(path: str) -> List[str]:
    """Set KEY=VALUE pairs from a .env file that aren't already in the
    environment. Returns the names it set (never the values)."""
    if not os.path.isfile(path):
        return []
    loaded = []
    with open(path, encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
                loaded.append(key)
    return loaded


def resolve_handler(url_path: str) -> Optional[type]:
    match = _ROUTE_RE.match(urlparse(url_path).path)
    if not match:
        return None
    parts = [p for p in match.groups() if p]
    file_path = os.path.join(API_DIR, *parts) + ".py"
    if not os.path.isfile(file_path):
        return None
    if file_path not in _handler_cache:
        spec = importlib.util.spec_from_file_location("devapi_" + "_".join(parts), file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _handler_cache[file_path] = module.handler
    return _handler_cache[file_path]


class DevRouter(BaseHTTPRequestHandler):
    def _dispatch(self, method: str) -> None:
        target = resolve_handler(self.path)
        if target is None:
            self._send_error(404, "Not found")
            return
        method_fn = getattr(target, f"do_{method}", None)
        if method_fn is None:
            self._send_error(405, "Method not allowed")
            return
        # The api handlers only use the BaseHTTPRequestHandler request/response
        # API, which this instance provides, so call them with this request.
        method_fn(self)

    def _send_error(self, status: int, message: str) -> None:
        body = json.dumps({"error": message}).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_DELETE(self):
        self._dispatch("DELETE")


def main() -> None:
    loaded = load_env_file(os.path.join(REPO_ROOT, ".env"))
    print(f"Loaded from .env: {', '.join(loaded) or '(nothing new)'}")
    print(f"QuantDesk dev API on http://{HOST}:{PORT}  (Ctrl+C to stop)")
    ThreadingHTTPServer((HOST, PORT), DevRouter).serve_forever()


if __name__ == "__main__":
    main()
