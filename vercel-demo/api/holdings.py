from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import db
import recommender
from holdings_logic import compute_holding_period, compute_sell_signal
from sources import news as news_source
from sources import prices as prices_source

# Demo-only override: see api/dashboard.py for why.
recommender.RSS_FEEDS = ["https://finance.yahoo.com/news/rssindex"]


def _device_id_from_headers(headers) -> str:
    device_id = (headers.get("X-Device-Id") or "").strip()
    if not device_id:
        raise ValueError("Missing X-Device-Id header")
    return device_id


def _build_holding_result(row, headlines):
    symbol = row["symbol"]
    asset = {"symbol": symbol, "type": None, "keywords": [recommender.derive_fallback_keyword(symbol)]}
    closes = prices_source.fetch_price_history(symbol)
    payload = recommender.build_asset_payload(asset, closes, headlines)

    current_price = closes[-1]
    buy_price = float(row["buy_price"])
    quantity = float(row["quantity"])
    period = compute_holding_period(row["buy_date"], symbol)
    sell_signal = compute_sell_signal(payload["scores"])

    return {
        "id": row["id"],
        "symbol": symbol,
        "buy_price": buy_price,
        "quantity": quantity,
        "buy_date": row["buy_date"].isoformat(),
        "current_price": round(current_price, 2),
        "unrealized_pnl": round((current_price - buy_price) * quantity, 2),
        "unrealized_pnl_pct": round((current_price - buy_price) / buy_price * 100, 2),
        "days_held": period["days_held"],
        "ltcg_applicable": period["ltcg_applicable"],
        "ltcg_eligible": period["ltcg_eligible"],
        "days_to_ltcg": period["days_to_ltcg"],
        "momentum": payload["momentum"],
        "momentum_detail": payload["momentum_detail"],
        "sentiment": payload["sentiment"],
        "day_change_pct": payload["day_change_pct"],
        "matched_headlines": payload["matched_headlines"],
        "scores": payload["scores"],
        "sell_signal": sell_signal,
    }


def list_holdings(device_id):
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, symbol, buy_price, quantity, buy_date FROM holdings "
                "WHERE device_id = %s ORDER BY created_at DESC",
                (device_id,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    try:
        headlines = news_source.fetch_headlines(recommender.RSS_FEEDS)
    except RuntimeError:
        headlines = []

    holdings = []
    failed = []
    for row in rows:
        try:
            holdings.append(_build_holding_result(row, headlines))
        except Exception as exc:
            failed.append({"id": row["id"], "symbol": row["symbol"], "error": str(exc)})
    return {"holdings": holdings, "failed": failed}


def add_holding(device_id, body):
    symbol = str(body.get("symbol", "")).strip().upper()
    if not symbol:
        raise ValueError("symbol is required")

    try:
        buy_price = float(body["buy_price"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("buy_price must be a positive number")
    if buy_price <= 0:
        raise ValueError("buy_price must be a positive number")

    try:
        quantity = float(body["quantity"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("quantity must be a positive number")
    if quantity <= 0:
        raise ValueError("quantity must be a positive number")

    try:
        buy_date = datetime.strptime(str(body.get("buy_date", "")), "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("buy_date must be in YYYY-MM-DD format")
    if buy_date > date.today():
        raise ValueError("buy_date cannot be in the future")

    # Fail loudly if the symbol isn't fetchable, before persisting anything.
    prices_source.fetch_price_history(symbol)

    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO holdings (device_id, symbol, buy_price, quantity, buy_date) "
                "VALUES (%s, %s, %s, %s, %s) RETURNING id, symbol, buy_price, quantity, buy_date",
                (device_id, symbol, buy_price, quantity, buy_date),
            )
            row = cur.fetchone()
        conn.commit()
    finally:
        conn.close()

    return {
        "id": row["id"],
        "symbol": row["symbol"],
        "buy_price": float(row["buy_price"]),
        "quantity": float(row["quantity"]),
        "buy_date": row["buy_date"].isoformat(),
    }


def delete_holding(device_id, holding_id):
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM holdings WHERE id = %s AND device_id = %s RETURNING id",
                (holding_id, device_id),
            )
            row = cur.fetchone()
        conn.commit()
    finally:
        conn.close()
    if row is None:
        raise LookupError("Holding not found")


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            device_id = _device_id_from_headers(self.headers)
            payload = list_holdings(device_id)
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
            payload = add_holding(device_id, body)
            status = 201
        except ValueError as exc:
            payload = {"error": str(exc)}
            status = 400
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
            delete_holding(device_id, int(raw_id))
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
