# QuantDesk Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the plain-text `vercel-demo/` API demo into a real dashboard: dynamic capital input, four sections (Day Trading / Short-Term / Swing / Top Movers) over an expanded ~40-asset watchlist, and an any-symbol search with a structured "why" breakdown — built with React + Vite on top of the existing, reviewed scoring logic.

**Architecture:** Two new JSON API endpoints (`api/dashboard.py`, `api/search.py`) reuse `recommender._compute_momentum` / `recommender._score_asset` / `sources.news` as-is, fetching each asset's price history and the shared headline pool once and computing all three style scores from those same numbers. Capital-dependent position sizing moves entirely to the frontend (`src/lib/positionSizing.js`) so changing the capital input is instant with zero network calls. React (Vite, no extra framework) renders it all.

**Tech Stack:** Python 3.14 (existing `api/*.py` pattern, `BaseHTTPRequestHandler`), React 18 + Vite 5 (Node v24.18.0 / npm 11.16.0 confirmed available on this machine), no automated test suite (per spec — this is a fast-iteration demo surface, matching its existing untested state).

## Global Constraints

- Reuse `recommender._compute_momentum(closes, symbol)` and `recommender._score_asset(asset, style, closes, matched_headlines)` exactly as they exist today — do not change their signatures. Call `_score_asset` once per style (3x per asset) rather than refactoring it to compute all styles at once.
- **Verification split:** this machine has a confirmed Windows Application Control Policy blocking pandas' compiled DLLs (see project memory `quantdesk-env-pandas-dll-block`), so any Python file importing `sources.prices` (transitively via `yfinance`→`pandas`) cannot be executed here. Verify those files via `python -c "import ast; ast.parse(open('FILE').read())"` plus a manual trace, exactly as done throughout the earlier Phase 1 plan. **Frontend (Node/Vite/React) files have no such blocker — Node v24.18.0 and npm 11.16.0 are confirmed working on this machine, so `npm install` / `npm run build` give real, executed verification, not just tracing.**
- Any new Python file that calls `news_source.fetch_headlines` must set `recommender.RSS_FEEDS = ["https://finance.yahoo.com/news/rssindex"]` immediately after importing `recommender`, matching the existing demo-only override already in the (now-removed) `api/recommend.py` — the repo's real `RSS_FEEDS` URLs are confirmed dead (see project memory `quantdesk-stale-rss-feeds`).
- `MIN_TICKET` fix (2% of capital, replacing the fixed ₹500 floor that zeroes out all allocations below ~₹2,500 capital) lives **only** in `src/lib/positionSizing.js`. Do not touch `recommender.py`'s Python `_position_sizing` — it's unused by the new endpoints and out of scope for this plan.
- Reuse the existing color tokens established in this project's HTML output (`#07111f` background, `#10233c` cards, `#2f4b72` borders, `#e7eefc` text, `#89a6c9` muted text, `#8ecfff` accent) — extend, don't replace.
- Dashboard/search endpoints tolerate per-asset and per-headline-fetch failures (never abort the whole response over one bad asset or a dead feed) — this is an intentional, spec-documented deviation from the reviewed Phase 1 "abort on any failure" philosophy, justified by the larger asset count. Failures are always surfaced to the user, never silently dropped.
- No automated test suite for this feature (per spec's Testing section) — verification is: Python syntax + manual trace, `npm run build` success, and a manual browser checklist at the end.
- Spec: `docs/superpowers/specs/2026-08-04-quantdesk-dashboard-design.md`.
- All work happens inside `vercel-demo/` (paths below are relative to that directory unless stated otherwise).

---

### Task 1: Expand the watchlist (`recommender.py`)

**Files:**
- Modify: `vercel-demo/recommender.py`

**Interfaces:**
- Produces: `recommender.UNIVERSE` — same shape as today (`symbol`, `yf_symbol`, `type`, `keywords`), now 40 entries instead of 8. Consumed by Task 2 (`api/dashboard.py`) and Task 3 (`api/search.py`).
- Produces: `recommender._momentum_detail(closes: List[float]) -> Dict[str, float]` returning `{"return_10d", "trend_vs_sma50"}`. Consumed by Task 2 and Task 3 (both call `recommender._momentum_detail(closes)` instead of each defining their own copy).

- [ ] **Step 1: Replace `UNIVERSE`**

In `vercel-demo/recommender.py`, replace the `UNIVERSE` list (currently lines 9-18) with:

```python
UNIVERSE = [
    {"symbol": "BTC", "yf_symbol": "BTC-USD", "type": "crypto", "keywords": ["bitcoin", "etf", "halving", "institutional"]},
    {"symbol": "ETH", "yf_symbol": "ETH-USD", "type": "crypto", "keywords": ["ethereum", "layer2", "staking", "smart contract"]},
    {"symbol": "SOL", "yf_symbol": "SOL-USD", "type": "crypto", "keywords": ["solana", "defi", "layer1", "validator"]},
    {"symbol": "BNB", "yf_symbol": "BNB-USD", "type": "crypto", "keywords": ["binance", "bnb chain", "exchange token"]},
    {"symbol": "XRP", "yf_symbol": "XRP-USD", "type": "crypto", "keywords": ["ripple", "xrp", "cross-border payments"]},
    {"symbol": "NVDA", "yf_symbol": "NVDA", "type": "equity_us", "keywords": ["ai", "chip", "data center", "semiconductor"]},
    {"symbol": "MSFT", "yf_symbol": "MSFT", "type": "equity_us", "keywords": ["cloud", "enterprise", "ai", "software"]},
    {"symbol": "AAPL", "yf_symbol": "AAPL", "type": "equity_us", "keywords": ["iphone", "apple", "consumer electronics", "services"]},
    {"symbol": "GOOGL", "yf_symbol": "GOOGL", "type": "equity_us", "keywords": ["google", "search", "cloud", "advertising"]},
    {"symbol": "TSLA", "yf_symbol": "TSLA", "type": "equity_us", "keywords": ["tesla", "electric vehicle", "ev", "autonomous driving"]},
    {"symbol": "AMZN", "yf_symbol": "AMZN", "type": "equity_us", "keywords": ["amazon", "ecommerce", "cloud", "logistics"]},
    {"symbol": "META", "yf_symbol": "META", "type": "equity_us", "keywords": ["facebook", "instagram", "social media", "advertising"]},
    {"symbol": "AMD", "yf_symbol": "AMD", "type": "equity_us", "keywords": ["chip", "semiconductor", "gpu", "processor"]},
    {"symbol": "NFLX", "yf_symbol": "NFLX", "type": "equity_us", "keywords": ["netflix", "streaming", "subscriber", "content"]},
    {"symbol": "JPM", "yf_symbol": "JPM", "type": "equity_us", "keywords": ["bank", "finance", "lending", "wall street"]},
    {"symbol": "V", "yf_symbol": "V", "type": "equity_us", "keywords": ["visa", "payments", "credit card", "transactions"]},
    {"symbol": "DIS", "yf_symbol": "DIS", "type": "equity_us", "keywords": ["disney", "streaming", "entertainment", "theme park"]},
    {"symbol": "RELIANCE", "yf_symbol": "RELIANCE.NS", "type": "equity_in", "keywords": ["retail", "energy", "telecom", "consumer"]},
    {"symbol": "INFY", "yf_symbol": "INFY.NS", "type": "equity_in", "keywords": ["software", "outsourcing", "digital", "it services"]},
    {"symbol": "TCS", "yf_symbol": "TCS.NS", "type": "equity_in", "keywords": ["services", "cloud", "enterprise", "it services"]},
    {"symbol": "HDFC", "yf_symbol": "HDFCBANK.NS", "type": "equity_in", "keywords": ["bank", "finance", "credit", "lending"]},
    {"symbol": "ICICIBANK", "yf_symbol": "ICICIBANK.NS", "type": "equity_in", "keywords": ["bank", "finance", "credit", "lending"]},
    {"symbol": "WIPRO", "yf_symbol": "WIPRO.NS", "type": "equity_in", "keywords": ["software", "outsourcing", "digital", "it services"]},
    {"symbol": "ITC", "yf_symbol": "ITC.NS", "type": "equity_in", "keywords": ["fmcg", "consumer goods", "cigarette", "hotel"]},
    {"symbol": "SBIN", "yf_symbol": "SBIN.NS", "type": "equity_in", "keywords": ["bank", "psu", "finance", "lending"]},
    {"symbol": "BHARTIARTL", "yf_symbol": "BHARTIARTL.NS", "type": "equity_in", "keywords": ["telecom", "airtel", "mobile", "broadband"]},
    {"symbol": "LT", "yf_symbol": "LT.NS", "type": "equity_in", "keywords": ["infrastructure", "construction", "engineering", "capital goods"]},
    {"symbol": "KOTAKBANK", "yf_symbol": "KOTAKBANK.NS", "type": "equity_in", "keywords": ["bank", "finance", "credit", "lending"]},
    {"symbol": "AXISBANK", "yf_symbol": "AXISBANK.NS", "type": "equity_in", "keywords": ["bank", "finance", "credit", "lending"]},
    {"symbol": "MARUTI", "yf_symbol": "MARUTI.NS", "type": "equity_in", "keywords": ["automobile", "car", "suzuki", "vehicle"]},
    {"symbol": "SUNPHARMA", "yf_symbol": "SUNPHARMA.NS", "type": "equity_in", "keywords": ["pharma", "healthcare", "drug", "medicine"]},
    {"symbol": "TITAN", "yf_symbol": "TITAN.NS", "type": "equity_in", "keywords": ["jewellery", "watches", "retail", "consumer"]},
    {"symbol": "ASIANPAINT", "yf_symbol": "ASIANPAINT.NS", "type": "equity_in", "keywords": ["paint", "consumer goods", "coatings", "retail"]},
    {"symbol": "BAJFINANCE", "yf_symbol": "BAJFINANCE.NS", "type": "equity_in", "keywords": ["nbfc", "finance", "lending", "consumer credit"]},
    {"symbol": "HCLTECH", "yf_symbol": "HCLTECH.NS", "type": "equity_in", "keywords": ["software", "outsourcing", "digital", "it services"]},
    {"symbol": "ULTRACEMCO", "yf_symbol": "ULTRACEMCO.NS", "type": "equity_in", "keywords": ["cement", "infrastructure", "construction", "building materials"]},
    {"symbol": "NESTLEIND", "yf_symbol": "NESTLEIND.NS", "type": "equity_in", "keywords": ["fmcg", "food", "consumer goods", "nutrition"]},
    {"symbol": "ADANIENT", "yf_symbol": "ADANIENT.NS", "type": "equity_in", "keywords": ["infrastructure", "energy", "ports", "conglomerate"]},
    {"symbol": "ONGC", "yf_symbol": "ONGC.NS", "type": "equity_in", "keywords": ["oil", "gas", "energy", "psu"]},
    {"symbol": "NTPC", "yf_symbol": "NTPC.NS", "type": "equity_in", "keywords": ["power", "energy", "psu", "electricity"]},
]
```

Note: `INFY`, `TCS`, `WIPRO`, and `HCLTECH`'s keyword lists replace the bare
word `"it"` with the phrase `"it services"`. `"it"` is a common English
pronoun ("Tesla says **it** will...") — even with the word-boundary
matching fix from the Phase 1 final review, a bare `"it"` keyword would
still match constantly on ordinary grammar, not just IT-industry news.
`"it services"` as a phrase is far less likely to appear by accident.

- [ ] **Step 2: Add a shared `_momentum_detail` helper**

Both Task 2 (`api/dashboard.py`) and Task 3 (`api/search.py`) need the
same momentum breakdown (10-day return, trend vs. 50-day average) for the
UI's "why" panel. Rather than duplicating this in both files, add it once
to `recommender.py`, right after `_compute_momentum` (after line 47):

```python
def _momentum_detail(closes: List[float]) -> Dict[str, float]:
    return_10d = (closes[-1] - closes[-11]) / closes[-11]
    sma_50 = sum(closes[-50:]) / 50
    trend_vs_sma50 = (closes[-1] / sma_50) - 1
    return {"return_10d": round(return_10d, 4), "trend_vs_sma50": round(trend_vs_sma50, 4)}
```

- [ ] **Step 3: Verify syntax**

Run: `python -c "import ast; ast.parse(open('recommender.py').read()); print('OK')"` from `vercel-demo/`.
Expected: `OK`.

- [ ] **Step 4: Manual trace**

Confirm by inspection: exactly 40 `UNIVERSE` entries, no duplicate
`symbol` values, no duplicate `yf_symbol` values, every entry has all four
keys (`symbol`/`yf_symbol`/`type`/`keywords`), every `type` is one of
`crypto`/`equity_us`/`equity_in`. For `_momentum_detail`: trace it against
a small rising series, e.g. `closes = [100.0 + i*0.5 for i in range(60)]`
(the same fixture Phase 1's tests used) — `return_10d = (129.5-124.5)/124.5
≈ 0.0402`, `sma_50 = mean(closes[10:60]) = 117.25`, `trend_vs_sma50 =
129.5/117.25 - 1 ≈ 0.1045` — confirm the function's arithmetic matches
`_compute_momentum`'s internal calculation of the same two quantities
(both should always agree, since they compute the identical formula).

- [ ] **Step 5: Commit**

```bash
git add vercel-demo/recommender.py
git commit -m "Expand dashboard watchlist from 8 to 40 assets, add shared momentum-detail helper"
```

---

### Task 2: `api/dashboard.py` — the dashboard data endpoint

**Files:**
- Create: `vercel-demo/api/dashboard.py`

**Interfaces:**
- Produces: `GET /api/dashboard` → `200 {"assets": [...], "failed": [...], "warning": str|null}` on success, `500 {"error": ..., "traceback": ...}` on unexpected failure. Each `assets[]` entry: `{"symbol", "type", "momentum", "momentum_detail": {"return_10d", "trend_vs_sma50"}, "sentiment", "day_change_pct", "matched_headlines": [...], "scores": {"intraday": {"score","action"}, "short_term": {...}, "swing": {...}}}`. Consumed by Task 6 (`StyleSection`/`App.jsx`) and Task 7 (`TopMovers`).

- [ ] **Step 1: Write `api/dashboard.py`**

```python
from __future__ import annotations

import json
import os
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import recommender
from sources import news as news_source
from sources import prices as prices_source

# Demo-only override: the repo's real RSS_FEEDS URLs are confirmed dead
# (feedburner.com / moneycontrol both return 0 entries). Matches the same
# override previously used in the now-removed api/recommend.py.
recommender.RSS_FEEDS = ["https://finance.yahoo.com/news/rssindex"]

STYLES = ("intraday", "short_term", "swing")


def _build_asset_result(asset, closes, headlines):
    matched = news_source.match_headlines(headlines, asset["keywords"])
    day_change_pct = round((closes[-1] - closes[-2]) / closes[-2] * 100, 2)

    scores = {}
    momentum_value = None
    sentiment_value = None
    for style in STYLES:
        scored = recommender._score_asset(asset, style, closes, matched)
        momentum_value = scored["momentum"]
        sentiment_value = scored["sentiment"]
        scores[style] = {"score": scored["score"], "action": scored["action"]}

    return {
        "symbol": asset["symbol"],
        "type": asset["type"],
        "momentum": momentum_value,
        "momentum_detail": recommender._momentum_detail(closes),
        "sentiment": sentiment_value,
        "day_change_pct": day_change_pct,
        "matched_headlines": matched,
        "scores": scores,
    }


def _fetch_one(asset):
    closes = prices_source.fetch_price_history(asset["yf_symbol"])
    return asset, closes


def build_dashboard():
    warning = None
    try:
        headlines = news_source.fetch_headlines(recommender.RSS_FEEDS)
    except RuntimeError as exc:
        headlines = []
        warning = f"News sentiment unavailable this run: {exc}"

    assets = []
    failed = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(_fetch_one, asset): asset for asset in recommender.UNIVERSE}
        for future in as_completed(futures):
            asset = futures[future]
            try:
                _, closes = future.result()
                assets.append(_build_asset_result(asset, closes, headlines))
            except Exception as exc:
                failed.append({"symbol": asset["symbol"], "error": str(exc)})

    assets.sort(key=lambda a: a["symbol"])
    failed.sort(key=lambda f: f["symbol"])
    return {"assets": assets, "failed": failed, "warning": warning}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            payload = build_dashboard()
            status = 200
        except Exception as exc:
            payload = {"error": str(exc), "traceback": traceback.format_exc()}
            status = 500

        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)
