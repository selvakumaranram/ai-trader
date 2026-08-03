import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import recommender
import backtest


def _rising_closes(n=60, start=100.0, step=0.5):
    return [start + i * step for i in range(n)]


def test_rankings_are_sorted_and_sized():
    rows = recommender.build_rankings()
    assert rows
    assert rows[0]["score"] >= rows[-1]["score"]
    assert all("suggested" in row for row in rows)


def test_backtest_run_returns_expected_shapes():
    prices = _rising_closes(60)

    value, buy_hold, periods = backtest.run_backtest(prices, 5, 15)

    assert isinstance(value, float)
    assert isinstance(buy_hold, float)
    assert periods == 60


def test_backtest_main_runs_without_syntax_error(monkeypatch, capsys):
    fake_prices = _rising_closes(60)
    monkeypatch.setattr(
        backtest.prices_source, "fetch_price_history", lambda symbol, period="1y": fake_prices
    )
    monkeypatch.setattr(sys, "argv", ["backtest.py", "TEST", "5", "15"])

    backtest.main()

    captured = capsys.readouterr()
    assert "Backtest for TEST" in captured.out
