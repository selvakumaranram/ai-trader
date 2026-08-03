import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

import backtest
import recommender


def _rising_closes(n=60, start=100.0, step=0.5):
    return [start + i * step for i in range(n)]


def test_compute_momentum_positive_for_uptrend():
    momentum = recommender._compute_momentum(_rising_closes(), "TEST")
    assert momentum == pytest.approx(0.07231912725528986, abs=1e-9)


def test_compute_momentum_raises_on_insufficient_history():
    with pytest.raises(ValueError):
        recommender._compute_momentum([100.0] * 10, "TEST")


def test_build_rankings_are_sorted_and_sized(monkeypatch):
    fake_headlines = [{"title": "great ai rally", "summary": "chip demand strong"}]

    monkeypatch.setattr(
        recommender.prices_source,
        "fetch_price_history",
        lambda yf_symbol, period="6mo": _rising_closes(),
    )
    monkeypatch.setattr(recommender.news_source, "fetch_headlines", lambda feeds: fake_headlines)

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
