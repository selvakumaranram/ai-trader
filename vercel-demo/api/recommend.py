from __future__ import annotations

import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import recommender

# Demo-only override: the repo's real RSS_FEEDS URLs are confirmed dead
# (feedburner.com / moneycontrol both return 0 entries as of 2026-08-03).
# That's a known, out-of-scope config issue, not a code bug -- swapped
# here so this live demo shows the full working pipeline end to end.
recommender.RSS_FEEDS = ["https://finance.yahoo.com/news/rssindex"]


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            rows = recommender.build_rankings()
            body = "QuantDesk -- Research & Recommendation (live Vercel demo)\n"
            body += f"Style: {recommender.STYLE} | Capital: Rs {recommender.CAPITAL:,.0f}\n\n"
            body += recommender.format_table(rows)
            deployed = sum(r["suggested"] for r in rows if r["suggested"] > 0)
            body += f"\n\nSuggested deployed: Rs {deployed:,.0f} | Cash buffer: Rs {recommender.CAPITAL - deployed:,.0f}\n"
            status = 200
        except Exception as exc:
            body = f"Error while building rankings (this may be the code correctly failing loudly on bad data):\n{exc}\n\n{traceback.format_exc()}"
            status = 500

        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))
