from __future__ import annotations

from typing import Dict, List

import yfinance as yf

_COLUMNS = (("open", "Open"), ("high", "High"), ("low", "Low"), ("close", "Close"), ("volume", "Volume"))


def fetch_ohlcv_history(yf_symbol: str, period: str = "6mo") -> Dict[str, List[float]]:
    try:
        data = yf.download(yf_symbol, period=period, progress=False)
    except Exception as exc:
        raise RuntimeError(f"Failed to fetch price history for {yf_symbol!r}: {exc}") from exc

    if data is None or getattr(data, "empty", True):
        raise RuntimeError(f"No price data returned for {yf_symbol!r} (period={period!r})")

    raw: Dict[str, List[float]] = {}
    for label, column in _COLUMNS:
        try:
            series = data[column]
        except KeyError:
            raise RuntimeError(f"No {column!r} column in price data for {yf_symbol!r}") from None
        if hasattr(series, "columns"):
            # Some yfinance versions return a single-column DataFrame here
            # instead of a Series even for one symbol — flatten it.
            series = series.iloc[:, 0]
        raw[label] = [float(value) for value in series.tolist()]

    # Demo-only relaxation (unchanged from the original close-only
    # version): drop rows where Close is NaN rather than aborting the
    # whole ranking run. Row selection is driven by Close alone, matching
    # the pre-OHLCV behavior exactly, so existing close-only callers see
    # no behavior change. Open/High/Low/Volume are carried along using
    # the same row selection — callers using those columns must tolerate
    # an occasional stray NaN on a day Close happened to be valid.
    valid_rows = [i for i, close in enumerate(raw["close"]) if close == close]  # NaN != NaN
    result = {label: [raw[label][i] for i in valid_rows] for label, _ in _COLUMNS}
    if not result["close"]:
        raise RuntimeError(f"Price data for {yf_symbol!r} is entirely NaN")
    return result


def fetch_price_history(yf_symbol: str, period: str = "6mo") -> List[float]:
    return fetch_ohlcv_history(yf_symbol, period)["close"]
