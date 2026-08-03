import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import recommender
import backtest


def test_rankings_are_sorted_and_sized():
    rows = recommender.build_rankings()
    assert rows
    assert rows[0]["score"] >= rows[-1]["score"]
    assert all("suggested" in row for row in rows)


def test_backtest_returns_expected_shapes():
    prices = backtest.build_price_series("TEST", periods=60)
    value, buy_hold, periods = backtest.run_backtest(prices, 5, 15)
    assert isinstance(value, float)
    assert isinstance(buy_hold, float)
    assert periods == 60
