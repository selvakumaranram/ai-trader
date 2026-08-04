from __future__ import annotations

import json
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import db
import recommender
from sources import news as news_source
from sources import prices as prices_source

# Demo-only override: see api/dashboard.py for why.
recommender.RSS_FEEDS = ["https://finance.yahoo.com/news/rssindex"]


def _device_id_from_headers(headers) -> str:
    device_id = (headers.get("X-Device-Id") or "").strip()
    if not device_id:
        raise ValueError("Missing X-Device-Id header")
    return device_id


def list_watchlist(device_id):
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, symbol FROM watchlist WHERE device_id = %s ORDER BY created_at DESC",
                (device_id,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    try:
        headlines = news_source.fetch_headlines(recommender.RSS_FEEDS)
    except RuntimeError:
        headlines = []

    watchlist = []
    failed = []
    for row in rows:
        symbol = row["symbol"]
        try:
            asset = {
                "symbol": symbol,
                "type": None,
                "keywords": [recommender.derive_fallback_keyword(symbol)],
            }
            closes = prices_source.fetch_price_history(symbol)
            payload = recommender.build_asset_payload(asset, closes, headlines)
            watchlist.append({"id": row["id"], **payload})
        except Exception as exc:
            failed.append({"id": row["id"], "symbol": symbol, "error": str(exc)})
    return {"watchlist": watchlist, "failed": failed}


def add_to_watchlist(device_id, body):
    symbol = str(body.get("symbol", "")).strip().upper()
    if not symbol:
        raise ValueError("symbol is required")

    # Fail loudly if the symbol isn't fetchable, before persisting anything.
    prices_source.fetch_price_history(symbol)

    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM watchlist WHERE device_id = %s AND symbol = %s",
                (device_id, symbol),
            )
            if cur.fetchone() is not None:
                raise LookupError("already in your watchlist")
            cur.execute(
                "INSERT INTO watchlist (device_id, symbol) VALUES (%s, %s) RETURNING id, symbol",
                (device_id, symbol),
            )
            row = cur.fetchone()
        conn.commit()
    finally:
        conn.close()

    return {"id": row["id"], "symbol": row["symbol"]}


def delete_from_watchlist(device_id, watchlist_id):
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM watchlist WHERE id = %s AND device_id = %s RETURNING id",
                (watchlist_id, device_id),
            )
            row = cur.fetchone()
        conn.commit()
    finally:
        conn.close()
    if row is None:
        raise LookupError("Watchlist entry not found")


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            device_id = _device_id_from_headers(self.headers)
            payload = list_watchlist(device_id)
            status = 200
        except ValueError as exc:
            payload = {"error": str(exc)}
            status = 400
        except Exception as exc:
            payload = {"error": str(exc), "traceback": traceback.format_exc()}
            status = 500
        self._send_json(status, payload)

    def do_POST(self):
        try:
            device_id = _device_id_from_headers(self.headers)
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(body, dict):
                raise ValueError("Request body must be a JSON object")
            payload = add_to_watchlist(device_id, body)
            status = 201
        except ValueError as exc:
            payload = {"error": str(exc)}
            status = 400
        except LookupError as exc:
            payload = {"error": str(exc)}
            status = 409
        except RuntimeError as exc:
            payload = {"error": str(exc)}
            status = 502
        except Exception as exc:
            payload = {"error": str(exc), "traceback": traceback.format_exc()}
            status = 500
        self._send_json(status, payload)

    def do_DELETE(self):
        try:
            device_id = _device_id_from_headers(self.headers)
            query = parse_qs(urlparse(self.path).query)
            raw_id = query.get("id", [""])[0]
            if not raw_id.isdigit():
                raise ValueError("Query parameter 'id' must be a positive integer")
            delete_from_watchlist(device_id, int(raw_id))
            payload = {"deleted": True}
            status = 204
        except ValueError as exc:
            payload = {"error": str(exc)}
            status = 400
        except LookupError as exc:
            payload = {"error": str(exc)}
            status = 404
        except Exception as exc:
            payload = {"error": str(exc), "traceback": traceback.format_exc()}
            status = 500
        self._send_json(status, payload)

    def _send_json(self, status, payload):
        body = b"" if status == 204 else json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "X-Device-Id, Content-Type")
        self.end_headers()
        if body:
            self.wfile.write(body)
