# Phase 1: Real Data Design

**Date:** 2026-08-03
**Status:** Approved

## Problem

QuantDesk's README describes Phase 1 (research & recommendation) as "built ✅" —
ranking a watchlist by real price momentum and real news sentiment. The actual
code does neither:

- `recommender.py`'s `_estimate_momentum` / `_estimate_sentiment` derive scores
  from a hash of the symbol/keyword text (`_stable_score`), not from any market
  or news data. Scores are deterministic fiction dressed up as research output.
- `backtest.py` has a literal syntax bug — a stray `\n` typed as two characters
  into the source on line 31 — so it currently cannot run at all
  (`SyntaxError: unexpected character after line continuation character`).
  Its price series is also synthetic (a seeded sine wave), so even once fixed
  it backtests against fake data.

This spec covers making Phase 1 real: genuine price momentum, genuine news
sentiment, a working backtester against real historical prices, and the
supporting module/test/doc changes. It does not cover Phase 2 items
(strategy library, paper trading, execution, risk engine) — those remain
future work per the README roadmap and are out of scope here.

## Decisions

These were confirmed with the user during brainstorming:

1. **Scope:** Fix `backtest.py`'s syntax bug and replace fake scoring in both
   scripts with real data — not just a minimal bug fix, and not a jump ahead
   to Phase 2's backtesting-library upgrade.
2. **Network behavior:** No offline/cached fallback. If a price or news fetch
   fails, the run fails loudly with a clear error. A research tool that
   silently shows stale or fabricated numbers as if they were current is
   worse than one that refuses to run.
3. **Dependencies:** `yfinance`, `feedparser`, and `vaderSentiment` become
   hard requirements. The README's current "runs with ZERO installs" framing
   is dropped — a zero-install tier can't produce real momentum/sentiment,
   which defeats the purpose of this change.
4. **Module layout:** Introduce `sources/prices.py` and `sources/news.py`
   (matching the repo structure the README already documents as planned),
   rather than inlining fetch logic into `recommender.py`.
5. **Backtest data:** `backtest.py` reuses `sources/prices.py` for real
   historical closes instead of its synthetic sine-wave generator. Fixing
   only the syntax bug would leave a working-but-meaningless tool.

## Architecture

```
sources/
├── __init__.py
├── prices.py     # fetch_price_history() via yfinance
└── news.py       # fetch_headlines() via feedparser, match + score via VADER

recommender.py     # UNIVERSE (+ yf_symbol), scoring, ranking, sizing, output
backtest.py        # SMA-crossover backtest, now fed by sources/prices.py
```

### `sources/prices.py`

```python
def fetch_price_history(yf_symbol: str, period: str = "6mo") -> list[float]:
    """Daily close prices, oldest to newest. Raises RuntimeError if the
    fetch fails or returns no data — no fallback."""
```

Wraps `yfinance.download(yf_symbol, period=period)`. Raises `RuntimeError`
with the symbol and underlying cause in the message on empty result or
exception — callers do not need to guess why a run failed.

### `sources/news.py`

```python
def fetch_headlines(feed_urls: list[str]) -> list[dict]:
    """Each dict: {"title": str, "summary": str}. Raises RuntimeError only
    if EVERY feed fails / zero headlines come back overall — partial
    per-feed failure is tolerated."""

def match_headlines(headlines: list[dict], keywords: list[str]) -> list[dict]:
    """Case-insensitive substring match against title+summary."""

def score_sentiment(headlines: list[dict]) -> float:
    """Mean VADER compound score over the given headlines, in [-1, 1].
    Returns 0.0 (neutral) for an empty list — no matched headlines is a
    legitimate 'no signal' outcome, not an error."""
```

Uses `vaderSentiment.vaderSentiment.SentimentIntensityAnalyzer`.

### `recommender.py` changes

- `UNIVERSE` entries gain a `yf_symbol` field, e.g.:
  - `BTC` → `BTC-USD`, `ETH` → `ETH-USD`
  - `NVDA` → `NVDA`, `MSFT` → `MSFT`
  - `RELIANCE` → `RELIANCE.NS`, `INFY` → `INFY.NS`, `TCS` → `TCS.NS`
  - `HDFC` → `HDFCBANK.NS` (the old standalone "HDFC" ticker merged into
    HDFC Bank in 2023; `HDFCBANK.NS` is the correct current NSE symbol)
- Headlines are fetched **once** per run (`sources.news.fetch_headlines`)
  and filtered per-asset via `match_headlines`, not re-fetched per asset.
