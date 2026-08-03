# Phase 1 Real Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace QuantDesk's fake hash-based scoring and broken/synthetic backtester with real price momentum (yfinance), real news sentiment (RSS + VADER), and a working SMA-crossover backtest against real historical prices.

**Architecture:** A new `sources/` package (`prices.py`, `news.py`) owns all external data fetching and raises `RuntimeError` on failure — no fallback, no caching. `recommender.py` and `backtest.py` import the `sources` submodules (not individual functions) so tests can monkeypatch fetch calls without network access, while production code path always hits the real APIs.

**Tech Stack:** Python 3.10+ (repo currently runs 3.14.6), `yfinance` (prices), `feedparser` (RSS), `vaderSentiment` (sentiment), `pytest` (already installed, not a new dependency).

## Global Constraints

- No offline/cached fallback anywhere: a price or news fetch failure raises `RuntimeError` and aborts the run. Never substitute stale, cached, or fabricated data.
- `yfinance`, `feedparser`, `vaderSentiment` are hard (uncommented) requirements in `requirements.txt`. `pandas`/`numpy`/`matplotlib` stay commented — out of scope (Phase 2).
- Momentum formula (exact): `momentum = clip(0.5 * return_10d + 0.5 * (last_close / sma_50 - 1), -1, 1)`, where `return_10d = (closes[-1] - closes[-11]) / closes[-11]` and `sma_50 = mean(closes[-50:])`. Requires at least 51 closes; raise `ValueError` otherwise.
- Sentiment: mean VADER `compound` score (range `[-1, 1]`) over headlines matched to an asset's `keywords`; `0.0` (neutral) if no headlines matched — not an error.
- `SCORE_THRESHOLD = 0.15` replaces the old hardcoded `0.55` threshold for `"Research LONG"`.
- Tests must never touch the network. Monkeypatch `sources.prices.fetch_price_history` / `sources.news.fetch_headlines` (etc.) via the **module object** (`recommender.prices_source`, `backtest.prices_source`, `recommender.news_source`) — never re-add a fake/deterministic scorer.
- Out of scope: Phase 2 (strategy library, paper trading, execution layer, risk engine), VectorBT/PyBroker migration, any `data/` caching directory.
- Spec: `docs/superpowers/specs/2026-08-03-phase1-real-data-design.md`.

---

### Task 1: `sources/prices.py` — real price history fetch

**Files:**
- Create: `sources/__init__.py`
- Create: `sources/prices.py`
- Modify: `requirements.txt`
- Test: `tests/test_prices.py`

**Interfaces:**
- Produces: `sources.prices.fetch_price_history(yf_symbol: str, period: str = "6mo") -> List[float]` — daily close prices, oldest to newest. Raises `RuntimeError` if the fetch fails or returns no data. Consumed by Task 3 (`backtest.py`) and Task 4 (`recommender.py`).

- [ ] **Step 1: Create the `sources` package**

Create `sources/__init__.py` with empty content (just makes `sources` an importable package).

- [ ] **Step 2: Uncomment `yfinance` in requirements.txt**

In `requirements.txt`, change:
```
# yfinance>=0.2
```
to:
```
yfinance>=0.2
```

- [ ] **Step 3: Install the new dependency**

Run: `pip install -r requirements.txt`
Expected: `yfinance` (and its transitive deps, including `pandas`) installs successfully. `feedparser` is already present; the still-commented `vaderSentiment` line is skipped by pip.

- [ ] **Step 4: Write the failing test file**

Create `tests/test_prices.py`:

