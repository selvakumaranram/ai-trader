# QuantDesk Dashboard: Design

**Date:** 2026-08-04
**Status:** Approved

## Problem

The Phase 1 Vercel demo (`vercel-demo/`) proved the real-data pipeline works
end to end (live yfinance prices, live RSS/VADER sentiment), but its only
interface is a plain-text `/api/recommend` endpoint using a hardcoded
₹25,000 capital, one global style, and an 8-asset watchlist. The user wants
a real product surface: a dashboard with dynamic capital, results split by
trading style, a today's-movers view, and an on-demand search for any
symbol with a "why" explanation — built on top of the same reviewed
scoring logic (`_compute_momentum`, `sources.news` sentiment), not a
rewrite of it.

This spec covers the dashboard UI, its two backend API endpoints, and the
watchlist/position-sizing changes needed to support them. It builds inside
`vercel-demo/` (kept at that path — the live Vercel project's Root
Directory is already configured to it, and renaming would mean redoing
dashboard settings that were already a source of friction) rather than
migrating into the reviewed `master` codebase; `vercel-demo/`'s Python
files are a standalone working copy that has already diverged from the
reviewed `sources/prices.py` (it tolerates NaN closes instead of raising —
see [[quantdesk-env-pandas-dll-block]] context), and this spec continues
building on that copy, not on the strict reviewed repo.

## Decisions

Confirmed with the user during brainstorming:

1. **Section layout:** three sections ranked by trading *style* — Day
   Trading (`intraday` weights), Short-Term (`short_term` weights), and
   Swing/Long-Term (`swing` weights) — each ranking the *entire* watchlist
   (crypto and equities together), not walled off by asset type. Plus a
   fourth **Top Movers** section (see #6).
2. **Search scope:** any ticker symbol, fetched live on demand — not
   restricted to the curated watchlist.
3. **Watchlist size:** expand from 8 to ~40 assets so each section can
   show a meaningful top 10.
4. **Explanation ("why"):** a structured data breakdown (momentum %, its
   10-day-return/50-day-trend components, sentiment score, the matched
   headlines, which style produced the shown score) — no invented
   narrative, no LLM in the loop. Matches this project's existing
   research-first, honest-numbers philosophy.
5. **Frontend:** React + Vite with a real build step, replacing the
   current static `index.html`.
6. **Top Movers (added after initial scope):** a fourth section ranking
   the same watchlist by *today's* % price change (gainers and losers),
   reusing data already fetched for the other three sections — no extra
   API calls. This is explicitly **not** market-wide NSE/BSE scanning
   (thousands of stocks); that would need Kite Connect's market data API
   or a fragile NSE-website scrape, neither of which this spec covers.
   Kite is not required for anything in this spec.
7. **Capital is per-section, not split three ways.** The three style
   sections are alternative strategies, not a combined portfolio — the
   same entered capital is shown independently allocated under each
   style ("if you traded this style with this capital..."), not divided
   by 3.

## Bug found during design: MIN_TICKET breaks small capital amounts

The reviewed `_position_sizing` uses a fixed `MIN_TICKET = 500` (rupees)
floor alongside `MAX_ALLOC_PER_IDEA = 0.20`. For the user's own example
(₹1,000 capital): `max_per_idea = 1000 × 0.20 = 200`, which is always
below the fixed ₹500 floor — every allocation would round to zero,
regardless of score. This never surfaced before because the original CLI
tool only ever ran with the hardcoded ₹25,000 default. Fix: replace the
fixed floor with `MIN_TICKET = capital × 0.02` (2% of capital) in the
dashboard's position-sizing logic. This is scoped to the dashboard's
client-side port (see Architecture) and does not touch the reviewed
`recommender.py`'s `_position_sizing`, which is out of scope for this spec.

## Architecture

```
vercel-demo/
├── package.json, vite.config.js, index.html   # Vite app, project root
├── src/
│   ├── main.jsx, App.jsx
│   ├── components/                             # CapitalInput, SectionTabs,
│   │                                             AssetCard, WhyPanel, SearchBox
│   └── lib/positionSizing.js                    # client-side port, see below
├── api/
│   ├── dashboard.py                             # GET /api/dashboard
│   └── search.py                                # GET /api/search?symbol=...
├── requirements.txt, recommender.py, backtest.py, sources/   # unchanged
```

Vercel's Vite + Python-Functions combination is zero-config: Framework
Preset `Vite` builds `src/` → `dist/`, and `api/*.py` is auto-detected as
serverless functions regardless. No `vercel.json` changes beyond what's
already there (`functions.api/*.py.maxDuration`).

### Backend: two read endpoints, no capital parameter

**`GET /api/dashboard`** — fetches each watchlist asset's price history
once and the shared RSS headline pool once (matching `recommender.build_rankings`'s
existing fetch-once pattern), then for each asset:

- `momentum = recommender._compute_momentum(closes, symbol)`
- `day_change_pct = (closes[-1] - closes[-2]) / closes[-2] * 100`
- `matched = news_source.match_headlines(headlines, asset["keywords"])`
- for each style in `("intraday", "short_term", "swing")`: call
  `recommender._score_asset(asset, style, closes, matched)` — reused
  as-is, called three times per asset. Momentum/sentiment recomputation
  inside each call is pure arithmetic on already-fetched data (cheap);
  this avoids touching `_score_asset`'s signature at all.

Response:
```json
{
  "assets": [
    {
      "symbol": "NVDA", "type": "equity_us",
      "momentum": 0.082, "momentum_detail": {"return_10d": 0.041, "trend_vs_sma50": 0.061},
      "sentiment": 0.150, "day_change_pct": 3.21,
      "matched_headlines": [{"title": "...", "summary": "..."}],
      "scores": {
        "intraday":   {"score": 0.091, "action": "Research LONG"},
        "short_term": {"score": 0.075, "action": "Watchlist"},
        "swing":      {"score": 0.113, "action": "Research LONG"}
      }
    }
  ],
  "failed": [{"symbol": "XYZ", "error": "No price data returned for 'XYZ.NS' ..."}]
}
```

Capital is **intentionally absent** from this response — sizing is
capital-dependent, ranking/scoring is not, so it's computed client-side
(see below) and updates instantly on every capital-input change with zero
network round-trips.

**`GET /api/search?symbol=XXX`** — same per-asset computation as above for
one ad-hoc symbol not necessarily in `UNIVERSE`. Keyword fallback: since
arbitrary symbols have no curated keyword list, matching uses the typed
symbol itself (suffix-stripped — `.NS`, `.BO`, `-USD` removed, lowercased)
as the sole keyword. **Known, disclosed limitation:** headlines usually
say "Apple," not "AAPL" — ticker-text matching will often yield zero
matched headlines (sentiment `0.0`, neutral) for tickers whose symbol
differs from how the company is referred to in prose. Momentum-based
analysis is unaffected by this and works fully for any symbol. This
limitation is surfaced in the UI (see below), not hidden.

Response shape matches one entry of `/api/dashboard`'s `assets` array
(same fields), or `{"error": "..."}` with HTTP 4xx/5xx on fetch failure
(e.g. invalid symbol, insufficient history).

### Error handling: dashboard/search tolerate per-asset failures

**This is an intentional, disclosed deviation from the reviewed Phase 1
philosophy** ("no fallback, one bad asset aborts the whole run"). That
rule made sense for an 8-asset CLI tool where a failure is unusual and
aborting is cheap to retry. At ~40 assets, individual fetch failures
(delisted tickers, transient rate limits) are routine, and aborting the
entire dashboard over one bad asset would be a much worse experience than
showing 38 of 40 with the 2 failures listed. `/api/dashboard` therefore
catches per-asset exceptions, excludes that asset from `assets`, and
lists it in `failed` with its error message — still surfaced to the user
(the failure isn't hidden or silently substituted with fake data), just
not fatal to the whole response. `/api/search` still fails loudly for its
single requested symbol (nothing to degrade gracefully with one asset).

### Frontend: client-side position sizing (`src/lib/positionSizing.js`)

A direct JS port of `_position_sizing`, with the `MIN_TICKET` fix above:

```js
export function sizePositions(scoredAssets, capital) {
  const MAX_DEPLOY_PCT = 0.60;
  const MAX_ALLOC_PER_IDEA = 0.20;
  const MIN_TICKET = capital * 0.02;

  const positive = scoredAssets.filter(a => a.score > 0).map(a => a.score);
  const totalPositive = positive.length ? positive.reduce((a, b) => a + b, 0) : 1.0;
  const deployable = capital * MAX_DEPLOY_PCT;
  const maxPerIdea = capital * MAX_ALLOC_PER_IDEA;

  return scoredAssets.map(a => {
    let allocation = 0;
    if (a.score > 0) {
      const raw = deployable * (a.score / totalPositive);
      allocation = Math.min(maxPerIdea, raw);
      if (allocation < MIN_TICKET) allocation = 0;
    }
    return { ...a, suggested: Math.round(allocation) };
  });
}
```

Each of the three style sections: sort `assets` by that style's
`scores.<style>.score` descending, take top 10, run `sizePositions` on
those 10 with the current capital-input value. Re-running on every
keystroke (debounced ~150ms) is instant — no fetch involved.

**Top Movers does not get capital allocation.** `day_change_pct` isn't a
conviction score on the same scale as momentum/sentiment — running
position sizing on it would be mathematically meaningless (a 17% mover
isn't "17% more investable" than a 2% mover). Top Movers shows rank,
`day_change_pct`, and the asset's existing swing-style score/action for
context, split into Top Gainers and Top Losers (sorted descending /
ascending by `day_change_pct`), top 10 each — informational, not sized.

### Watchlist expansion

`UNIVERSE` in the dashboard's working copy of `recommender.py` grows from
8 to the following ~40 (symbol, yf_symbol, type — keywords follow the
existing curation pattern, reusing the word-boundary matching already
fixed in `sources/news.py`):

- **Crypto (5):** BTC (`BTC-USD`), ETH (`ETH-USD`), SOL (`SOL-USD`), BNB
  (`BNB-USD`), XRP (`XRP-USD`)
- **US equities (12):** NVDA, MSFT, AAPL, GOOGL, TSLA, AMZN, META, AMD,
  NFLX, JPM, V, DIS
- **Indian equities (23):** RELIANCE.NS, INFY.NS, TCS.NS, HDFCBANK.NS,
  ICICIBANK.NS, WIPRO.NS, ITC.NS, SBIN.NS, BHARTIARTL.NS, LT.NS,
  KOTAKBANK.NS, AXISBANK.NS, MARUTI.NS, SUNPHARMA.NS, TITAN.NS, ASIANPAINT.NS,
  BAJFINANCE.NS, HCLTECH.NS, ULTRACEMCO.NS, NESTLEIND.NS, ADANIENT.NS,
  ONGC.NS, NTPC.NS

Exact keyword lists are an implementation-time detail (follow the existing
pattern: 3-4 lowercase terms per asset tied to its sector/product), not
enumerated here to keep this spec from ballooning — the implementation
plan will spell them out verbatim per the project's no-placeholder
convention.

## UI

Single-page dashboard:
- Capital input (number field, pre-filled ₹25,000, live-updates all three
  sized sections on change).
- Search box (any symbol) — shows a dedicated result card with all 3
  styles' scores/actions and the full "why" breakdown when used.
- Four sections as tabs or stacked panels (implementation detail — the
  plan decides based on how it looks built): Day Trading, Short-Term,
  Swing/Long-Term (each: top 10 cards, symbol/score/action/suggested ₹,
  expandable "why" panel), and Top Movers (Top Gainers / Top Losers,
  no ₹ sizing, as decided above).
- A visible note when `failed` is non-empty ("2 of 40 assets unavailable
  right now: XYZ (reason), ABC (reason)") — failures stay visible, never
  silently dropped.

Visual polish (color, typography, layout rhythm) is an implementation-time
concern for whoever builds it, guided by making it "look wonderful" per
the user's request — not pre-specified pixel-by-pixel here.

## Testing

`vercel-demo/` has no automated test suite today (it's a working demo
copy, already diverged from the reviewed, tested `master` codebase). This
spec does not introduce one either — matching the existing pattern in
this folder, and appropriate for a fast-iteration product surface rather
than the reviewed core. Verification is manual: load the deployed
dashboard, confirm all four sections populate, change the capital input
and confirm suggested amounts update instantly with no network call,
search a watchlist symbol and an arbitrary non-watchlist symbol, confirm
a deliberately invalid symbol shows a clear error rather than a crash.

## Out of scope

- True market-wide (100s–1000s of stocks) gainers/losers scanning via
  Kite Connect or NSE scraping — a separate future feature, not designed
  here.
- Candlestick pattern recognition (as opposed to the existing
  return/trend-based momentum) — a different technique, not part of this
  spec.
- Live order execution via Kite Connect — unrelated to this spec; still
  Phase 2 on the original README roadmap.
- Migrating any of this back into the reviewed `master` codebase.
- Automated tests for the new dashboard code (see Testing above).
