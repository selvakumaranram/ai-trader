from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import db
import http_utils
import recommender
from sources import news as news_source
from sources import prices as prices_source

def _fetch_one_watchlist_item(row, headlines):
    symbol = row["symbol"]
    asset = {
        "symbol": symbol,
        "type": None,
        "keywords": [recommender.derive_fallback_keyword(symbol)],
    }
    closes = prices_source.fetch_price_history(symbol)
    payload = recommender.build_asset_payload(asset, closes, headlines)
    return {"id": row["id"], **payload}


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

    warning = None
    try:
        headlines = news_source.fetch_headlines(recommender.RSS_FEEDS)
    except RuntimeError as exc:
        headlines = []
        warning = f"News sentiment unavailable this run: {exc}"

    results = {}
    failed = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(_fetch_one_watchlist_item, row, headlines): row for row in rows}
        for future in as_completed(futures):
            row = futures[future]
            try:
                results[row["id"]] = future.result()
            except Exception as exc:
                failed.append({"id": row["id"], "symbol": row["symbol"], "error": str(exc)})

    watchlist = [results[row["id"]] for row in rows if row["id"] in results]
    return {"watchlist": watchlist, "failed": failed, "warning": warning}


def add_to_watchlist(device_id, body):
    symbol = str(body.get("symbol", "")).strip().upper()
    if not symbol:
        raise ValueError("symbol is required")

    # Fail loudly if the symbol isn't fetchable or lacks enough price
    # history to score (same computation GET will need later), before
    # persisting anything.
    closes = prices_source.fetch_price_history(symbol)
    asset = {"symbol": symbol, "type": None, "keywords": [recommender.derive_fallback_keyword(symbol)]}
    recommender.build_asset_payload(asset, closes, [])

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
            device_id = http_utils.device_id_from_headers(self.headers)
            payload, status = list_watchlist(device_id), 200
        except http_utils.HttpError as exc:
            payload, status = {"error": str(exc)}, exc.status
        except ValueError as exc:
            payload, status = {"error": str(exc)}, 400
        except Exception as exc:
            payload, status = http_utils.internal_error(exc), 500
        http_utils.send_json(self, status, payload)

    def do_POST(self):
        try:
            device_id = http_utils.device_id_from_headers(self.headers)
            body = http_utils.read_json_object(self)
            payload, status = add_to_watchlist(device_id, body), 201
        except http_utils.HttpError as exc:
            payload, status = {"error": str(exc)}, exc.status
        except ValueError as exc:
            payload, status = {"error": str(exc)}, 400
        except LookupError as exc:
            payload, status = {"error": str(exc)}, 409
        except RuntimeError as exc:
            payload, status = {"error": str(exc)}, 502
        except Exception as exc:
            payload, status = http_utils.internal_error(exc), 500
        http_utils.send_json(self, status, payload)

    def do_DELETE(self):
        try:
            device_id = http_utils.device_id_from_headers(self.headers)
            query = parse_qs(urlparse(self.path).query)
            raw_id = query.get("id", [""])[0]
            if not raw_id.isdigit():
                raise ValueError("Query parameter 'id' must be a positive integer")
            delete_from_watchlist(device_id, int(raw_id))
            payload, status = None, 204
        except http_utils.HttpError as exc:
            payload, status = {"error": str(exc)}, exc.status
        except ValueError as exc:
            payload, status = {"error": str(exc)}, 400
        except LookupError as exc:
            payload, status = {"error": str(exc)}, 404
        except Exception as exc:
            payload, status = http_utils.internal_error(exc), 500
        http_utils.send_json(self, status, payload)