```python
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from sources import prices


class _FakeSeries:
    def __init__(self, values):
        self._values = values

    def tolist(self):
        return self._values


class _FakeFrame:
    def __init__(self, values):
        self.empty = len(values) == 0
        self._close = _FakeSeries(values)

    def __getitem__(self, key):
        assert key == "Close"
        return self._close


def test_fetch_price_history_returns_close_values(monkeypatch):
    monkeypatch.setattr(prices.yf, "download", lambda *a, **k: _FakeFrame([100.0, 101.5, 99.25]))

    result = prices.fetch_price_history("TEST", period="6mo")

    assert result == [100.0, 101.5, 99.25]


def test_fetch_price_history_raises_on_empty_data(monkeypatch):
    monkeypatch.setattr(prices.yf, "download", lambda *a, **k: _FakeFrame([]))

    with pytest.raises(RuntimeError):
        prices.fetch_price_history("TEST")


def test_fetch_price_history_raises_on_download_exception(monkeypatch):
    def _raise(*a, **k):
        raise ConnectionError("network down")

    monkeypatch.setattr(prices.yf, "download", _raise)

    with pytest.raises(RuntimeError):
        prices.fetch_price_history("TEST")
```

- [ ] **Step 5: Run test to verify it fails**

Run: `python -m pytest tests/test_prices.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sources.prices'` (or similar import error) — `sources/prices.py` doesn't exist yet.

- [ ] **Step 6: Write the implementation**

Create `sources/prices.py`:

```python
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

    closes = data["Close"]
    if hasattr(closes, "columns"):
        # Some yfinance versions return a single-column DataFrame here
        # instead of a Series even for one symbol — flatten it.
        closes = closes.iloc[:, 0]
    return [float(value) for value in closes.tolist()]
```

- [ ] **Step 7: Run test to verify it passes**

Run: `python -m pytest tests/test_prices.py -v`
Expected: 3 passed.

- [ ] **Step 8: Commit**

```bash
git add sources/__init__.py sources/prices.py requirements.txt tests/test_prices.py
git commit -m "Add sources/prices.py for real yfinance price history"
```

---

### Task 2: `sources/news.py` — real headline fetch, matching, sentiment

**Files:**
- Create: `sources/news.py`
- Modify: `requirements.txt`
- Test: `tests/test_news.py`

**Interfaces:**
- Produces: `sources.news.fetch_headlines(feed_urls: List[str]) -> List[Dict[str, str]]` (each dict has `title`, `summary`); raises `RuntimeError` only if zero headlines come back across all feeds.
- Produces: `sources.news.match_headlines(headlines: List[Dict[str, str]], keywords: List[str]) -> List[Dict[str, str]]` — case-insensitive substring match.
- Produces: `sources.news.score_sentiment(headlines: List[Dict[str, str]]) -> float` — mean VADER compound score, `0.0` for an empty list.
- All three consumed by Task 4 (`recommender.py`).

- [ ] **Step 1: Uncomment `feedparser` and `vaderSentiment`, tidy the file**

Rewrite `requirements.txt` to:

```
# Phase 1 hard requirements — real price data, RSS parsing, sentiment scoring
yfinance>=0.2
feedparser>=6.0
vaderSentiment>=3.7

# Optional dependencies for later phases (Phase 2 backtesting upgrade)
# pandas>=2.0
# numpy>=1.26
# matplotlib>=3.8
```

- [ ] **Step 2: Install the new dependency**

Run: `pip install -r requirements.txt`
Expected: `vaderSentiment` installs successfully (`feedparser`/`yfinance` already present from Task 1).

- [ ] **Step 3: Write the failing test file**

Create `tests/test_news.py`:

