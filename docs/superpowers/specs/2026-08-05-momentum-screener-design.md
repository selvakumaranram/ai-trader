# QuantDesk: Momentum-Based Short-Term Screener Design

**Date:** 2026-08-05
**Status:** Approved

## Problem

`Momentum_Based_Short_Term_Stock_Strategy.md` (repo root) describes a momentum-investing
strategy for Indian equities: a multi-timeframe weighted score, quality filters (market
cap, ASM/GSM, F&O ban, promoter holding, debt-to-equity, earnings growth), EMA trend
confirmation, volume confirmation, risk management (stop-loss/target/trailing stop), and
a backtest-before-trust workflow. None of this exists in QuantDesk today — the existing
dashboard's `momentum` field (`recommender._compute_momentum`) is a much simpler
10-day-return-vs-50-day-SMA blend applied uniformly across a fixed 40-asset universe
(crypto + US equities + ~22 Indian equities), with no quality gates, no EMA/RSI/MACD/ATR,
and no NSE-specific data at all.

The user wants this built as a new, separate section of the existing QuantDesk app (not
a separate deployment) — a screener purpose-built for Indian equities, since the
strategy's quality filters are meaningless for crypto/US stocks.

## Decisions

Confirmed with the user during brainstorming:

1. **Quality filters use a real NSE data source**, not a best-effort/skip approach —
   despite the added complexity and the real risk that NSE's anti-bot posture blocks
   requests from Vercel's serverless IPs (see Risks below). One exception: **promoter
   holding is sourced from yfinance's `.info`, not NSE** — NSE has no bulk feed for
   shareholding pattern (it's per-company quarterly filings, not a single downloadable
   list like the ban lists), so pulling it from NSE would mean 200 fragile per-symbol
   requests for one filter. It gets the same best-effort/yfinance treatment as
   debt-to-equity, which NSE's exchange feeds don't publish at all (it's a
   balance-sheet ratio, not market data).
2. **New tab(s) in the existing QuantDesk app**, not a separate page or separate
   deployment — reuses the existing header, capital input, styling, and `apiFetch`
   plumbing.
3. **Universe: NSE equities only**, anchored on the **Nifty 200** constituent list
   (published directly by NSE), not the existing 40-asset `UNIVERSE`. Crypto and US
   equities are out of scope for this feature entirely.
4. **Compute model: scheduled + cached**, not live-per-request. A daily Vercel Cron job
   runs the full screen and writes results to Postgres (the database already
   provisioned for Holdings/Watchlist); tabs read the cached results instantly. This
   avoids both a serverless-timeout risk (200 symbols × NSE + yfinance lookups) and
   hammering NSE/yfinance on every tab open. Daily cadence also matches Vercel's
   Hobby-tier cron limit (minimum once-per-day interval) and reality — NSE's delivery %
   data is only finalized end-of-day, so intraday refresh wouldn't gain anything for
   that filter anyway.
5. **Five tabs, not one**: a composite **Screener** tab (full quality gates + weighted
   score, the "give me a filtered shortlist" tool) plus four **timeframe tabs** — 1
   Day / 3 Day / 7 Day / 1 Month Movers — that apply only the market-cap filter and
   sort by that period's raw return (the "let me eyeball what's moving" tool). The
   timeframe tabs were added after the user found a single composite score too opaque
   for building intuition about which specific timeframe is driving a stock's strength.
6. **Every row shows sector, P/E, and a link out to `screener.in/company/<SYMBOL>/`**
   (opens in the user's own browser — NSE's server-side anti-bot posture doesn't apply
   to a client-side hyperlink) for further research beyond what QuantDesk itself shows.
7. **Backtest included in this build**, not deferred — a 6th tab that replays the exact
   same scoring/filter functions the live Screener tab uses against historical data, so
   the backtest is honestly testing the live rules, not a separate re-implementation
   that could drift.

## Architecture

```
Daily cron (Vercel Cron, ~19:00 IST — after NSE's EOD bhavcopy is published)
        │
        ▼
  api/cron/momentum_screen.py
        │
   ┌────┴────┐
   ▼         ▼
sources/nse.py           sources/prices.py (extended: pull Open/High/Low/
 - Nifty 200 list          Volume alongside Close, not Close-only as today)
 - F&O ban list
 - ASM list
 - GSM list
 - Latest bhavcopy
   (delivery %, volume)
        │
        ▼
  momentum_screen.py (new scoring module, shared by cron + backtest)
   - quality filter gates (pass/fail)
   - EMA trend gate
   - weighted momentum score
   - per-timeframe returns (1D/3D/7D/1M)
   - suggested stop-loss/target
        │
        ▼
  Postgres: momentum_rankings table
  (overwritten each cron run, stamped with run date)
        │
        ▼
  api/momentum.py (GET — reads the latest cached rows, instant, no live fetch)
        │
        ▼
  "Momentum" section in the existing QuantDesk UI: 5 tabs (Screener,
  1D/3D/7D/1M Movers) reading the same cached rows, sorted/filtered
  differently per tab — plus a 6th Backtest tab that calls
  momentum_screen.py's functions on-demand against historical data
  instead of reading the cache.
```

