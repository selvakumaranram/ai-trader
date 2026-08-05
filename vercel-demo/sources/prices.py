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

    def _extract(column: str) -> List[float]:
        series = data[column]
        if hasattr(series, "columns"):
            # Some yfinance versions return a single-column DataFrame here
            # instead of a Series even for one symbol — flatten it.
            series = series.iloc[:, 0]
        return [float(value) for value in series.tolist()]

    try:
        close = _extract("Close")
    except KeyError:
        raise RuntimeError(f"No 'Close' column in price data for {yf_symbol!r}") from None
    except (ValueError, TypeError) as exc:
        raise RuntimeError(f"Non-numeric value in 'Close' column for {yf_symbol!r}: {exc}") from exc

    raw: Dict[str, List[float]] = {"close": close}
    for label, column in _COLUMNS:
        if label == "close":
            continue
        try:
            raw[label] = _extract(column)
        except (KeyError, ValueError, TypeError):
            # Close is the only hard requirement (matches the pre-OHLCV
            # fetch_price_history contract exactly) — a missing OR
            # non-numeric Open/High/Low/Volume column degrades to
            # NaN-filled rather than aborting the whole fetch, since
            # callers of those columns already have to tolerate a stray
            # NaN per-row.
            raw[label] = [float("nan")] * len(close)

    try:
        dates = [ts.date().isoformat() for ts in data.index]
    except Exception:
        dates = [None] * len(close)

    # Demo-only relaxation (unchanged from the original close-only
    # version): drop rows where Close is NaN rather than aborting the
    # whole ranking run. Row selection is driven by Close alone, matching
    # the pre-OHLCV behavior exactly, so existing close-only callers see
    # no behavior change. Open/High/Low/Volume/dates are carried along
    # using the same row selection — callers using those columns must
    # tolerate an occasional stray NaN/None on a day Close happened to be
    # valid.
    valid_rows = [i for i, c in enumerate(raw["close"]) if c == c]  # NaN != NaN
    result = {label: [raw[label][i] for i in valid_rows] for label, _ in _COLUMNS}
    result["dates"] = [dates[i] for i in valid_rows]
    if not result["close"]:
        raise RuntimeError(f"Price data for {yf_symbol!r} is entirely NaN")
    return result


def fetch_price_history(yf_symbol: str, period: str = "6mo") -> List[float]:
    return fetch_ohlcv_history(yf_symbol, period)["close"]