```python
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from sources import news


class _FakeParsed:
    def __init__(self, entries, bozo=False):
        self.entries = entries
        self.bozo = bozo


def test_fetch_headlines_collects_entries_across_feeds(monkeypatch):
    def fake_parse(url):
        if url == "feed-a":
            return _FakeParsed([{"title": "A rises", "summary": "up"}])
        return _FakeParsed([{"title": "B falls", "summary": "down"}])

    monkeypatch.setattr(news.feedparser, "parse", fake_parse)

    result = news.fetch_headlines(["feed-a", "feed-b"])

    assert len(result) == 2
    assert result[0]["title"] == "A rises"
    assert result[1]["title"] == "B falls"


def test_fetch_headlines_tolerates_partial_feed_failure(monkeypatch):
    def fake_parse(url):
        if url == "feed-a":
            raise ConnectionError("feed-a down")
        return _FakeParsed([{"title": "B falls", "summary": "down"}])

    monkeypatch.setattr(news.feedparser, "parse", fake_parse)

    result = news.fetch_headlines(["feed-a", "feed-b"])

    assert len(result) == 1
    assert result[0]["title"] == "B falls"


def test_fetch_headlines_raises_when_all_feeds_fail(monkeypatch):
    monkeypatch.setattr(news.feedparser, "parse", lambda url: _FakeParsed([], bozo=True))

    with pytest.raises(RuntimeError):
        news.fetch_headlines(["feed-a"])


def test_match_headlines_filters_by_keyword():
    headlines = [
        {"title": "Bitcoin rallies", "summary": "ETF inflows"},
        {"title": "Coffee prices dip", "summary": "harvest season"},
    ]

    matched = news.match_headlines(headlines, ["bitcoin", "etf"])

    assert matched == [headlines[0]]


def test_score_sentiment_returns_zero_for_no_headlines():
    assert news.score_sentiment([]) == 0.0


def test_score_sentiment_is_positive_for_positive_text():
    headlines = [{"title": "Great news, huge rally, best day ever", "summary": ""}]

    assert news.score_sentiment(headlines) > 0


def test_score_sentiment_is_negative_for_negative_text():
    headlines = [{"title": "Terrible crash, massive losses, worst day ever", "summary": ""}]

    assert news.score_sentiment(headlines) < 0
```

- [ ] **Step 4: Run test to verify it fails**

Run: `python -m pytest tests/test_news.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sources.news'`.

- [ ] **Step 5: Write the implementation**

Create `sources/news.py`:

```python
from __future__ import annotations

from typing import Dict, List

import feedparser
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_analyzer = SentimentIntensityAnalyzer()


def fetch_headlines(feed_urls: List[str]) -> List[Dict[str, str]]:
    headlines: List[Dict[str, str]] = []
    for url in feed_urls:
        try:
            parsed = feedparser.parse(url)
        except Exception:
            continue
        if parsed.bozo and not parsed.entries:
            continue
        for entry in parsed.entries:
            headlines.append({
                "title": entry.get("title", ""),
                "summary": entry.get("summary", ""),
            })

    if not headlines:
        raise RuntimeError(
            f"Failed to fetch any headlines from {len(feed_urls)} feed(s): {feed_urls}"
        )
    return headlines


def match_headlines(headlines: List[Dict[str, str]], keywords: List[str]) -> List[Dict[str, str]]:
    lowered_keywords = [kw.lower() for kw in keywords]
    matched = []
    for headline in headlines:
        text = f"{headline.get('title', '')} {headline.get('summary', '')}".lower()
        if any(kw in text for kw in lowered_keywords):
            matched.append(headline)
    return matched


def score_sentiment(headlines: List[Dict[str, str]]) -> float:
    if not headlines:
        return 0.0
    scores = []
    for headline in headlines:
        text = f"{headline.get('title', '')} {headline.get('summary', '')}"
        scores.append(_analyzer.polarity_scores(text)["compound"])
    return sum(scores) / len(scores)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest tests/test_news.py -v`
Expected: 7 passed.

- [ ] **Step 7: Commit**

```bash
git add sources/news.py requirements.txt tests/test_news.py
git commit -m "Add sources/news.py for real RSS headlines and VADER sentiment"
```

---

### Task 3: Fix `backtest.py` syntax bug and use real prices

`backtest.py` is fixed before `recommender.py` because `tests/test_core.py`
imports both modules unconditionally at the top of the file. As long as
`backtest.py` has its current `SyntaxError`, no test in that file can even
be collected — so the backtest fix has to land first, or every later step
that touches this shared test file would fail on an unrelated collection
error instead of the thing it's actually testing.

**Files:**
- Modify: `backtest.py` (full rewrite)
- Modify: `tests/test_core.py`

