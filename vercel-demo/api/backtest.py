from __future__ import annotations

import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import backtest
import http_utils
from sources import prices as prices_source

MAX_WINDOW = 250  # ~1 year of trading days; the fetch below is period="1y"


def parse_backtest_query(path: str) -> tuple:
    query = parse_qs(urlparse(path).query)
    symbol = query.get("symbol", ["RELIANCE.NS"])[0].strip()
    if not symbol:
        raise ValueError("symbol must not be empty")
    try:
        short_window = int(query.get("short", ["20"])[0])
        long_window = int(query.get("long", ["50"])[0])
    except ValueError:
        raise ValueError("short and long must be whole numbers") from None
    if not 1 <= short_window < long_window <= MAX_WINDOW:
        raise ValueError(f"Windows must satisfy 1 <= short < long <= {MAX_WINDOW}")
    return symbol, short_window, long_window


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            symbol, short_window, long_window = parse_backtest_query(self.path)
            prices = prices_source.fetch_price_history(symbol, period="1y")
            if len(prices) <= long_window:
                raise ValueError(
                    f"Only {len(prices)} price points for {symbol!r}; need more than the long window ({long_window})"
                )
            strategy_value, buy_hold_value, periods = backtest.run_backtest(prices, short_window, long_window)
            text = (
                f"Backtest for {symbol} | periods={periods} | short={short_window} | long={long_window}\n"
                f"Strategy final value: Rs {strategy_value:,.2f}\n"
                f"Buy-and-hold value:  Rs {buy_hold_value:,.2f}\n"
            )
            text += (
                "Outcome: strategy outperformed buy-and-hold.\n"
                if strategy_value > buy_hold_value
                else "Outcome: strategy underperformed buy-and-hold.\n"
            )
            status = 200
        except ValueError as exc:
            text, status = f"Error: {exc}\n", 400
        except RuntimeError as exc:
            text, status = f"Error fetching price data: {exc}\n", 502
        except Exception as exc:
            text, status = f"Error: {http_utils.internal_error(exc)['error']}\n", 500
        http_utils.send_text(self, status, text)
