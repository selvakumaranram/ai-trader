from __future__ import annotations

import datetime
import json
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import db

_VALID_TABS = {"screener", "1d", "3d", "7d", "1m"}
_SORT_COLUMN = {"1d": "return_1d", "3d": "return_3d", "7d": "return_7d", "1m": "return_1m"}
_STALE_AFTER_DAYS = 2


def _row_to_dict(row) -> dict:
    return {
        "symbol": row["symbol"],
        "sector": row["sector"],
        "pe_ratio": float(row["pe_ratio"]) if row["pe_ratio"] is not None else None,
        "current_price": float(row["current_price"]),
        "return_1d": float(row["return_1d"]) if row["return_1d"] is not None else None,
        "return_3d": float(row["return_3d"]) if row["return_3d"] is not None else None,
        "return_7d": float(row["return_7d"]) if row["return_7d"] is not None else None,
        "return_1m": float(row["return_1m"]) if row["return_1m"] is not None else None,
        "passes_quality_gates": row["passes_quality_gates"],
        "passes_trend_gate": row["passes_trend_gate"],
        "quality_gate_detail": row["quality_gate_detail"],
        "momentum_score": float(row["momentum_score"]) if row["momentum_score"] is not None else None,
        "volume_confirmation": row["volume_confirmation"],
        "stop_loss": float(row["stop_loss"]) if row["stop_loss"] is not None else None,
        "target_low": float(row["target_low"]) if row["target_low"] is not None else None,
        "target_high": float(row["target_high"]) if row["target_high"] is not None else None,
        "screener_url": f"https://www.screener.in/company/{row['symbol']}/",
    }


def get_momentum(tab: str) -> dict:
    if tab not in _VALID_TABS:
        raise ValueError(f"tab must be one of {sorted(_VALID_TABS)}, got {tab!r}")

    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT MAX(run_date) AS latest FROM momentum_rankings")
            latest_row = cur.fetchone()
            run_date = latest_row["latest"] if latest_row else None
            if run_date is None:
                raise LookupError("No momentum screen has run yet")

            if tab == "screener":
                cur.execute(
                    "SELECT * FROM momentum_rankings WHERE run_date = %s "
                    "AND passes_quality_gates = TRUE AND passes_trend_gate = TRUE "
                    "ORDER BY momentum_score DESC NULLS LAST LIMIT 20",
                    (run_date,),
                )
            else:
                column = _SORT_COLUMN[tab]
                cur.execute(
                    f"SELECT * FROM momentum_rankings WHERE run_date = %s "
                    f"ORDER BY {column} DESC NULLS LAST LIMIT 20",
                    (run_date,),
                )
            rows = cur.fetchall()
    finally:
        conn.close()

    stale = (datetime.date.today() - run_date).days > _STALE_AFTER_DAYS
    return {"run_date": run_date.isoformat(), "stale": stale, "rows": [_row_to_dict(r) for r in rows]}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            query = parse_qs(urlparse(self.path).query)
            tab = query.get("tab", ["screener"])[0]
            payload = get_momentum(tab)
            status = 200
        except ValueError as exc:
            payload = {"error": str(exc)}
            status = 400
        except LookupError as exc:
            payload = {"error": str(exc)}
            status = 503
        except Exception as exc:
            payload = {"error": str(exc), "traceback": traceback.format_exc()}
            status = 500
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)