**Interfaces:**
- Consumes: `sources.prices.fetch_price_history(symbol, period="1y") -> List[float]` (Task 1).
- Produces: `backtest.run_backtest(prices, short_window, long_window)` (signature unchanged), `backtest.sma(values, window)` (unchanged), `backtest.main()`. Module-level `backtest.prices_source` is the patch point for tests. `backtest.build_price_series` is removed (no longer needed — real data replaces the synthetic generator).

- [ ] **Step 1: Update the backtest tests in `tests/test_core.py`**

Replace the full contents of `tests/test_core.py` with:

```python
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
```

`test_rankings_are_sorted_and_sized` is untouched here and still exercises
today's fake `recommender.build_rankings()` — that's expected and correct,
since `recommender.py` isn't rewritten until Task 4. It keeps passing
throughout this task because it doesn't depend on `backtest.py` at all.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_core.py -v`
Expected: FAIL with a collection error — `backtest.py` currently has a
`SyntaxError` at import time (line 31: a stray `\n` typed as literal text
into the source), so `import backtest` at the top of `tests/test_core.py`
fails before any test runs. This is the exact bug this task fixes.

- [ ] **Step 3: Rewrite `backtest.py`**

Replace the full contents of `backtest.py` with:

```python
from __future__ import annotations

import math
import sys
from typing import List, Tuple

from sources import prices as prices_source


def sma(values: List[float], window: int) -> List[float]:
    result: List[float] = []
    for index in range(len(values)):
        if index < window - 1:
            result.append(float("nan"))
        else:
            window_values = values[index - window + 1:index + 1]
            result.append(sum(window_values) / window)
    return result


def run_backtest(prices: List[float], short_window: int, long_window: int) -> Tuple[float, float, int]:
    short_sma = sma(prices, short_window)
    long_sma = sma(prices, long_window)
    cash = 10000.0
    shares = 0
    entry_price = prices[0]

    for index in range(1, len(prices)):
        short_value = short_sma[index]
        long_value = long_sma[index]
        if math.isnan(short_value) or math.isnan(long_value):
            continue
        if short_value > long_value and shares == 0:
            shares = cash / prices[index]
            cash = 0.0
        elif short_value < long_value and shares > 0:
            cash = shares * prices[index]
            shares = 0

    if shares > 0:
        cash = shares * prices[-1]

    buy_hold = prices[-1] / prices[0] * 10000.0
    return round(cash, 2), round(buy_hold, 2), len(prices)


def main() -> None:
    symbol = sys.argv[1] if len(sys.argv) > 1 else "RELIANCE.NS"
    short_window = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    long_window = int(sys.argv[3]) if len(sys.argv) > 3 else 50

    prices = prices_source.fetch_price_history(symbol, period="1y")
    strategy_value, buy_hold_value, periods = run_backtest(prices, short_window, long_window)

    print(f"Backtest for {symbol} | periods={periods} | short={short_window} | long={long_window}")
    print(f"Strategy final value: Rs {strategy_value:,.2f}")
    print(f"Buy-and-hold value:  Rs {buy_hold_value:,.2f}")
    if strategy_value > buy_hold_value:
        print("Outcome: strategy outperformed buy-and-hold for this symbol.")
    else:
        print("Outcome: strategy underperformed buy-and-hold for this symbol.")


if __name__ == "__main__":
    main()
```

