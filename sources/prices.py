from __future__ import annotations

from typing import List

import yfinance as yf


def fetch_price_history(yf_symbol: str, period: str = "6mo") -> List[float]:
    try:
        data = yf.download(yf_symbol, period=period, progress=False)
    except Exception as exc:
        raise RuntimeError(f"Failed to fetch price history for {yf_symbol!r}: {exc}") from exc

    if data is None or getattr(data, "empty", True):
        raise RuntimeError(f"No price data returned for {yf_symbol!r} (period={period!r})")

    try:
        closes = data["Close"]
    except KeyError:
        raise RuntimeError(f"No 'Close' column in price data for {yf_symbol!r}") from None
    if hasattr(closes, "columns"):
        # Some yfinance versions return a single-column DataFrame here
        # instead of a Series even for one symbol — flatten it.
        closes = closes.iloc[:, 0]
    return [float(value) for value in closes.tolist()]