```

`ThreadPoolExecutor(max_workers=10)` parallelizes the ~40 real yfinance
fetches — sequential fetches at ~0.5-1s each could otherwise take
20-40 seconds and risk exceeding the serverless function's time limit;
10-way concurrency (I/O-bound, so threading works despite the GIL) brings
that down substantially.

- [ ] **Step 2: Verify syntax**

Run: `python -c "import ast; ast.parse(open('api/dashboard.py').read()); print('OK')"` from `vercel-demo/`.
Expected: `OK`.

- [ ] **Step 3: Manual trace**

Walk through `build_dashboard()`: if `fetch_headlines` raises, `headlines`
becomes `[]` and `warning` is set — confirm `match_headlines([], keywords)`
returns `[]` (it iterates an empty list) and `score_sentiment([])` returns
`0.0` (existing early-return), so every asset still gets a valid
(neutral-sentiment) result rather than crashing. For the per-asset loop:
if `_fetch_one` raises (bad ticker, network error), `future.result()`
re-raises inside the `try`, caught by `except Exception`, appended to
`failed` — confirm this does NOT abort the loop for other futures (each
future is handled independently via `as_completed`). Confirm
`_build_asset_result` never raises `KeyError` on `asset["keywords"]` etc.
since every `UNIVERSE` entry has all four keys (verified in Task 1).

- [ ] **Step 4: Commit**

```bash
git add vercel-demo/api/dashboard.py
git commit -m "Add GET /api/dashboard endpoint (all 3 styles + day change, per-asset failure tolerance)"
```

---

### Task 3: `api/search.py` — the search endpoint, remove superseded `api/recommend.py`

**Files:**
- Create: `vercel-demo/api/search.py`
- Delete: `vercel-demo/api/recommend.py` (fully superseded by `api/dashboard.py`; its plain-text output and single-style limitation no longer serve any purpose once the dashboard exists)

**Interfaces:**
- Produces: `GET /api/search?symbol=XXX` → `200 {"symbol", "type": null, "momentum", "momentum_detail", "sentiment", "day_change_pct", "matched_headlines", "scores": {...same 3 styles...}, "warning": str|null}` on success; `400 {"error": ...}` if `symbol` is missing/blank; `502 {"error": ...}` if the fetch/compute fails for that symbol (invalid ticker, insufficient history); `500 {"error", "traceback"}` on unexpected failure. Consumed by Task 8 (`SearchBox`).

- [ ] **Step 1: Delete the superseded endpoint**

```bash
git rm vercel-demo/api/recommend.py
```

- [ ] **Step 2: Write `api/search.py`**

```python
from __future__ import annotations

