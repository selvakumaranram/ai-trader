import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vercel-demo"))

from momentum_screen import (
    compute_ema_trend,
    compute_returns,
    compute_risk_management,
    compute_rsi,
    compute_volume_confirmation,
    compute_volume_increase,
    evaluate_quality_gates,
    compute_momentum_scores,
    build_symbol_metrics,
)


def _rising_closes(n, start=100.0, step=1.0):
    return [start + i * step for i in range(n)]


def test_compute_returns_basic():
    closes = _rising_closes(30)  # closes[i] = 100 + i
    result = compute_returns(closes)
    assert result["return_1d"] == round((closes[-1] - closes[-2]) / closes[-2], 4)
    assert result["return_3d"] == round((closes[-1] - closes[-4]) / closes[-4], 4)
    assert result["return_7d"] == round((closes[-1] - closes[-8]) / closes[-8], 4)
    assert result["return_1m"] == round((closes[-1] - closes[-22]) / closes[-22], 4)


def test_compute_returns_too_few_closes_raises():
    try:
        compute_returns(_rising_closes(10))
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_compute_rsi_all_gains_is_100():
    closes = _rising_closes(20)  # strictly increasing -> no losses at all
    assert compute_rsi(closes) == 100.0


def test_compute_rsi_all_losses_is_0():
    closes = list(reversed(_rising_closes(20)))  # strictly decreasing
    assert compute_rsi(closes) == 0.0


def test_compute_ema_trend_uptrend_passes():
    closes = _rising_closes(60)  # steadily rising -> price > EMA20 > EMA50
    result = compute_ema_trend(closes)
    assert result["passes"] is True
    assert result["price"] > result["ema20"] > result["ema50"]


def test_compute_ema_trend_downtrend_fails():
    closes = list(reversed(_rising_closes(60)))
    result = compute_ema_trend(closes)
    assert result["passes"] is False


def test_compute_volume_increase_rising():
    volumes = [100.0] * 10 + [200.0]  # today is double the trailing average
    assert compute_volume_increase(volumes) == 1.0


def test_compute_volume_confirmation_full():
    closes = [100.0, 101.0, 102.0, 103.0]
    volumes = [1000.0, 1000.0, 1000.0, 2000.0]
    deliveries = [50.0, 50.0, 50.0, 60.0]
    assert compute_volume_confirmation(closes, volumes, deliveries) == "full"


def test_compute_volume_confirmation_none():
    closes = [103.0, 102.0, 101.0, 100.0]
    volumes = [2000.0, 1500.0, 1200.0, 1000.0]
    assert compute_volume_confirmation(closes, volumes, None) == "none"


def test_evaluate_quality_gates_all_pass():
    fundamentals = {
        "market_cap_cr": 6000.0,
        "promoter_holding_pct": 50.0,
        "debt_to_equity": 0.5,
        "earnings_growth_pct": 10.0,
    }
    nse_flags = {"asm": False, "gsm": False, "fo_ban": False}
    result = evaluate_quality_gates(fundamentals, nse_flags, avg_daily_traded_value=15.0)
    assert result["passes"] is True
    assert all(v == "pass" for v in result["detail"].values())


def test_evaluate_quality_gates_unknown_excludes():
    fundamentals = {
        "market_cap_cr": 6000.0,
        "promoter_holding_pct": None,  # missing data
        "debt_to_equity": 0.5,
        "earnings_growth_pct": 10.0,
    }
    nse_flags = {"asm": False, "gsm": False, "fo_ban": False}
    result = evaluate_quality_gates(fundamentals, nse_flags, avg_daily_traded_value=15.0)
    assert result["passes"] is False
    assert result["detail"]["promoter_holding"] == "unknown"


def test_evaluate_quality_gates_fo_ban_fails():
    fundamentals = {
        "market_cap_cr": 6000.0,
        "promoter_holding_pct": 50.0,
        "debt_to_equity": 0.5,
        "earnings_growth_pct": 10.0,
    }
    nse_flags = {"asm": False, "gsm": False, "fo_ban": True}  # banned
    result = evaluate_quality_gates(fundamentals, nse_flags, avg_daily_traded_value=15.0)
    assert result["passes"] is False
    assert result["detail"]["fo_ban"] == "fail"


def test_compute_risk_management():
    result = compute_risk_management(100.0)
    assert result == {"stop_loss": 95.0, "target_low": 110.0, "target_high": 115.0}


def test_compute_momentum_scores_ranks_stronger_symbol_higher():
    strong_closes = _rising_closes(30, start=100.0, step=2.0)
    weak_closes = _rising_closes(30, start=100.0, step=0.1)
    volumes = [1000.0] * 30

    pool = {
        "STRONG": build_symbol_metrics(strong_closes, volumes, None, {}, {}, None),
        "WEAK": build_symbol_metrics(weak_closes, volumes, None, {}, {}, None),
    }
    scores = compute_momentum_scores(pool)
    assert scores["STRONG"] > scores["WEAK"]


def test_compute_momentum_scores_missing_factor_still_scores():
    closes = _rising_closes(30)
    volumes = [1000.0] * 30
    metrics = build_symbol_metrics(closes, volumes, None, {}, {}, None)
    # delivery_pct is None (no deliveries passed) — must not crash or
    # produce None for the whole score.
    assert metrics["delivery_pct"] is None
    scores = compute_momentum_scores({"ONLY": metrics})
    assert scores["ONLY"] is not None


if __name__ == "__main__":
    import sys as _sys
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except AssertionError as exc:
            failures += 1
            print(f"FAIL {test.__name__}: {exc}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    _sys.exit(1 if failures else 0)
