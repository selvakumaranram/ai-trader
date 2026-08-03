from __future__ import annotations

import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import backtest
from sources import prices as prices_source


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        symbol = query.get("symbol", ["RELIANCE.NS"])[0]
        short_window = int(query.get("short", ["20"])[0])
        long_window = int(query.get("long", ["50"])[0])

        try:
            prices = prices_source.fetch_price_history(symbol, period="1y")
            strategy_value, buy_hold_value, periods = backtest.run_backtest(prices, short_window, long_window)
            body = (
                f"Backtest for {symbol} | periods={periods} | short={short_window} | long={long_window}\n"
                f"Strategy final value: Rs {strategy_value:,.2f}\n"
                f"Buy-and-hold value:  Rs {buy_hold_value:,.2f}\n"
            )
            body += (
                "Outcome: strategy outperformed buy-and-hold.\n"
                if strategy_value > buy_hold_value
                else "Outcome: strategy underperformed buy-and-hold.\n"
            )
            status = 200
        except Exception as exc:
            body = f"Error running backtest:\n{exc}\n\n{traceback.format_exc()}"
            status = 500

        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))