import json
import os
import re
import sys
import traceback
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import recommender
from sources import news as news_source
from sources import prices as prices_source

# Demo-only override: see api/dashboard.py for why.
recommender.RSS_FEEDS = ["https://finance.yahoo.com/news/rssindex"]

STYLES = ("intraday", "short_term", "swing")
_SUFFIX_RE = re.compile(r"\.(NS|BO)$|-USD$", re.IGNORECASE)


def search_symbol(raw_symbol: str) -> dict:
    symbol = raw_symbol.strip().upper()
    if not symbol:
        raise ValueError("No symbol provided")

    # Arbitrary symbols have no curated keyword list, so fall back to the
    # symbol text itself (suffix-stripped) as the sole match keyword. This
    # is a known, disclosed limitation: headlines usually say "Apple," not
    # "AAPL," so search sentiment will often come back neutral for tickers
    # whose symbol doesn't match how the company is written in prose.
    # Momentum-based analysis is unaffected and works for any symbol.
    keyword = _SUFFIX_RE.sub("", symbol).lower()
    asset = {"symbol": symbol, "type": None, "keywords": [keyword]}

    closes = prices_source.fetch_price_history(symbol)

    warning = None
    try:
        headlines = news_source.fetch_headlines(recommender.RSS_FEEDS)
    except RuntimeError as exc:
        headlines = []
        warning = f"News sentiment unavailable this run: {exc}"

    matched = news_source.match_headlines(headlines, asset["keywords"])
    day_change_pct = round((closes[-1] - closes[-2]) / closes[-2] * 100, 2)

    scores = {}
    momentum_value = None
    sentiment_value = None
    for style in STYLES:
        scored = recommender._score_asset(asset, style, closes, matched)
        momentum_value = scored["momentum"]
        sentiment_value = scored["sentiment"]
        scores[style] = {"score": scored["score"], "action": scored["action"]}

    return {
        "symbol": symbol,
        "type": None,
        "momentum": momentum_value,
        "momentum_detail": recommender._momentum_detail(closes),
        "sentiment": sentiment_value,
        "day_change_pct": day_change_pct,
        "matched_headlines": matched,
        "scores": scores,
        "warning": warning,
    }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        raw_symbol = query.get("symbol", [""])[0]

        try:
            if not raw_symbol.strip():
                payload = {"error": "Query parameter 'symbol' is required"}
                status = 400
            else:
                payload = search_symbol(raw_symbol)
                status = 200
        except (RuntimeError, ValueError) as exc:
            payload = {"error": str(exc)}
            status = 502
        except Exception as exc:
            payload = {"error": str(exc), "traceback": traceback.format_exc()}
            status = 500

        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)
