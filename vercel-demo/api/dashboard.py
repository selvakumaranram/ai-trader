from __future__ import annotations

import json
import os
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import recommender
from sources import news as news_source
from sources import prices as prices_source

# Demo-only override: the repo's real RSS_FEEDS URLs are confirmed dead
# (feedburner.com / moneycontrol both return 0 entries). Matches the same
# override previously used in the now-removed api/recommend.py.
recommender.RSS_FEEDS = ["https://finance.yahoo.com/news/rssindex"]


def _fetch_one(asset):
    closes = prices_source.fetch_price_history(asset["yf_symbol"])
    return asset, closes


def build_dashboard():
    warning = None
    try:
        headlines = news_source.fetch_headlines(recommender.RSS_FEEDS)
    except RuntimeError as exc:
        headlines = []
        warning = f"News sentiment unavailable this run: {exc}"

    assets = []
    failed = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(_fetch_one, asset): asset for asset in recommender.UNIVERSE}
        for future in as_completed(futures):
            asset = futures[future]
            try:
                _, closes = future.result()
                assets.append(recommender.build_asset_payload(asset, closes, headlines))
            except Exception as exc:
                failed.append({"symbol": asset["symbol"], "error": str(exc)})

    assets.sort(key=lambda a: a["symbol"])
    failed.sort(key=lambda f: f["symbol"])
    return {"assets": assets, "failed": failed, "warning": warning}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            payload = build_dashboard()
            status = 200
        except Exception as exc:
            payload = {"error": str(exc), "traceback": traceback.format_exc()}
            status = 500

        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)