Note: `build_price_series` (the synthetic sine-wave generator) is removed entirely — `main()` now calls `prices_source.fetch_price_history` directly. The `entry_price` variable is unused, same as in the original file; left as-is since it's unrelated to this task's scope. The outcome message wording changed from "on this synthetic sample" to "for this symbol" since the data is now real.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_core.py -v`
Expected: 3 passed (`test_rankings_are_sorted_and_sized` against the still-fake `recommender.py`, plus the two new backtest tests).

- [ ] **Step 5: Run the full test suite**

Run: `python -m pytest tests/ -v`
Expected: all tests pass (13 total: 3 in `test_prices.py`, 7 in `test_news.py`, 3 in `test_core.py`).

- [ ] **Step 6: Commit**

```bash
git add backtest.py tests/test_core.py
git commit -m "Fix backtest.py syntax bug and backtest against real historical prices"
```

---

### Task 4: Rewrite `recommender.py` to use real momentum and sentiment

**Files:**
- Modify: `recommender.py` (full rewrite)
- Modify: `tests/test_core.py`

**Interfaces:**
- Consumes: `sources.prices.fetch_price_history(yf_symbol, period="6mo") -> List[float]` (Task 1), `sources.news.fetch_headlines(feed_urls) -> List[Dict]`, `match_headlines(headlines, keywords) -> List[Dict]`, `score_sentiment(headlines) -> float` (Task 2).
- Produces: `recommender._compute_momentum(closes: List[float]) -> float` (raises `ValueError` if `len(closes) < 51`); `recommender.build_rankings() -> List[Dict[str, object]]` (unchanged external shape: each row has `symbol`, `type`, `momentum`, `sentiment`, `score`, `action`, `suggested`). Module-level `recommender.prices_source` / `recommender.news_source` are the patch points for tests.

- [ ] **Step 1: Update the ranking/momentum tests in `tests/test_core.py`**

Replace the full contents of `tests/test_core.py` with:

```python
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

import backtest
import recommender


def _rising_closes(n=60, start=100.0, step=0.5):
    return [start + i * step for i in range(n)]


def test_compute_momentum_positive_for_uptrend():
    momentum = recommender._compute_momentum(_rising_closes())
    assert momentum > 0


def test_compute_momentum_raises_on_insufficient_history():
    with pytest.raises(ValueError):
        recommender._compute_momentum([100.0] * 10)


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
```

The two `backtest` tests are carried over unchanged from Task 3 and keep
passing throughout (they don't touch `recommender.py`).

- [ ] **Step 2: Run test to verify the new/changed assertions fail**

Run: `python -m pytest tests/test_core.py -v`
Expected: FAIL — `test_compute_momentum_positive_for_uptrend`, `test_compute_momentum_raises_on_insufficient_history`, and `test_build_rankings_are_sorted_and_sized` all error with `AttributeError` (`recommender._compute_momentum`, `recommender.prices_source`, `recommender.news_source` don't exist yet). The two backtest tests still pass — `backtest.py` was already fixed in Task 3, so it's unaffected here.

- [ ] **Step 3: Rewrite `recommender.py`**

Replace the full contents of `recommender.py` with:

```python
from __future__ import annotations

import os
from typing import Dict, List

from sources import news as news_source
from sources import prices as prices_source

UNIVERSE = [
    {"symbol": "BTC", "yf_symbol": "BTC-USD", "type": "crypto", "keywords": ["bitcoin", "etf", "halving", "institutional"]},
    {"symbol": "ETH", "yf_symbol": "ETH-USD", "type": "crypto", "keywords": ["ethereum", "layer2", "staking", "smart contract"]},
    {"symbol": "NVDA", "yf_symbol": "NVDA", "type": "equity_us", "keywords": ["ai", "chip", "data center", "semiconductor"]},
    {"symbol": "MSFT", "yf_symbol": "MSFT", "type": "equity_us", "keywords": ["cloud", "enterprise", "ai", "software"]},
    {"symbol": "RELIANCE", "yf_symbol": "RELIANCE.NS", "type": "equity_in", "keywords": ["retail", "energy", "telecom", "consumer"]},
    {"symbol": "INFY", "yf_symbol": "INFY.NS", "type": "equity_in", "keywords": ["it", "software", "outsourcing", "digital"]},
    {"symbol": "TCS", "yf_symbol": "TCS.NS", "type": "equity_in", "keywords": ["it", "services", "cloud", "enterprise"]},
    {"symbol": "HDFC", "yf_symbol": "HDFCBANK.NS", "type": "equity_in", "keywords": ["bank", "finance", "credit", "lending"]},
]

