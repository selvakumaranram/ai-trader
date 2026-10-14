"""Drive a vercel-demo/api handler class in-process: no socket, DB or network."""
from __future__ import annotations

import importlib.util
import io
import json
import os
from email.message import Message

API_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "vercel-demo", "api"))


def load_api_module(relative_path: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, os.path.join(API_DIR, relative_path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Response:
    def __init__(self, raw: bytes):
        head, _, self.body = raw.partition(b"\r\n\r\n")
        lines = head.decode("latin-1").split("\r\n")
        self.status = int(lines[0].split()[1])
        self.headers = {}
        for line in lines[1:]:
            name, _, value = line.partition(":")
            self.headers[name.strip().lower()] = value.strip()

    def json(self):
        return json.loads(self.body)

    @property
    def text(self) -> str:
        return self.body.decode("utf-8")


def call(handler_cls, method: str, path: str, headers=None, body: bytes = b"") -> Response:
    handler = handler_cls.__new__(handler_cls)  # skip socket setup in __init__
    message = Message()
    for name, value in (headers or {}).items():
        message[name] = value
    if body and "Content-Length" not in message:
        message["Content-Length"] = str(len(body))
    handler.headers = message
    handler.path = path
    handler.command = method
    handler.request_version = "HTTP/1.1"
    handler.requestline = f"{method} {path} HTTP/1.1"
    handler.client_address = ("127.0.0.1", 0)
    handler.rfile = io.BytesIO(body)
    handler.wfile = io.BytesIO()
    handler.log_message = lambda *args, **kwargs: None
    getattr(handler, f"do_{method}")()
    return Response(handler.wfile.getvalue())


class _FakeCursor:
    def __init__(self, conn):
        self._conn = conn
        self._rows = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self._conn.executed.append((sql, params))
        self._rows = self._conn.on_execute(sql, params) if self._conn.on_execute else []

    def executemany(self, sql, seq):
        self._conn.executed.append((sql, list(seq)))

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


class FakeConnection:
    """on_execute(sql, params) returns the rows for that statement, or raises."""

    def __init__(self, on_execute=None):
        self.on_execute = on_execute
        self.executed = []
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return _FakeCursor(self)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True