## Data sources (`vercel-demo/sources/nse.py`, new file)

All bulk requests — one HTTP call per data point per cron run, not per-symbol:

| Data | Source | Refresh |
|---|---|---|
| Nifty 200 constituents | `archives.nseindia.com/content/indices/ind_nifty200list.csv` | Cached ~1 week |
| F&O ban list | `nsearchives.nseindia.com/content/fo/fo_secban.csv` | Every cron run |
| ASM list | NSE surveillance list endpoint | Every cron run |
| GSM list | NSE surveillance list endpoint | Every cron run |
| Bhavcopy (delivery %, volume, OHLC) | `nsearchives.nseindia.com/products/content/sec_bhavdata_full_<DDMMYYYY>.csv` | Every cron run (previous trading day) |

NSE requires session cookies (a `GET` to nseindia.com's homepage first, to receive
cookies, then reusing them plus a realistic `User-Agent`/`Referer` on the actual data
requests via `requests.Session()`) — naive unauthenticated requests are commonly
rejected. **Symbol matching:** NSE's files key by the bare symbol (e.g. `RELIANCE`)
while `UNIVERSE`-style code uses `yf_symbol` (e.g. `RELIANCE.NS`) for yfinance —
`sources/nse.py` normalizes between the two; the Nifty 200 list itself becomes the
source of bare symbols, with `.NS` appended for the yfinance leg.

Promoter holding, debt-to-equity, market cap, sector, and P/E all come from yfinance's
`yf.Ticker(symbol).info` (one call per symbol — slower than the bulk NSE calls, but
unavoidable since none of these are in NSE's bulk feeds or in `yf.download`'s OHLCV
response). Coverage for NSE tickers via `.info` is known to be inconsistent; a missing
value is treated as `"unknown"` for that filter, never assumed to mean "fails the gate."

`sources/prices.py`'s `fetch_price_history` currently discards everything except
`Close` from `yf.download`'s response — extended (or a new sibling function) to also
return `Open`/`High`/`Low`/`Volume`, needed for ATR and volume-based factors.

## Scoring & quality filters (`vercel-demo/momentum_screen.py`, new file)

**Quality filter gates** — pass/fail, applied before scoring; a symbol failing any gate
is excluded from the Screener tab entirely (not down-ranked):

| Filter | Rule | Source |
|---|---|---|
| Market cap | > ₹5,000 Cr | yfinance `.info` |
| Avg daily traded value | > ₹10 Cr | Computed from bhavcopy volume × price |
| ASM restriction | Not on list | NSE |
| GSM restriction | Not on list | NSE |
| F&O ban | Not on list | NSE |
| Promoter holding | > 40% | yfinance `.info` (best-effort) |
| Debt-to-equity | < 1.0 | yfinance `.info` (best-effort) |
| Earnings growth | Latest reported YoY ≥ 0% | yfinance `.info` (best-effort) |

**Trend confirmation gate** (also pass/fail): Price > EMA20, Price > EMA50, and
EMA20 > EMA50 — all three must hold.

**Momentum score** (only computed for symbols passing every gate above), weights taken
directly from the strategy doc:

| Factor | Weight |
|---|---|
| 1 Month Return | 30% |
| 7 Day Return | 25% |
| 3 Day Return | 15% |
| 1 Day Return | 10% |
| Volume Increase | 10% |
| Delivery Percentage | 5% |
| RSI (55–70 band) | 5% |

Each factor is normalized to a 0–1 range before weighting: returns are normalized
against that day's Nifty 200 pool's own return distribution (so "strong" is relative to
the field, not a fixed arbitrary cutoff); RSI scores highest at the center of the 55-70
band, tapering to 0 outside it.

**Volume confirmation** is a badge, not a gate — the strategy doc frames it softly
("momentum is stronger when accompanied by...") rather than exclusionary like the
quality filters. Computed as: rising price + rising volume + rising delivery % over the
recent window, shown as ✓ full / partial / none per result.

**Suggested risk management**, shown per result on the Screener tab: stop-loss at
entry × 0.95, target range at entry × 1.10–1.15, and the existing capital-based position
sizing already used elsewhere in the app.

## Tabs

**Screener** (composite): full quality gates + trend gate + weighted score, top 10-20
shown, ranked by score. Each row: rank, score breakdown (which factors drove it), which
quality gates passed, volume-confirmation badge, suggested stop-loss/target/position
size — plus the shared fields below.

**1 Day / 3 Day / 7 Day / 1 Month Movers** (four tabs): market-cap filter only (no ASM/
GSM/F&O-ban/promoter-holding/debt-to-equity/earnings gates — these are for quickly
eyeballing raw movers, not a filtered shortlist), sorted by that period's return,
descending. Each row: symbol, that period's return — plus the shared fields below.

**Shared fields on every row, all 5 tabs:** symbol, sector, P/E ratio, and a link to
`screener.in/company/<SYMBOL>/` (opens in a new browser tab).

**Backtest** (6th tab): see below.

## Backtest

Reuses `momentum_screen.py`'s exact quality-gate and scoring functions — not a
re-implementation — against historical data, so it validates the same rules the live
Screener tab uses.