RSS_FEEDS = [
    "https://feeds.feedburner.com/cointelegraph",
    "https://feeds.feedburner.com/techcrunch/startups",
    "https://www.moneycontrol.com/rss/marketnews.xml",
]

STYLE = "short_term"
CAPITAL = 25000
MAX_DEPLOY_PCT = 0.60
MAX_ALLOC_PER_IDEA = 0.20
MIN_TICKET = 500
SCORE_THRESHOLD = 0.15

STYLE_WEIGHTS = {
    "intraday": {"momentum": 0.8, "sentiment": 0.2},
    "short_term": {"momentum": 0.7, "sentiment": 0.3},
    "swing": {"momentum": 0.55, "sentiment": 0.45},
}


def _compute_momentum(closes: List[float]) -> float:
    if len(closes) < 51:
        raise ValueError(f"Need at least 51 closes to compute momentum, got {len(closes)}")
    return_10d = (closes[-1] - closes[-11]) / closes[-11]
    sma_50 = sum(closes[-50:]) / 50
    trend = (closes[-1] / sma_50) - 1
    momentum = 0.5 * return_10d + 0.5 * trend
    return max(-1.0, min(1.0, momentum))


def _score_asset(
    asset: Dict[str, object],
    style: str,
    closes: List[float],
    matched_headlines: List[Dict[str, str]],
) -> Dict[str, object]:
    momentum = _compute_momentum(closes)
    sentiment = news_source.score_sentiment(matched_headlines)
    style_mix = STYLE_WEIGHTS[style]
    score = round(momentum * style_mix["momentum"] + sentiment * style_mix["sentiment"], 3)

    action = "Research LONG" if score >= SCORE_THRESHOLD else "Watchlist"
    return {
        "symbol": asset["symbol"],
        "type": asset["type"],
        "momentum": round(momentum, 3),
        "sentiment": round(sentiment, 3),
        "score": score,
        "action": action,
    }


def _position_sizing(scores: List[Dict[str, object]]) -> List[Dict[str, object]]:
    positive_scores = [entry["score"] for entry in scores if entry["score"] > 0]
    total_positive = sum(positive_scores) if positive_scores else 1.0
    deployable_capital = CAPITAL * MAX_DEPLOY_PCT
    max_per_idea = CAPITAL * MAX_ALLOC_PER_IDEA

    sized: List[Dict[str, object]] = []
    for entry in scores:
        if entry["score"] <= 0:
            allocation = 0
        else:
            normalized_weight = entry["score"] / total_positive
            raw_allocation = deployable_capital * normalized_weight
            allocation = min(max_per_idea, raw_allocation)
            if allocation < MIN_TICKET:
                allocation = 0
        entry["suggested"] = round(allocation, 0)
        sized.append(entry)
    return sized


def build_rankings() -> List[Dict[str, object]]:
    headlines = news_source.fetch_headlines(RSS_FEEDS)
    scored = []
    for asset in UNIVERSE:
        closes = prices_source.fetch_price_history(asset["yf_symbol"])
        matched = news_source.match_headlines(headlines, asset["keywords"])
        scored.append(_score_asset(asset, STYLE, closes, matched))
    ranked = sorted(scored, key=lambda item: item["score"], reverse=True)
    return _position_sizing(ranked)


def format_table(rows: List[Dict[str, object]]) -> str:
    headers = ["RANK", "ASSET", "TYPE", "SCORE", "SUGGEST", "ACTION"]
    body = [
        f"{headers[0]:<4} {headers[1]:<10} {headers[2]:<12} {headers[3]:<6} {headers[4]:<8} {headers[5]}"
    ]
    for index, row in enumerate(rows, start=1):
        body.append(
            f"{index:<4} {str(row['symbol']):<10} {str(row['type']):<12} {row['score']:<6.3f} Rs {row['suggested']:>7,.0f} {row['action']}"
        )
    return "\n".join(body)