- `_estimate_momentum(asset)` replaced:
  ```
  momentum = clip(0.5 * return_10d + 0.5 * (last_close / sma_50 - 1), -1, 1)
  ```
  where `return_10d = (close[-1] - close[-11]) / close[-11]` and `sma_50` is
  the mean of the last 50 closes. Requires at least 51 closes of history;
  `period="6mo"` comfortably provides this for daily bars.
- `_estimate_sentiment(asset)` replaced by
  `score_sentiment(match_headlines(headlines, asset["keywords"]))`.
- Combination stays the existing `STYLE_WEIGHTS`-driven weighted sum, now
  operating on real values roughly in `[-1, 1]` instead of the old
  artificially-floored `[0.05, 0.99]`. Scores can be genuinely negative
  (e.g. broad downturn) — that's intentional per decision #2's honesty
  requirement, not a bug.
- `SCORE_THRESHOLD` (new named constant, replacing the hardcoded `0.55`)
  set to `0.15`, applied the same way (`"Research LONG"` if
  `score >= SCORE_THRESHOLD` else `"Watchlist"`). Documented as tunable.
- `_position_sizing` logic is unchanged (already correctly guards
  `score <= 0` before allocating).

### `backtest.py` changes

- Fix the syntax bug: line 31 becomes two statements
  (`long_sma = sma(prices, long_window)` then `cash = 10000.0`).
- `build_price_series(symbol, periods=250)` replaced by a direct call to
  `sources.prices.fetch_price_history(symbol, period="1y")` — `yfinance`
  only accepts named periods (`"1y"`, `"6mo"`, etc.), not an arbitrary day
  count, so the `periods` parameter is dropped rather than faked. The
  backtest runs over however many trading days `"1y"` actually returns
  (typically ~250, close to today's default); `run_backtest` and the
  `sma()` helper are unaffected since they already work off `len(prices)`.
  CLI usage is unchanged (`python backtest.py RELIANCE.NS 20 50`); the
  symbol argument was already yfinance-style in the existing default.

### `requirements.txt`

`yfinance`, `feedparser`, `vaderSentiment` uncommented and required.
`pandas`/`numpy`/`matplotlib` remain commented as future Phase 2 items
(VectorBT/PyBroker migration) — not needed for this change.

### `README.md`

Quick Start section updated: remove the "Phase 1 runs with ZERO installs"
claim and the two-step install framing; state plainly that `pip install -r
requirements.txt` and network access are required to run either script.

## Error handling

- Price fetch failure (bad symbol, network down, empty result) →
  `RuntimeError` from `sources/prices.py`, propagates uncaught, run aborts
  with a message naming the failing symbol.
- News fetch failure where **all** feeds fail → `RuntimeError` from
  `sources/news.py`, run aborts.
- News fetch where some feeds fail but others succeed → proceeds with what
  was retrieved (not a fallback — just tolerance of partial feed outages).
- Asset with valid price data but no matching headlines → sentiment `0.0`,
  run continues normally.
- `backtest.py` on an invalid/delisted symbol → same `RuntimeError` from
  `sources/prices.py`, not an internal `yfinance`/pandas traceback.

## Testing

- `tests/test_core.py` is updated to monkeypatch
  `sources.prices.fetch_price_history` and `sources.news.fetch_headlines`
  with small canned fixtures, so the suite stays fast and network-free
  while exercising the real momentum/sentiment/ranking/sizing math (not a
  fake-score stub as today).
- New/updated cases:
  - Momentum formula produces the expected value for a known price fixture.
  - Sentiment scoring produces the expected value for known headline text
    (clearly positive vs. clearly negative vs. no matches → `0.0`).
  - Ranking and position sizing behavior (existing coverage, re-verified
    against the new score range).
  - `backtest.py` runs without `SyntaxError` and produces the documented
    output shape, using a monkeypatched price fixture.
- Actually hitting yfinance/RSS over the network is verified manually by
  running the scripts (not part of the automated suite) — consistent with
  the "no fallback" decision being a runtime concern, not a test-suite
  requirement.

## Out of scope

- Phase 2 items: strategy library, paper trading, execution layer (OpenAlgo
  / pykiteconnect), risk engine, go-live — unchanged from README roadmap.
- Migrating `backtest.py` to VectorBT/PyBroker, walk-forward validation,
  transaction costs/slippage modeling — remains a later Phase 2 step.
- Caching layer / `data/` directory — explicitly rejected by decision #2.