```

- [ ] **Step 3: Verify syntax**

Run: `python -c "import ast; ast.parse(open('api/search.py').read()); print('OK')"` from `vercel-demo/`.
Expected: `OK`.

- [ ] **Step 4: Manual trace**

Trace `search_symbol("reliance.ns")`: `symbol = "RELIANCE.NS"`,
`_SUFFIX_RE.sub("", "RELIANCE.NS")` strips the `.NS` suffix → `"RELIANCE"`
→ `keyword = "reliance"`. Trace `search_symbol("btc-usd")`: strips `-USD`
→ `keyword = "btc"`. Trace an empty/whitespace symbol: raises `ValueError`
before any fetch, caught by the handler's `except (RuntimeError, ValueError)`
→ actually caught earlier by the `if not raw_symbol.strip()` branch in
`do_GET`, which returns 400 without calling `search_symbol` at all —
confirm both paths agree (empty symbol never reaches `search_symbol`).

- [ ] **Step 5: Commit**

```bash
git add vercel-demo/api/search.py
git commit -m "Add GET /api/search endpoint, remove superseded api/recommend.py"
```

---

### Task 4: Vite + React scaffold

**Files:**
- Create: `vercel-demo/package.json`
- Create: `vercel-demo/package-lock.json` (generated by `npm install`, Step 9)
- Create: `vercel-demo/vite.config.js`
- Modify: `vercel-demo/index.html` (full replace — old static landing page superseded by the React app's entry HTML)
- Create: `vercel-demo/src/main.jsx`
- Create: `vercel-demo/src/App.jsx`
- Create: `vercel-demo/src/index.css`
- Modify: `vercel-demo/vercel.json`
- Modify: `D:\ai-trader\.gitignore` (repo root, not `vercel-demo/` — add `node_modules/`/`dist/`)

**Interfaces:**
- Produces: a working `npm run build` that outputs `dist/`. `App.jsx` fetches `/api/dashboard` on mount and renders a basic loading/error/loaded state — the skeleton later tasks build on. CSS custom properties (`--bg`, `--card`, `--card-border`, `--text`, `--text-muted`, `--accent`, `--positive`, `--negative`) are the shared design tokens every later component uses.

- [ ] **Step 1: Write `package.json`**

```json
{
  "name": "quantdesk-dashboard",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.1",
    "vite": "^5.4.0"
  }
}
```

- [ ] **Step 2: Write `vite.config.js`**

```js
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
});
```

- [ ] **Step 3: Replace `index.html`**

Replace the full contents of `vercel-demo/index.html` with:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>QuantDesk Dashboard</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

- [ ] **Step 4: Write `src/main.jsx`**

```jsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

- [ ] **Step 5: Write `src/index.css`**

```css
:root {
  --bg: #07111f;
  --card: #10233c;
  --card-border: #2f4b72;
  --text: #e7eefc;
  --text-muted: #89a6c9;
  --accent: #8ecfff;
  --positive: #4ade80;
  --negative: #f87171;
  --warning: #fbbf24;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: var(--bg);
  color: var(--text);
}

#root {
  max-width: 1100px;
  margin: 0 auto;
  padding: 2rem 1.25rem 4rem;
}

.error-text {
  color: var(--negative);
}

.warning-text {
  color: var(--warning);
  font-size: 0.9rem;
}
```

- [ ] **Step 6: Write `src/App.jsx` skeleton**