def write_dashboard(rows: List[Dict[str, object]], path: str = "dashboard.html") -> None:
    items = []
    for row in rows:
        items.append(
            f"<li><strong>{row['symbol']}</strong> — {row['type']} — score {row['score']:.3f} — suggested Rs {int(row['suggested']):,} — {row['action']}</li>"
        )

    html = f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>QuantDesk Research Dashboard</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem; background: #07111f; color: #e7eefc; }}
    .card {{ background: #10233c; border: 1px solid #2f4b72; border-radius: 12px; padding: 1.5rem; max-width: 840px; }}
    ul {{ line-height: 1.7; }}
    .meta {{ color: #89a6c9; margin-bottom: 1rem; }}
  </style>
</head>
<body>
  <div class=\"card\">
    <h1>QuantDesk Research Dashboard</h1>
    <p class=\"meta\">Capital: Rs {CAPITAL:,.0f} • Style: {STYLE} • Feeds: {len(RSS_FEEDS)}</p>
    <ul>
      {''.join(items)}
    </ul>
  </div>
</body>
</html>
"""
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(html)


def main() -> None:
    rows = build_rankings()
    print("QuantDesk — Research & Recommendation")
    print(f"Style: {STYLE} | Capital: Rs {CAPITAL:,.0f} | Max deploy: {MAX_DEPLOY_PCT * 100:.0f}%")
    print(format_table(rows))
    deployed = sum(row["suggested"] for row in rows if row["suggested"] > 0)
    print(f"\nSuggested deployed: Rs {deployed:,.0f} | Cash buffer: Rs {CAPITAL - deployed:,.0f}")

    output_path = os.path.join(os.path.dirname(__file__) or ".", "dashboard.html")
    write_dashboard(rows, output_path)
    print(f"\nDashboard written to {output_path}")


if __name__ == "__main__":
    main()
```

Note what was intentionally removed vs. the old file: `_stable_score`, `_estimate_momentum`, `_estimate_sentiment` (the fake scorer), the unused `WEIGHTS` dict (dead code — `_score_asset` always overwrote it with `STYLE_WEIGHTS[style]` since `STYLE` is always a valid key), and the unused `math`/`textwrap` imports.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_core.py -v`
Expected: 5 passed.

- [ ] **Step 5: Run the full test suite**

Run: `python -m pytest tests/ -v`
Expected: all tests pass (15 total: 3 in `test_prices.py`, 7 in `test_news.py`, 5 in `test_core.py`).

- [ ] **Step 6: Commit**

```bash
git add recommender.py tests/test_core.py
git commit -m "Replace recommender.py fake scoring with real momentum and sentiment"
```

---

### Task 5: Update README.md for the real-data behavior

**Files:**
- Modify: `README.md`

**Interfaces:** None (documentation only).

- [ ] **Step 1: Update the Quick Start section**

Find this block in `README.md`:

```markdown
## Quick start

\`\`\`bash
git clone <your-repo-url> quantdesk && cd quantdesk

# Phase 1 runs with ZERO installs (standard library only):
python recommender.py            # prints watchlist + writes dashboard.html

# Upgrade to real data + better sentiment:
pip install yfinance vaderSentiment feedparser
python recommender.py

# Phase 2 seed — backtesting:
pip install pandas numpy matplotlib
python backtest.py RELIANCE.NS 20 50
\`\`\`

Then edit `CAPITAL` and `UNIVERSE` at the top of `recommender.py` to match yours.
```

Replace it with:

```markdown
## Quick start

\`\`\`bash
git clone <your-repo-url> quantdesk && cd quantdesk

pip install -r requirements.txt   # yfinance, feedparser, vaderSentiment

python recommender.py             # prints watchlist + writes dashboard.html
python backtest.py RELIANCE.NS 20 50
\`\`\`

Then edit `CAPITAL` and `UNIVERSE` at the top of `recommender.py` to match yours.
Both scripts fetch live prices and news over the network on every run — there
is no offline or cached mode. A fetch failure aborts the run with an error
naming the symbol or feed that failed.
```

- [ ] **Step 2: Update the Config table**

Find this block:

```markdown
### Config (top of `recommender.py`)
| Setting | Meaning |
|---|---|
| `UNIVERSE` | assets to rank (symbol, type, keywords) |
| `RSS_FEEDS` | free news feeds to pull |
| `WEIGHTS` | momentum vs sentiment mix |
| `STYLE` | `intraday` / `short_term` / `swing` |
| `CAPITAL` | rupees to deploy (e.g. 25000) |
| `MAX_DEPLOY_PCT` | max % of capital deployed (default 60%) |
| `MAX_ALLOC_PER_IDEA` | max % in one name (default 20%) |
```

Replace it with:

```markdown
### Config (top of `recommender.py`)
| Setting | Meaning |
|---|---|
| `UNIVERSE` | assets to rank (symbol, yf_symbol, type, keywords) |
| `RSS_FEEDS` | free news feeds to pull |
| `STYLE` | `intraday` / `short_term` / `swing` — also sets the momentum vs sentiment mix (`STYLE_WEIGHTS`) |
| `SCORE_THRESHOLD` | minimum combined score for "Research LONG" (default 0.15) |
| `CAPITAL` | rupees to deploy (e.g. 25000) |
| `MAX_DEPLOY_PCT` | max % of capital deployed (default 60%) |
| `MAX_ALLOC_PER_IDEA` | max % in one name (default 20%) |
```

- [ ] **Step 3: Update the Tech stack sentiment line**

Find:
```markdown
- **Sentiment:** built-in lexicon → VADER → FinBERT / LLM (upgrade path)
```

Replace with:
```markdown
- **Sentiment:** VADER (lexicon-based, current) → FinBERT / LLM (future upgrade path)
```

- [ ] **Step 4: Add a note under the Example section**

In README.md, the Example section ends with a fenced code block whose last
line is `Suggested deployed: Rs 15,000  |  Cash buffer: Rs 10,000`.

Immediately after that code block's closing fence (and before the `### Config` heading), add:

```markdown
> Scores now come from live price and news data, so exact numbers will
> differ every run — the table above is illustrative, not a fixed sample.
```

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "Update README for real-data Phase 1 (no zero-install tier, network required)"
```

---

### Task 6: Final verification

**Files:** None modified — verification only.

**Interfaces:** None.

- [ ] **Step 1: Verify a clean install works end-to-end**

Run: `pip install -r requirements.txt`
Expected: exits 0, no errors (all three real dependencies already installed from prior tasks, this just confirms the final `requirements.txt` is internally consistent).

- [ ] **Step 2: Run the complete automated test suite**

Run: `python -m pytest tests/ -v`
Expected: all tests pass (15 total: 3 in `test_prices.py`, 7 in `test_news.py`, 5 in `test_core.py`), none skipped, no network calls made (all fetches are monkeypatched).

- [ ] **Step 3: Confirm no leftover references to removed code**

Run: `grep -rn "build_price_series\|_stable_score\|_estimate_momentum\|_estimate_sentiment" --include="*.py" .`
Expected: no matches — confirms the old fake-scoring and synthetic-price code paths are fully gone.

- [ ] **Step 4: Manual smoke test (requires network — report results, don't block on failure here)**

Run: `python recommender.py`
Expected: either a populated ranking table + `dashboard.html` written, or a clear `RuntimeError` naming the failing symbol/feed (e.g. if a ticker is delisted or a feed URL is stale — `RSS_FEEDS` in the repo point at third-party endpoints that may have moved since the README was written). If it errors, note which symbol/feed failed; fixing a stale feed URL or ticker mapping is a follow-up, not a plan blocker, since the code's job here is to fail loudly and correctly, which a clear error demonstrates.

Run: `python backtest.py RELIANCE.NS 20 50`
Expected: same — either a real backtest result, or a clear `RuntimeError` naming the symbol.

- [ ] **Step 5: Report results to the user**

Summarize: test suite pass/fail counts, and the outcome of the two manual smoke-test runs (success with sample output, or the specific error surfaced). No commit needed for this task — it's verification only.