- **Method:** for each historical trading day in a chosen lookback window (default 6
  months), run the same quality gates + scoring against that day's data, take the
  top-N ranked symbols, simulate entering at next trading day's open. Exit at whichever
  comes first: stop-loss (-5%), target (+10% to +15%), a trailing stop once the position
  is profitable, or a 10-trading-day maximum holding period (matching "short-term").
- **Metrics:** win rate, average return per trade, average holding days, max drawdown,
  total simulated return over the window.
- **UI:** pick a lookback window, run on demand (not cron'd — this is a much heavier,
  slower request than the cached tabs, since it needs historical OHLCV for every Nifty
  200 symbol across the whole window, not just the latest day). Shows a loading state.
  Each run's fetched inputs are cached so re-running the same window doesn't re-fetch
  everything.
- A missing symbol-day (data gap) is skipped for that symbol on that day, not treated
  as aborting the whole backtest run.

## Scheduling & caching

New Postgres table (`vercel-demo/schema.sql`, additive to the existing `holdings`/
`watchlist` tables):

```sql
CREATE TABLE IF NOT EXISTS momentum_rankings (
    id SERIAL PRIMARY KEY,
    run_date DATE NOT NULL,
    symbol TEXT NOT NULL,
    sector TEXT,
    pe_ratio NUMERIC,
    return_1d NUMERIC,
    return_3d NUMERIC,
    return_7d NUMERIC,
    return_1m NUMERIC,
    passes_quality_gates BOOLEAN NOT NULL,
    passes_trend_gate BOOLEAN NOT NULL,
    quality_gate_detail JSONB NOT NULL,
    momentum_score NUMERIC,
    volume_confirmation TEXT,
    stop_loss NUMERIC,
    target_low NUMERIC,
    target_high NUMERIC,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_momentum_rankings_run_date ON momentum_rankings(run_date);
```

One row per symbol per cron run. `GET /api/momentum?tab=screener|1d|3d|7d|1m` reads the
most recent `run_date`'s rows and sorts/filters in the query per tab — no
recomputation. `quality_gate_detail` (JSONB) stores the per-filter pass/fail/unknown
breakdown shown on the Screener tab.

**Vercel Cron:** `vercel.json`'s `crons` array gets a new entry pointing at
`/api/cron/momentum_screen`, scheduled daily. This is a manual Vercel-dashboard-adjacent
setup step (like the Postgres provisioning before it) — the cron entry itself ships in
`vercel.json`, but Vercel Cron requires the project to be on a plan that supports it and
the deployment to pick up the new `vercel.json`.

## Error handling

- If NSE blocks a cron run's requests entirely, the API keeps serving the last
  successful `run_date`'s cached rows with an "as of [date]" stamp, plus a staleness
  warning if that date is more than ~2 days old. A tab is never blank or broken because
  a single cron run failed.
- A per-symbol data failure (NSE or yfinance) drops that symbol from that run's rows —
  doesn't fail the whole cron run.
- A gate whose underlying data is missing (e.g. yfinance `.info` has no `debtToEquity`
  for a symbol) is recorded as `"unknown"` in `quality_gate_detail`, and the symbol is
  **excluded** from the Screener tab (a filter that can't be verified is not the same
  as a filter that passed) — but still appears normally on the four timeframe tabs,
  since those don't apply this gate at all.
- The backtest skips a missing symbol-day rather than aborting the run.

## Risks (documented, not solved by this spec)

- **NSE anti-bot blocking is a real, unverifiable-until-deployed risk.** NSE is known to
  block requests from datacenter/cloud IPs, which includes Vercel's serverless
  functions. The cookie/session/header approach in `sources/nse.py` is the standard
  mitigation, but there is no way to confirm it works from this environment before a
  real cron run executes against the live NSE endpoints. If NSE blocks Vercel entirely,
  every quality gate sourced from NSE (ASM, GSM, F&O ban, delivery %) degrades to
  `"unknown"` for every symbol, effectively disabling the Screener tab's filtering
  (the four timeframe tabs, which only need yfinance, would be unaffected).
- **NSE's unofficial endpoints can change without notice** — there's no public API
  contract, just conventionally-used URLs the community has reverse-engineered. A URL
  or file-format change silently breaks that specific data point until noticed and
  fixed.
- **yfinance `.info` coverage for NSE tickers is inconsistent** — promoter holding,
  debt-to-equity, earnings growth, sector, and P/E may be missing or stale for some
  Nifty 200 constituents, independent of any NSE-blocking risk.

## Out of scope for v1

All explicitly listed as "Future Enhancements" in the strategy doc, deliberately
deferred rather than forgotten: sector momentum ranking, institutional buying data,
relative strength vs Nifty, AI-based momentum prediction, dedicated news-sentiment
analysis for these stocks (distinct from the existing app-wide sentiment feature),
automatic buy/sell execution, portfolio optimization. Also out of scope: intraday
refresh (daily cron only, per decision #4), a UI to edit the candidate pool beyond
Nifty 200, and any mobile-specific redesign beyond what the app already has.
