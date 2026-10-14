import sys

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


def test_rss_feeds_are_canonical_not_overridden():
    assert recommender.RSS_FEEDS == ["https://finance.yahoo.com/news/rssindex"]


def test_derive_fallback_keyword_strips_exchange_suffixes():
    assert recommender.derive_fallback_keyword("RELIANCE.NS") == "reliance"
    assert recommender.derive_fallback_keyword("btc-usd") == "btc"


def test_build_asset_payload_scores_every_style():
    asset = {"symbol": "TEST", "type": "equity_in", "keywords": ["test"]}
    payload = recommender.build_asset_payload(asset, _rising_closes(), [])
    assert set(payload["scores"]) == {"intraday", "short_term", "swing"}
    assert payload["sentiment"] == 0.0


def test_write_dashboard_writes_escaped_html(tmp_path):
    rows = [{"symbol": "<b>X</b>", "type": "equity_in", "score": 0.2, "suggested": 1000, "action": "Research LONG"}]
    path = tmp_path / "dashboard.html"

    recommender.write_dashboard(rows, str(path))

    html = path.read_text(encoding="utf-8")
    assert "&lt;b&gt;X&lt;/b&gt;" in html
    assert "<b>X</b>" not in html
