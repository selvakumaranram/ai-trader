from __future__ import annotations

from typing import Dict, List, Optional

UNKNOWN = "unknown"


# --- Trend & momentum indicators -------------------------------------------

def _ema_series(values: List[float], period: int) -> List[float]:
    multiplier = 2 / (period + 1)
    ema_values = [sum(values[:period]) / period]
    for value in values[period:]:
        ema_values.append((value - ema_values[-1]) * multiplier + ema_values[-1])
    return ema_values


def compute_ema_trend(closes: List[float]) -> Dict[str, object]:
    if len(closes) < 30:
        raise ValueError(f"Need at least 30 closes for EMA trend, got {len(closes)}")
    ema20 = _ema_series(closes, 20)[-1]
    ema50 = _ema_series(closes, 50)[-1]
    price = closes[-1]
    passes = price > ema20 and price > ema50 and ema20 > ema50
    return {"ema20": round(ema20, 2), "ema50": round(ema50, 2), "price": round(price, 2), "passes": passes}


def compute_rsi(closes: List[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        raise ValueError(f"Need at least {period + 1} closes for RSI{period}, got {len(closes)}")
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(d, 0.0) for d in deltas]
    losses = [max(-d, 0.0) for d in deltas]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for gain, loss in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def _rsi_factor_score(rsi: float) -> float:
    """1.0 at the center of the strategy's 55-70 'sweet spot' band, tapering
    to 0 outside a wider window either side."""
    center, half_width = 62.5, 7.5
    if 55 <= rsi <= 70:
        return round(1.0 - 0.3 * (abs(rsi - center) / half_width), 4)
    if rsi < 55:
        return round(max(0.0, 0.7 * (rsi - 30) / 25), 4)
    return round(max(0.0, 0.7 * (100 - rsi) / 30), 4)


def compute_returns(closes: List[float]) -> Dict[str, float]:
    if len(closes) < 23:  # ~1 month of trading days, with headroom
        raise ValueError(f"Need at least 23 closes for return calculations, got {len(closes)}")

    def _return(days_back: int) -> float:
        return round((closes[-1] - closes[-1 - days_back]) / closes[-1 - days_back], 4)

    return {
        "return_1d": _return(1),
        "return_3d": _return(3),
        "return_7d": _return(7),
        "return_1m": _return(21),  # ~21 trading days per calendar month
    }


# --- Volume ------------------------------------------------------------

def compute_volume_increase(volumes: List[float], lookback: int = 10) -> float:
    if len(volumes) < lookback + 1:
        raise ValueError(f"Need at least {lookback + 1} volume points, got {len(volumes)}")
    recent_avg = sum(volumes[-(lookback + 1):-1]) / lookback
    today = volumes[-1]
    if recent_avg == 0 or recent_avg != recent_avg or today != today:  # guards NaN/zero
        return 0.0
    return round((today - recent_avg) / recent_avg, 4)


def compute_volume_confirmation(
    closes: List[float],
    volumes: List[float],
    deliveries: Optional[List[float]],
    lookback: int = 3,
) -> str:
    """"full" | "partial" | "none" — rising price + rising volume + rising
    delivery % over the recent window (delivery % is optional: bhavcopy
    only carries the latest day, so a multi-day delivery series may not be
    available; the confirmation still works off price+volume alone then)."""
    if len(closes) < lookback + 1 or len(volumes) < lookback + 1:
        return "none"
    price_rising = closes[-1] > closes[-1 - lookback]
    volume_rising = volumes[-1] > volumes[-1 - lookback]
    signals = [price_rising, volume_rising]
    if deliveries and len(deliveries) >= lookback + 1:
        signals.append(deliveries[-1] > deliveries[-1 - lookback])
    if all(signals):
        return "full"
    if any(signals):
        return "partial"
    return "none"


# --- Quality gates -----------------------------------------------------

def evaluate_quality_gates(
    fundamentals: Dict[str, Optional[float]],
    nse_flags: Dict[str, Optional[bool]],
    avg_daily_traded_value: Optional[float],
) -> Dict[str, object]:
    """
    fundamentals: {"market_cap_cr", "promoter_holding_pct", "debt_to_equity",
                    "earnings_growth_pct"} -> float | None
    nse_flags: {"asm", "gsm", "fo_ban"} -> bool | None (True = restricted/banned)
    avg_daily_traded_value: float | None, in Rs Crore

    A gate whose underlying value is None is recorded as "unknown", and
    "unknown" counts as not-passing for the overall gate — a filter that
    can't be verified is not the same as a filter that passed.
    """
    detail: Dict[str, str] = {}

    def _gate(name: str, value, passes_fn) -> None:
        detail[name] = UNKNOWN if value is None else ("pass" if passes_fn(value) else "fail")

    _gate("market_cap", fundamentals.get("market_cap_cr"), lambda v: v > 5000)
    _gate("avg_daily_traded_value", avg_daily_traded_value, lambda v: v > 10)
    _gate("asm", nse_flags.get("asm"), lambda v: v is False)
    _gate("gsm", nse_flags.get("gsm"), lambda v: v is False)
    _gate("fo_ban", nse_flags.get("fo_ban"), lambda v: v is False)
    _gate("promoter_holding", fundamentals.get("promoter_holding_pct"), lambda v: v > 40)
    _gate("debt_to_equity", fundamentals.get("debt_to_equity"), lambda v: v < 1.0)
    _gate("earnings_growth", fundamentals.get("earnings_growth_pct"), lambda v: v >= 0)

    passes_all = all(v == "pass" for v in detail.values())
    return {"detail": detail, "passes": passes_all}


# --- Risk management -----------------------------------------------------

def compute_risk_management(entry_price: float) -> Dict[str, float]:
    return {
        "stop_loss": round(entry_price * 0.95, 2),
        "target_low": round(entry_price * 1.10, 2),
        "target_high": round(entry_price * 1.15, 2),
    }


# --- Per-symbol assembly -----------------------------------------------

def build_symbol_metrics(
    closes: List[float],
    volumes: List[float],
    deliveries: Optional[List[float]],
    fundamentals: Dict[str, Optional[float]],
    nse_flags: Dict[str, Optional[bool]],
    avg_daily_traded_value: Optional[float],
) -> Dict[str, object]:
    """Everything computable for one symbol except the pool-relative
    composite score (see compute_momentum_scores, which needs every
    symbol's metrics at once to normalize against the pool)."""
    returns = compute_returns(closes)
    rsi = compute_rsi(closes)
    ema_trend = compute_ema_trend(closes)
    volume_increase = compute_volume_increase(volumes)
    volume_confirmation = compute_volume_confirmation(closes, volumes, deliveries)
    quality_gates = evaluate_quality_gates(fundamentals, nse_flags, avg_daily_traded_value)
    risk = compute_risk_management(closes[-1])
    delivery_pct = deliveries[-1] if deliveries else None

    return {
        "returns": returns,
        "rsi": rsi,
        "rsi_factor": _rsi_factor_score(rsi),
        "ema_trend": ema_trend,
        "volume_increase": volume_increase,
        "volume_confirmation": volume_confirmation,
        "delivery_pct": delivery_pct,
        "quality_gates": quality_gates,
        "risk": risk,
        "current_price": round(closes[-1], 2),
    }


# --- Pool-wide composite score -------------------------------------------

_SCORE_WEIGHTS = {
    "return_1m": 0.30,
    "return_7d": 0.25,
    "return_3d": 0.15,
    "return_1d": 0.10,
    "volume_increase": 0.10,
    "delivery_pct": 0.05,
    "rsi_factor": 0.05,
}


def _normalize_pool(values: Dict[str, float]) -> Dict[str, float]:
    """Min-max normalize a {symbol: raw_value} dict to [0, 1] across the pool."""
    if not values:
        return {}
    lo, hi = min(values.values()), max(values.values())
    if hi == lo:
        return {symbol: 0.5 for symbol in values}
    return {symbol: round((v - lo) / (hi - lo), 4) for symbol, v in values.items()}


def compute_momentum_scores(pool: Dict[str, Dict[str, object]]) -> Dict[str, Optional[float]]:
    """
    pool: {symbol: build_symbol_metrics(...) result}
    Returns {symbol: composite_score} (0-1 range), normalized against the
    pool's own return/volume/delivery distribution for this run. A symbol
    missing some factors (e.g. no delivery_pct) still gets a score,
    renormalized over the factors it does have, rather than being
    penalized to zero or excluded outright — matches the rest of this
    app's graceful-degradation philosophy.
    """
    factor_sources = {
        "return_1m": lambda m: m["returns"]["return_1m"],
        "return_7d": lambda m: m["returns"]["return_7d"],
        "return_3d": lambda m: m["returns"]["return_3d"],
        "return_1d": lambda m: m["returns"]["return_1d"],
        "volume_increase": lambda m: m["volume_increase"],
        "delivery_pct": lambda m: m["delivery_pct"],
    }

    normalized_factors: Dict[str, Dict[str, float]] = {symbol: {} for symbol in pool}

    for factor, extractor in factor_sources.items():
        raw = {}
        for symbol, metrics in pool.items():
            value = extractor(metrics)
            if value is not None:
                raw[symbol] = value
        for symbol, score in _normalize_pool(raw).items():
            normalized_factors[symbol][factor] = score

    for symbol, metrics in pool.items():
        normalized_factors[symbol]["rsi_factor"] = metrics["rsi_factor"]

    scores: Dict[str, Optional[float]] = {}
    for symbol, factors in normalized_factors.items():
        weighted_sum = 0.0
        weight_used = 0.0
        for factor, weight in _SCORE_WEIGHTS.items():
            if factor in factors:
                weighted_sum += factors[factor] * weight
                weight_used += weight
        scores[symbol] = round(weighted_sum / weight_used, 4) if weight_used > 0 else None
    return scores
