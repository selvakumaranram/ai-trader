import datetime

import pytest

from holdings_logic import compute_holding_period, compute_sell_signal


def _scores(short_term, swing):
    return {"short_term": {"score": short_term}, "swing": {"score": swing}}


@pytest.mark.parametrize(
    "short_term, swing, action",
    [
        (-0.1, -0.1, "Consider selling"),
        (-0.1, 0.2, "Short-term weakness"),
        (0.2, -0.1, "Long-term weakness"),
        (0.2, 0.2, "Hold"),
        (0.0, 0.0, "Hold"),
    ],
)
def test_sell_signal_branches(short_term, swing, action):
    assert compute_sell_signal(_scores(short_term, swing))["action"] == action


def test_holding_period_indian_equity_before_ltcg():
    buy = datetime.date.today() - datetime.timedelta(days=100)
    result = compute_holding_period(buy, "INFY.NS")
    assert result == {"days_held": 100, "ltcg_applicable": True, "ltcg_eligible": False, "days_to_ltcg": 265}


def test_holding_period_indian_equity_after_ltcg():
    buy = datetime.date.today() - datetime.timedelta(days=400)
    result = compute_holding_period(buy, "TCS.BO")
    assert result["ltcg_eligible"] is True
    assert result["days_to_ltcg"] == 0


def test_holding_period_non_indian_symbol_has_no_ltcg():
    buy = datetime.date.today() - datetime.timedelta(days=10)
    result = compute_holding_period(buy, "AAPL")
    assert result == {"days_held": 10, "ltcg_applicable": False, "ltcg_eligible": None, "days_to_ltcg": None}
