from __future__ import annotations

import json
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import recommender
from sources import news as news_source
from sources import prices as prices_source

# Demo-only override: see api/dashboard.py for why.
recommender.RSS_FEEDS = ["https://finance.yahoo.com/news/rssindex"]


def search_symbol(raw_symbol: str) -> dict:
    symbol = raw_symbol.strip().upper()
    if not symbol:
        raise ValueError("No symbol provided")

    # Arbitrary symbols have no curated keyword list, so fall back to the
    # symbol text itself (suffix-stripped) as the sole match keyword. This
    # is a known, disclosed limitation: headlines usually say "Apple," not
    # "AAPL," so search sentiment will often come back neutral for tickers
    # whose symbol doesn't match how the company is written in prose.
    # Momentum-based analysis is unaffected and works for any symbol.
    keyword = recommender.derive_fallback_keyword(symbol)
    asset = {"symbol": symbol, "type": None, "keywords": [keyword]}

    closes = prices_source.fetch_price_history(symbol)

    warning = None
    try:
        headlines = news_source.fetch_headlines(recommender.RSS_FEEDS)
    except RuntimeError as exc:
        headlines = []
        warning = f"News sentiment unavailable this run: {exc}"

    payload = recommender.build_asset_payload(asset, closes, headlines)
    payload["warning"] = warning
    return payload


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        raw_symbol = query.get("symbol", [""])[0]

        try:
            if not raw_symbol.strip():
                payload = {"error": "Query parameter 'symbol' is required"}
                status = 400
            else:
                payload = search_symbol(raw_symbol)
                status = 200
        except (RuntimeError, ValueError) as exc:
            payload = {"error": str(exc)}
            status = 502
        except Exception as exc:
            payload = {"error": str(exc), "traceback": traceback.format_exc()}
            status = 500

        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)