```jsx
import { useEffect, useState } from "react";

export default function App() {
  const [dashboard, setDashboard] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/dashboard")
      .then((res) => res.json())
      .then((data) => {
        if (data.error) throw new Error(data.error);
        setDashboard(data);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <header style={{ marginBottom: "2rem" }}>
        <h1 style={{ marginBottom: "0.25rem" }}>QuantDesk</h1>
        <p style={{ color: "var(--text-muted)", margin: 0 }}>
          Research &amp; recommendation dashboard — live prices, live sentiment.
        </p>
      </header>
      {loading && <p>Loading live market data…</p>}
      {error && <p className="error-text">Error: {error}</p>}
      {dashboard && (
        <p style={{ color: "var(--text-muted)" }}>
          Loaded {dashboard.assets.length} assets
          {dashboard.failed.length > 0 && `, ${dashboard.failed.length} unavailable`}.
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 7: Update `vercel.json`**

Replace the full contents of `vercel-demo/vercel.json` with:

```json
{
  "framework": "vite",
  "functions": {
    "api/*.py": {
      "maxDuration": 60
    }
  }
}
```

(`maxDuration` raised from 30 to 60 — fetching ~40 real tickers even with
10-way concurrency can take longer than the old 8-asset demo did.)

- [ ] **Step 8: Exclude build artifacts from git**

The repo's top-level `.gitignore` (`D:\ai-trader\.gitignore`) currently
contains:
```
.superpowers/
dashboard.html
__pycache__/
*.pyc
```
It has no Node-related entries yet. Append two lines to it:
```
node_modules/
dist/
```

- [ ] **Step 9: Install and build — real verification**

Run from `vercel-demo/`: `npm install`
Expected: exits 0, `node_modules/` created, no errors.

Run: `npm run build`
Expected: exits 0, `dist/index.html` and `dist/assets/*.js` created, no build errors. This is real, executed verification — Node has no pandas DLL blocker.

- [ ] **Step 10: Commit**

```bash
git add .gitignore vercel-demo/package.json vercel-demo/package-lock.json vercel-demo/vite.config.js vercel-demo/index.html vercel-demo/src vercel-demo/vercel.json
git commit -m "Scaffold Vite + React app, replace static demo landing page"
```

`package-lock.json` (created by `npm install` in Step 9) is committed
alongside `package.json` for reproducible installs — confirm it exists
before this commit; if `npm install` didn't create one, run it again.

---

### Task 5: Client-side position sizing + capital input

**Files:**
- Create: `vercel-demo/src/lib/positionSizing.js`
- Create: `vercel-demo/src/components/CapitalInput.jsx`
- Modify: `vercel-demo/src/App.jsx` (add capital state, render `CapitalInput`)
- Modify: `vercel-demo/src/index.css` (append capital input styles)

**Interfaces:**
- Produces: `sizePositions(scoredAssets: {score: number, ...}[], capital: number) -> ({...,"suggested": number})[]` — the JS port of `_position_sizing`, with `MIN_TICKET = capital * 0.02` replacing the fixed ₹500 floor. Consumed by Task 6 (`StyleSection`).
- Produces: `<CapitalInput capital={number} onChange={(number) => void} />`.

- [ ] **Step 1: Write `src/lib/positionSizing.js`**

```js
const MAX_DEPLOY_PCT = 0.6;
const MAX_ALLOC_PER_IDEA = 0.2;

export function sizePositions(scoredAssets, capital) {
  const minTicket = capital * 0.02;
  const positive = scoredAssets.filter((a) => a.score > 0).map((a) => a.score);
  const totalPositive = positive.length ? positive.reduce((a, b) => a + b, 0) : 1.0;
  const deployable = capital * MAX_DEPLOY_PCT;
  const maxPerIdea = capital * MAX_ALLOC_PER_IDEA;

  return scoredAssets.map((a) => {
    let allocation = 0;
    if (a.score > 0) {
      const raw = deployable * (a.score / totalPositive);
      allocation = Math.min(maxPerIdea, raw);
      if (allocation < minTicket) allocation = 0;
    }
    return { ...a, suggested: Math.round(allocation) };
  });
}
```

- [ ] **Step 2: Write `src/components/CapitalInput.jsx`**

```jsx
export default function CapitalInput({ capital, onChange }) {
  return (
    <div className="capital-input">
      <label htmlFor="capital">Capital to deploy (₹)</label>
      <input
        id="capital"
        type="number"
        min="0"
        step="100"
        value={capital}
        onChange={(e) => onChange(Number(e.target.value) || 0)}
      />
    </div>
  );
}
```

- [ ] **Step 3: Append capital input styles to `src/index.css`**

```css
.capital-input {
  margin-bottom: 1.5rem;
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.capital-input label {
  color: var(--text-muted);
  font-size: 0.9rem;
}

.capital-input input {
  padding: 0.5rem 0.75rem;
  border-radius: 8px;
  border: 1px solid var(--card-border);
  background: var(--card);
  color: var(--text);
  font-size: 1rem;
  width: 160px;
}
```

- [ ] **Step 4: Wire `CapitalInput` into `App.jsx`**

In `src/App.jsx`, add the import and capital state, and render it between
the header and the loading/error block:

```jsx
import { useEffect, useState } from "react";
import CapitalInput from "./components/CapitalInput.jsx";
```

Add inside the component, before the `return`:
```jsx
const [capital, setCapital] = useState(25000);
```

Add right after the closing `</header>` tag, before `{loading && ...}`:
```jsx
      <CapitalInput capital={capital} onChange={setCapital} />
```

- [ ] **Step 5: Verify — real execution**

Run from `vercel-demo/`:
```bash
node --input-type=module -e "
import { sizePositions } from './src/lib/positionSizing.js';
const assets = [
  { symbol: 'A', score: 0.5 },
  { symbol: 'B', score: 0.3 },
  { symbol: 'C', score: -0.1 },
];
console.log('capital=1000:', JSON.stringify(sizePositions(assets, 1000)));
console.log('capital=25000:', JSON.stringify(sizePositions(assets, 25000)));
"
```
Expected: for `capital=1000` — `minTicket=20`, `maxPerIdea=200`,
`deployable=600`, `totalPositive=0.8`. A: `raw=600*(0.5/0.8)=375`,
`allocation=min(200,375)=200` (≥20, kept). B: `raw=600*(0.3/0.8)=225`,
`allocation=min(200,225)=200` (kept). C: score≤0 → `suggested=0`. So
**A=200, B=200, C=0** — confirming the old fixed-₹500 floor bug (which
would have zeroed everything under ₹2,500 capital) is fixed: both A and B
get real, non-zero suggested amounts at ₹1,000 capital.

Then run: `npm run build` (from Task 4's script) — confirm it still exits 0
with the new files included.

- [ ] **Step 6: Commit**

```bash
git add vercel-demo/src/lib/positionSizing.js vercel-demo/src/components/CapitalInput.jsx vercel-demo/src/App.jsx vercel-demo/src/index.css
git commit -m "Add client-side position sizing (fixes MIN_TICKET bug for small capital) and capital input"
```

---

### Task 6: The three style sections (AssetCard, WhyPanel, StyleSection)

**Files:**
- Create: `vercel-demo/src/components/AssetCard.jsx`
- Create: `vercel-demo/src/components/WhyPanel.jsx`
- Create: `vercel-demo/src/components/StyleSection.jsx`
- Modify: `vercel-demo/src/App.jsx` (add style tabs, render `StyleSection`)
- Modify: `vercel-demo/src/index.css` (append card/tab/why-panel styles)

**Interfaces:**
- Consumes: `sizePositions` (Task 5), one `assets[]` entry shape (Task 2's `/api/dashboard` response).
- Produces: `<StyleSection assets={array} style={"intraday"|"short_term"|"swing"} capital={number} />`, rendering up to 10 `<AssetCard>` sorted by that style's score. `<AssetCard asset={object} style={string} suggested={number|undefined} />` with an expandable `<WhyPanel>`.

- [ ] **Step 1: Write `src/components/WhyPanel.jsx`**

```jsx
const STYLE_LABELS = {
  intraday: "Day Trading",
  short_term: "Short-Term",
  swing: "Swing / Long-Term",
};

export default function WhyPanel({ asset, style }) {
  const styleData = asset.scores[style];

  return (
    <div className="why-panel">
      <div className="why-row">
        <span className="why-label">Momentum</span>
        <span className="why-value">{(asset.momentum * 100).toFixed(1)}%</span>
        <span className="why-detail">
          10-day return {(asset.momentum_detail.return_10d * 100).toFixed(1)}%, vs 50-day
          average {(asset.momentum_detail.trend_vs_sma50 * 100).toFixed(1)}%
        </span>
      </div>
      <div className="why-row">
        <span className="why-label">Sentiment</span>
        <span className="why-value">{asset.sentiment.toFixed(3)}</span>
        <span className="why-detail">
          {asset.matched_headlines.length > 0
            ? `From ${asset.matched_headlines.length} matched headline${asset.matched_headlines.length === 1 ? "" : "s"}`
            : "No matching headlines this run — neutral by default, not an error"}
        </span>
      </div>
      {asset.matched_headlines.length > 0 && (
        <ul className="why-headlines">
          {asset.matched_headlines.slice(0, 5).map((h, i) => (
            <li key={i}>{h.title}</li>
          ))}
        </ul>
      )}
      <div className="why-row">
        <span className="why-label">{STYLE_LABELS[style]} score</span>
        <span className="why-value">{styleData.score.toFixed(3)}</span>
        <span className="why-detail">
          Momentum × style weight + sentiment × style weight, threshold 0.15 for "Research LONG"
        </span>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Write `src/components/AssetCard.jsx`**

```jsx
import { useState } from "react";
import WhyPanel from "./WhyPanel.jsx";

const TYPE_LABELS = {
  crypto: "Crypto",
  equity_us: "US Equity",
  equity_in: "Indian Equity",
};

const ACTION_COLORS = {
  "Research LONG": "var(--positive)",
  Watchlist: "var(--text-muted)",
};

export default function AssetCard({ asset, style, suggested }) {
  const [expanded, setExpanded] = useState(false);
  const styleData = asset.scores[style];

  return (
    <div className="asset-card">
      <div className="asset-card-row" onClick={() => setExpanded(!expanded)}>
        <div className="asset-card-main">
          <span className="asset-symbol">{asset.symbol}</span>
          {asset.type && <span className="asset-type">{TYPE_LABELS[asset.type] || asset.type}</span>}
        </div>
        <div className="asset-card-stats">
          <span className="asset-score">{styleData.score.toFixed(3)}</span>
          {suggested !== undefined && (
            <span className="asset-suggested">
              {suggested > 0 ? `₹${suggested.toLocaleString("en-IN")}` : "—"}
            </span>
          )}
          <span
            className="asset-action"
            style={{ color: ACTION_COLORS[styleData.action] || "var(--text-muted)" }}
          >
            {styleData.action}
          </span>
          <span className="asset-expand-icon">{expanded ? "▲" : "▼"}</span>
        </div>
      </div>
      {expanded && <WhyPanel asset={asset} style={style} />}
    </div>
  );
}
```

- [ ] **Step 3: Write `src/components/StyleSection.jsx`**

```jsx
import AssetCard from "./AssetCard.jsx";
import { sizePositions } from "../lib/positionSizing.js";

export default function StyleSection({ assets, style, capital }) {
  const ranked = [...assets]
    .sort((a, b) => b.scores[style].score - a.scores[style].score)
    .slice(0, 10)
    .map((a) => ({ ...a, score: a.scores[style].score }));

  const sized = sizePositions(ranked, capital);

  return (
    <div className="style-section">
      {sized.map((asset) => (
        <AssetCard key={asset.symbol} asset={asset} style={style} suggested={asset.suggested} />
      ))}
    </div>
  );
}
```

Note: `.map((a) => ({ ...a, score: a.scores[style].score }))` copies the
active style's score onto a flat `score` field — `sizePositions` (Task 5)
reads `a.score`, but the asset objects from `/api/dashboard` only carry
per-style scores nested under `a.scores[style].score`. This bridges the
two shapes without modifying `sizePositions` itself.

- [ ] **Step 4: Append card/tab/why-panel styles to `src/index.css`**

```css
.app-header h1 {
  margin: 0 0 0.25rem;
  font-size: 2rem;
  background: linear-gradient(135deg, var(--accent), #c084fc);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.tabs {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
  border-bottom: 1px solid var(--card-border);
  padding-bottom: 0.5rem;
  flex-wrap: wrap;
}

.tab {
  padding: 0.5rem 1rem;
  border-radius: 8px;
  border: 1px solid transparent;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 0.9rem;
}

.tab.active {
  background: var(--card);
  border-color: var(--card-border);
  color: var(--text);
}

.style-section {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.asset-card {
  background: var(--card);
  border: 1px solid var(--card-border);
  border-radius: 10px;
  overflow: hidden;
}

.asset-card-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.85rem 1rem;
  cursor: pointer;
  gap: 1rem;
  flex-wrap: wrap;
}

.asset-card-main {
  display: flex;
  align-items: baseline;
  gap: 0.6rem;
}

.asset-symbol {
  font-weight: 700;
  font-size: 1.05rem;
}

.asset-type {
  font-size: 0.75rem;
  color: var(--text-muted);
  background: rgba(142, 207, 255, 0.1);
  padding: 0.1rem 0.5rem;
  border-radius: 999px;
}

.asset-card-stats {
  display: flex;
  align-items: center;
  gap: 1rem;
  font-size: 0.9rem;
}

.asset-score {
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
}

.asset-suggested {
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.asset-action {
  font-weight: 600;
  min-width: 8rem;
  text-align: right;
}

.asset-expand-icon {
  color: var(--text-muted);
  font-size: 0.7rem;
}

.why-panel {
  padding: 0 1rem 1rem;
  border-top: 1px solid var(--card-border);
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  font-size: 0.85rem;
}

.why-row {
  display: grid;
  grid-template-columns: 8rem 5rem 1fr;
  gap: 0.5rem;
  align-items: baseline;
  padding-top: 0.5rem;
}

.why-label {
  color: var(--text-muted);
}

.why-value {
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.why-detail {
  color: var(--text-muted);
}

.why-headlines {
  margin: 0;
  padding-left: 1.2rem;
  color: var(--text-muted);
}

@media (max-width: 640px) {
  .why-row {
    grid-template-columns: 1fr;
  }
  .asset-action {
    min-width: auto;
  }
}
```

- [ ] **Step 5: Wire tabs + `StyleSection` into `App.jsx`**

Replace the full contents of `src/App.jsx` with:

```jsx
import { useEffect, useState } from "react";
import CapitalInput from "./components/CapitalInput.jsx";
import StyleSection from "./components/StyleSection.jsx";

const TABS = [
  { key: "intraday", label: "Day Trading" },
  { key: "short_term", label: "Short-Term" },
  { key: "swing", label: "Swing / Long-Term" },
];

export default function App() {
  const [dashboard, setDashboard] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [capital, setCapital] = useState(25000);
  const [activeTab, setActiveTab] = useState("intraday");

  useEffect(() => {
    fetch("/api/dashboard")
      .then((res) => res.json())
      .then((data) => {
        if (data.error) throw new Error(data.error);
        setDashboard(data);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <header className="app-header">
        <h1>QuantDesk</h1>
        <p style={{ color: "var(--text-muted)", margin: 0 }}>
          Research &amp; recommendation dashboard — live prices, live sentiment.
        </p>
      </header>

      <CapitalInput capital={capital} onChange={setCapital} />

      {loading && <p>Loading live market data…</p>}
      {error && <p className="error-text">Error: {error}</p>}

      {dashboard && dashboard.warning && <p className="warning-text">{dashboard.warning}</p>}
      {dashboard && dashboard.failed.length > 0 && (
        <p className="warning-text">
          {dashboard.failed.length} asset(s) unavailable this run:{" "}
          {dashboard.failed.map((f) => f.symbol).join(", ")}
        </p>
      )}

      {dashboard && (
        <>
          <nav className="tabs">
            {TABS.map((tab) => (
              <button
                key={tab.key}
                className={activeTab === tab.key ? "tab active" : "tab"}
                onClick={() => setActiveTab(tab.key)}
              >
                {tab.label}
              </button>
            ))}
          </nav>
          <StyleSection assets={dashboard.assets} style={activeTab} capital={capital} />
        </>
      )}
    </div>
  );
}
```

(This task's `TABS` has 3 entries; Task 7 adds the 4th "Top Movers" tab.)

- [ ] **Step 6: Verify — real build**

Run from `vercel-demo/`: `npm run build`
Expected: exits 0, no errors.

- [ ] **Step 7: Commit**

```bash
git add vercel-demo/src/components/AssetCard.jsx vercel-demo/src/components/WhyPanel.jsx vercel-demo/src/components/StyleSection.jsx vercel-demo/src/App.jsx vercel-demo/src/index.css
git commit -m "Add the 3 style-ranked sections (Day Trading, Short-Term, Swing) with expandable why panels"
```

---

### Task 7: Top Movers section

**Files:**
- Create: `vercel-demo/src/components/TopMovers.jsx`
- Modify: `vercel-demo/src/App.jsx` (add 4th tab, branch render logic)
- Modify: `vercel-demo/src/index.css` (append movers styles)

**Interfaces:**
- Produces: `<TopMovers assets={array} />` — no capital/sizing involved (day_change_pct isn't a conviction score, sizing on it would be meaningless — see spec).

- [ ] **Step 1: Write `src/components/TopMovers.jsx`**

```jsx
export default function TopMovers({ assets }) {
  const gainers = [...assets].sort((a, b) => b.day_change_pct - a.day_change_pct).slice(0, 10);
  const losers = [...assets].sort((a, b) => a.day_change_pct - b.day_change_pct).slice(0, 10);

  return (
    <div className="top-movers">
      <div className="movers-column">
        <h3>Top Gainers</h3>
        {gainers.map((a) => (
          <div key={a.symbol} className="mover-row">
            <span className="asset-symbol">{a.symbol}</span>
            <span className="mover-pct positive">+{a.day_change_pct.toFixed(2)}%</span>
          </div>
        ))}
      </div>
      <div className="movers-column">
        <h3>Top Losers</h3>
        {losers.map((a) => (
          <div key={a.symbol} className="mover-row">
            <span className="asset-symbol">{a.symbol}</span>
            <span className="mover-pct negative">{a.day_change_pct.toFixed(2)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Append movers styles to `src/index.css`**

```css
.top-movers {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
}

.movers-column h3 {
  margin: 0 0 0.5rem;
  font-size: 1rem;
  color: var(--text-muted);
}

.mover-row {
  display: flex;
  justify-content: space-between;
  padding: 0.5rem 0.75rem;
  background: var(--card);
  border: 1px solid var(--card-border);
  border-radius: 8px;
  margin-bottom: 0.4rem;
}

.mover-pct.positive {
  color: var(--positive);
  font-weight: 600;
}

.mover-pct.negative {
  color: var(--negative);
  font-weight: 600;
}

@media (max-width: 640px) {
  .top-movers {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 3: Add the 4th tab and branch rendering in `App.jsx`**

In `src/App.jsx`, add the import:
```jsx
import TopMovers from "./components/TopMovers.jsx";
```

Replace the `TABS` array with:
```jsx
const TABS = [
  { key: "intraday", label: "Day Trading" },
  { key: "short_term", label: "Short-Term" },
  { key: "swing", label: "Swing / Long-Term" },
  { key: "movers", label: "Top Movers" },
];
```

Replace the line `<StyleSection assets={dashboard.assets} style={activeTab} capital={capital} />` with:
```jsx
          {activeTab === "movers" ? (
            <TopMovers assets={dashboard.assets} />
          ) : (
            <StyleSection assets={dashboard.assets} style={activeTab} capital={capital} />
          )}
```

- [ ] **Step 4: Verify — real build**

Run from `vercel-demo/`: `npm run build`
Expected: exits 0, no errors.

- [ ] **Step 5: Commit**

```bash
git add vercel-demo/src/components/TopMovers.jsx vercel-demo/src/App.jsx vercel-demo/src/index.css
git commit -m "Add Top Movers section (gainers/losers by today's % change, no sizing)"
```

---

### Task 8: Search box

**Files:**
- Create: `vercel-demo/src/components/SearchBox.jsx`
- Modify: `vercel-demo/src/App.jsx` (render `SearchBox`)
- Modify: `vercel-demo/src/index.css` (append search styles)

**Interfaces:**
- Consumes: `GET /api/search?symbol=...` (Task 3), `<AssetCard>` (Task 6).
- Produces: `<SearchBox />` — self-contained, no props needed (manages its own query/result/error state).

- [ ] **Step 1: Write `src/components/SearchBox.jsx`**

```jsx
import { useState } from "react";
import AssetCard from "./AssetCard.jsx";

const STYLES = ["intraday", "short_term", "swing"];

export default function SearchBox() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch(`/api/search?symbol=${encodeURIComponent(query.trim())}`);
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="search-box">
      <form onSubmit={handleSearch}>
        <input
          type="text"
          placeholder="Search any symbol (e.g. AAPL, RELIANCE.NS, BTC-USD)"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button type="submit" disabled={loading}>
          {loading ? "Searching…" : "Search"}
        </button>
      </form>
      {error && <p className="error-text">{error}</p>}
      {result && result.warning && <p className="warning-text">{result.warning}</p>}
      {result && (
        <div className="search-results">
          {STYLES.map((style) => (
            <AssetCard key={style} asset={result} style={style} suggested={undefined} />
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Append search styles to `src/index.css`**

```css
.search-box {
  margin-bottom: 1.5rem;
}

.search-box form {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.search-box input[type="text"] {
  flex: 1;
  min-width: 200px;
  padding: 0.65rem 0.9rem;
  border-radius: 8px;
  border: 1px solid var(--card-border);
  background: var(--card);
  color: var(--text);
  font-size: 0.95rem;
}

.search-box button {
  padding: 0.65rem 1.25rem;
  border-radius: 8px;
  border: none;
  background: var(--accent);
  color: #07111f;
  font-weight: 600;
  cursor: pointer;
}

.search-box button:disabled {
  opacity: 0.6;
  cursor: default;
}

.search-results {
  margin-top: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
```

- [ ] **Step 3: Render `SearchBox` in `App.jsx`**

In `src/App.jsx`, add the import:
```jsx
import SearchBox from "./components/SearchBox.jsx";
```

Add `<SearchBox />` right after the closing `</header>` tag, before `<CapitalInput ...>`:
```jsx
      <SearchBox />
```

- [ ] **Step 4: Verify — real build**

Run from `vercel-demo/`: `npm run build`
Expected: exits 0, no errors.

- [ ] **Step 5: Commit**

```bash
git add vercel-demo/src/components/SearchBox.jsx vercel-demo/src/App.jsx vercel-demo/src/index.css
git commit -m "Add any-symbol search box with cross-style why breakdown"
```

---

### Task 9: Final polish and manual verification checklist

**Files:** None new — final review pass over what's already built.

**Interfaces:** None.

- [ ] **Step 1: Confirm `.gitignore` excludes build artifacts**

Check `D:\ai-trader\.gitignore` contains the `node_modules/` and `dist/`
lines added in Task 4, Step 8. Run `git status` from `vercel-demo/` and
confirm neither directory appears as untracked-to-be-added.

- [ ] **Step 2: Full real build, one more time**

Run from `vercel-demo/`: `rm -rf node_modules dist && npm install && npm run build`
Expected: exits 0 end to end, confirming a completely fresh install still
builds cleanly (catches any accidental reliance on stale local state).

- [ ] **Step 3: Python syntax check across all modified/new backend files**

Run from `vercel-demo/`:
```bash
python -c "
import ast
for f in ['recommender.py', 'api/dashboard.py', 'api/search.py']:
    ast.parse(open(f).read())
    print(f, 'OK')
"
```
Expected: all three print `OK`.

- [ ] **Step 4: Manual verification checklist (for the human partner, once deployed)**

Document this checklist in the task report — actually running it requires
the live Vercel URL, which is outside this session's reach (deployment is
the human partner's step, same as Phase 1):

1. Load the dashboard root URL — confirm it shows the QuantDesk header,
   search box, capital input (default ₹25,000), and 4 tabs.
2. Confirm all 4 tabs populate with ranked cards (or a clear "N unavailable"
   note if some assets failed to fetch — not a blank/broken page).
3. Change the capital input to `1000` — confirm suggested ₹ amounts update
   **instantly** (no loading spinner, no network tab activity) and are
   non-zero for the top-ranked ideas (confirms the MIN_TICKET fix works
   live, not just in the Task 5 Node check).
4. Click an asset card — confirm the why panel expands showing momentum
   detail, sentiment, and matched headlines (or the "no matching headlines"
   note).
5. Search a watchlist symbol (e.g. `NVDA`) — confirm 3 result cards appear
   (one per style) with real data.
6. Search a non-watchlist symbol (e.g. `PLTR` or `WIPRO.NS` if not in the
   list) — confirm it still returns real momentum data, likely with a
   "no matching headlines" sentiment note.
7. Search a deliberately invalid symbol (e.g. `ZZZZZZZ`) — confirm a clear
   error message appears, not a crash or blank state.

- [ ] **Step 5: Report results**

Summarize in the task report: build status (Steps 2-3), and that Step 4's
checklist is documented for the human partner to run post-deployment. No
commit needed for this task beyond what Steps 1 already covers (a
`.gitignore` fix, if one was needed).
