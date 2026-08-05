# Momentum-Based Short-Term Screener Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the live half of the Momentum-Based Short-Term Screener described in
`docs/superpowers/specs/2026-08-05-momentum-screener-design.md` — an NSE data source,
quality-gated scoring, a daily cron job caching results in Postgres, and a 5-tab UI
(Screener + 1D/3D/7D/1M Movers) reading that cache. The Backtest tab is a separate,
later plan that reuses this plan's scoring module.

**Architecture:** A daily Vercel Cron job (`api/cron/momentum_screen.py`) fetches NSE
bulk data (`sources/nse.py`) and per-symbol OHLCV/fundamentals (extended
`sources/prices.py` + yfinance `.info`) for the Nifty 200, scores each symbol via pure
functions in `momentum_screen.py`, and writes one row per symbol to a new
`momentum_rankings` Postgres table. `api/momentum.py` reads that cache — no live
fetching on the request path. The frontend adds a new "Momentum" top-level tab whose
own sub-navigation switches between the 5 views, all backed by the same cached rows.

**Tech Stack:** Python (`http.server.BaseHTTPRequestHandler`, matching every existing
`vercel-demo/api/*.py` file), `requests` (new dependency, for NSE's cookie/session
dance), `psycopg2` (existing), React (existing).

## Global Constraints

- **No pandas/psycopg2 execution on the dev machine.** A Windows Application Control
  Policy blocks their compiled DLLs. `sources/nse.py` and `momentum_screen.py` are
  deliberately written with zero pandas/psycopg2 imports (`requests` + stdlib `csv`/
  `io` only) specifically so they can be executed for real on this machine — treat that
  as a hard requirement, not a nice-to-have, when implementing them. Every other file
  in this plan (`sources/prices.py`, `api/cron/momentum_screen.py`, `api/momentum.py`)
  imports yfinance/psycopg2 transitively and must be verified via `ast.parse` plus
  careful manual tracing only, never real execution.
- **NSE endpoint confidence varies.** The Nifty 200 constituent list and F&O ban list
  URLs are long-standing, widely-referenced endpoints. The ASM/GSM list URLs used in
  Task 1 are a best-effort guess at NSE's URL pattern, not independently confirmed —
  this must be called out explicitly in that task's manual-verification step and
  flagged to the human partner as something to confirm against NSE's live site at
  first deployment, the same way the Holdings/Watchlist plan flagged the unknown
  Postgres env var name rather than guessing silently.
- **NSE may block Vercel's IP entirely** — every NSE-sourced function must degrade to
  raising a catchable exception (never crash the whole cron run), matching the
  established per-symbol failure-tolerance pattern already used throughout this app.
- **Momentum rankings are public, not per-device data** — `api/momentum.py` does NOT
  require `X-Device-Id` (unlike holdings/watchlist), matching `api/dashboard.py`'s
  existing no-auth pattern. The frontend uses plain `fetch()`, not `apiFetch`.
- **Scoring weights, gate thresholds, and tab structure are fixed by the spec** — use
  the exact values from `docs/superpowers/specs/2026-08-05-momentum-screener-design.md`
  (30/25/15/10/10/5/5 weighting, ₹5,000 Cr market cap, 40% promoter holding, <1.0 debt-
  to-equity, EMA20/50 trend gate, 5%/10-15% stop-loss/target) — do not invent different
  numbers.

---

### Task 1: NSE data source (`sources/nse.py`)

**Files:**
- Create: `vercel-demo/sources/nse.py`
- Modify: `vercel-demo/requirements.txt`

**Interfaces:**
- Produces: `fetch_nifty200_symbols() -> List[str]` (bare NSE symbols, e.g. `"RELIANCE"`).
- Produces: `fetch_fo_ban_symbols() -> Set[str]` (bare symbols currently in F&O ban).
- Produces: `fetch_asm_symbols() -> Set[str]`, `fetch_gsm_symbols() -> Set[str]`.
- Produces: `fetch_bhavcopy(trading_date: datetime.date) -> Dict[str, Dict[str, float]]`
  — `{bare_symbol: {"volume": float, "delivery_pct": float}}` for every NSE symbol in
  that day's bhavcopy.
- Produces: `latest_trading_day() -> datetime.date` — today if before/at NSE's
  bhavcopy-publish cutover, else falls back by one day at a time until a bhavcopy fetch
  succeeds (weekends/holidays have no bhavcopy).
- Consumed by: Task 4 (`api/cron/momentum_screen.py`).

- [ ] **Step 1: Add `requests` to `requirements.txt`**

Add this line to `vercel-demo/requirements.txt` (already contains `yfinance`,
`feedparser`, `vaderSentiment`, `psycopg2-binary`):
```
requests>=2.31
```
`requests` is already an installed transitive dependency of `yfinance`, so this makes
an existing dependency explicit rather than adding new install weight.

- [ ] **Step 2: Write `sources/nse.py`**

```python
from __future__ import annotations

import csv
import datetime
import io
from typing import Dict, List, Set

import requests

_BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/csv,application/csv,*/*",
}

_HOMEPAGE_URL = "https://www.nseindia.com/"
_NIFTY200_URL = "https://archives.nseindia.com/content/indices/ind_nifty200list.csv"
_FO_BAN_URL = "https://nsearchives.nseindia.com/content/fo/fo_secban.csv"
# NOTE: these two ASM/GSM URLs follow NSE's established archives.nseindia.com /
# nsearchives.nseindia.com path convention but are NOT independently confirmed against
# the live site from this environment. Verify these against NSE's current Surveillance
# pages at first deployment and update here if they've moved — same category of
# "confirm at setup time, don't trust a guess" caveat as this project's Postgres env
# var name.
_ASM_URL = "https://nsearchives.nseindia.com/content/equities/asmStage1List.csv"
_GSM_URL = "https://nsearchives.nseindia.com/content/equities/gsmStage1List.csv"
_BHAVCOPY_URL_TEMPLATE = (
    "https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{ddmmyyyy}.csv"
)


def _new_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(_BASE_HEADERS)
    # NSE's data endpoints commonly reject requests with no prior cookie —
    # a plain GET to the homepage first is the standard workaround. This
    # may still fail if NSE blocks the requesting IP outright regardless
    # of cookies/headers (see the design spec's Risks section) — that
    # shows up as a non-2xx status or a connection error either way, and
    # every public function in this module raises RuntimeError for both.
    try:
        session.get(_HOMEPAGE_URL, timeout=10)
    except requests.RequestException as exc:
        raise RuntimeError(f"Failed to establish an NSE session: {exc}") from exc
    return session


def _fetch_csv_rows(session: requests.Session, url: str) -> List[Dict[str, str]]:
    try:
        response = session.get(url, timeout=15)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Failed to fetch {url!r}: {exc}") from exc
    reader = csv.DictReader(io.StringIO(response.text))
    return [{(k or "").strip(): (v or "").strip() for k, v in row.items()} for row in reader]


def fetch_nifty200_symbols() -> List[str]:
    session = _new_session()
    rows = _fetch_csv_rows(session, _NIFTY200_URL)
    symbols = [row["Symbol"] for row in rows if row.get("Symbol")]
    if not symbols:
        raise RuntimeError("Nifty 200 constituent list was empty or malformed")
    return symbols


def _first_column_symbols(rows: List[Dict[str, str]]) -> Set[str]:
    # Ban/surveillance list exports have varied their header text across
    # NSE's own revisions over time; the symbol is reliably the first
    # column regardless of what that column is named that day.
    symbols: Set[str] = set()
    for row in rows:
        values = list(row.values())
        if values and values[0]:
            symbols.add(values[0].strip().upper())
    return symbols


def fetch_fo_ban_symbols() -> Set[str]:
    session = _new_session()
    rows = _fetch_csv_rows(session, _FO_BAN_URL)
    return _first_column_symbols(rows)


def fetch_asm_symbols() -> Set[str]:
    session = _new_session()
    rows = _fetch_csv_rows(session, _ASM_URL)
    return _first_column_symbols(rows)


def fetch_gsm_symbols() -> Set[str]:
    session = _new_session()
    rows = _fetch_csv_rows(session, _GSM_URL)
    return _first_column_symbols(rows)


def fetch_bhavcopy(trading_date: datetime.date) -> Dict[str, Dict[str, float]]:
    url = _BHAVCOPY_URL_TEMPLATE.format(ddmmyyyy=trading_date.strftime("%d%m%Y"))
    session = _new_session()
    rows = _fetch_csv_rows(session, url)
    if not rows:
        raise RuntimeError(f"Bhavcopy for {trading_date.isoformat()} was empty")

    result: Dict[str, Dict[str, float]] = {}
    for row in rows:
        symbol = row.get("SYMBOL", "").strip().upper()
        if not symbol:
            continue
        try:
            volume = float(row.get("TTL_TRD_QNTY", "0").replace(",", "") or 0)
            delivery_pct = float(row.get("DELIV_PER", "0").replace(",", "") or 0)
        except ValueError:
            continue
        result[symbol] = {"volume": volume, "delivery_pct": delivery_pct}
    return result


def latest_trading_day(today: datetime.date | None = None) -> datetime.date:
    """Walk backward from today until a bhavcopy fetch succeeds (skips
    weekends/holidays, which have no bhavcopy file)."""
    candidate = today or datetime.date.today()
    for _ in range(10):  # NSE holidays never run more than a few days consecutively
        try:
            fetch_bhavcopy(candidate)
            return candidate
        except RuntimeError:
            candidate -= datetime.timedelta(days=1)
    raise RuntimeError("Could not find a valid NSE trading day with a bhavcopy in the last 10 days")
```

- [ ] **Step 3: Verify — real execution (this file has no pandas/psycopg2 dependency)**

Run from `vercel-demo/`:
```bash
python -c "import sources.nse; print('import OK')"
```
Expected: `import OK` (confirms the module has no syntax errors and all imports
resolve — `requests` must already be installed in this environment for the import
itself to succeed; if it's not yet installed, run `pip install requests` first, matching
`ast.parse`-level confidence otherwise).

This module's *network calls* cannot be exercised from this environment (no live
internet-dependent test in this session, and even if there were, NSE's anti-bot
behavior is exactly the thing under question) — but unlike every other backend file in
this project, the import and function-definition correctness of this specific file
*can* be verified for real, since it has no pandas/psycopg2 dependency. Take advantage
of that: also run
```bash
python -c "
import sources.nse as nse
import inspect
for name in ('fetch_nifty200_symbols', 'fetch_fo_ban_symbols', 'fetch_asm_symbols', 'fetch_gsm_symbols', 'fetch_bhavcopy', 'latest_trading_day'):
    assert hasattr(nse, name), f'{name} missing'
    print(name, inspect.signature(getattr(nse, name)))
"
```
Expected: all 6 functions print their signature with no `AssertionError`.

- [ ] **Step 4: Manual trace**

Trace `_first_column_symbols` with a row like `{"SYMBOL ": "RELIANCE", "SERIES": "EQ"}`
(note the stripped key from `_fetch_csv_rows`) → `list(row.values())[0]` is `"RELIANCE"`
→ added to the set uppercased. Trace `fetch_bhavcopy` with a row missing `DELIV_PER`
→ `.get("DELIV_PER", "0")` returns `"0"` → `float("0")` succeeds → `delivery_pct: 0.0`,
not a crash. Trace `latest_trading_day` when today is a Sunday with no bhavcopy →
`fetch_bhavcopy` raises `RuntimeError` → loop decrements to Saturday → still fails →
Friday → succeeds (assuming Friday was a trading day) → returns Friday's date.

- [ ] **Step 5: Commit**

```bash
git add sources/nse.py requirements.txt
git commit -m "Add NSE data source: Nifty 200, F&O ban, ASM/GSM, bhavcopy"
```

---

### Task 2: Extend price fetching for OHLCV (`sources/prices.py`)

**Files:**
- Modify: `vercel-demo/sources/prices.py`

**Interfaces:**
- Produces: `fetch_ohlcv_history(yf_symbol: str, period: str = "6mo") -> Dict[str, List[float]]`
  — keys `"open"`, `"high"`, `"low"`, `"close"`, `"volume"`, each a same-length,
  index-aligned list (index 0 = oldest, index -1 = most recent).
- Modifies: `fetch_price_history` — same signature and behavior as before (existing
  callers in `recommender.py`, `api/dashboard.py`, `api/search.py`, `api/holdings.py`,
  `api/watchlist.py` are unaffected), now implemented as a thin wrapper over
  `fetch_ohlcv_history` instead of independently calling `yf.download`.
- Consumed by: Task 4 (`api/cron/momentum_screen.py`).

- [ ] **Step 1: Rewrite `sources/prices.py`**

```python
from __future__ import annotations

from typing import Dict, List

import yfinance as yf

_COLUMNS = (("open", "Open"), ("high", "High"), ("low", "Low"), ("close", "Close"), ("volume", "Volume"))


def fetch_ohlcv_history(yf_symbol: str, period: str = "6mo") -> Dict[str, List[float]]:
    try:
        data = yf.download(yf_symbol, period=period, progress=False)
    except Exception as exc:
        raise RuntimeError(f"Failed to fetch price history for {yf_symbol!r}: {exc}") from exc

    if data is None or getattr(data, "empty", True):
        raise RuntimeError(f"No price data returned for {yf_symbol!r} (period={period!r})")

    raw: Dict[str, List[float]] = {}
    for label, column in _COLUMNS:
        try:
            series = data[column]
        except KeyError:
            raise RuntimeError(f"No {column!r} column in price data for {yf_symbol!r}") from None
        if hasattr(series, "columns"):
            # Some yfinance versions return a single-column DataFrame here
            # instead of a Series even for one symbol — flatten it.
            series = series.iloc[:, 0]
        raw[label] = [float(value) for value in series.tolist()]

    # Demo-only relaxation (unchanged from the original close-only
    # version): drop rows where Close is NaN rather than aborting the
    # whole ranking run. Row selection is driven by Close alone, matching
    # the pre-OHLCV behavior exactly, so existing close-only callers see
    # no behavior change. Open/High/Low/Volume are carried along using
    # the same row selection — callers using those columns must tolerate
    # an occasional stray NaN on a day Close happened to be valid.
    valid_rows = [i for i, close in enumerate(raw["close"]) if close == close]  # NaN != NaN
    result = {label: [raw[label][i] for i in valid_rows] for label, _ in _COLUMNS}
    if not result["close"]:
        raise RuntimeError(f"Price data for {yf_symbol!r} is entirely NaN")
    return result


def fetch_price_history(yf_symbol: str, period: str = "6mo") -> List[float]:
    return fetch_ohlcv_history(yf_symbol, period)["close"]
```

- [ ] **Step 2: Verify syntax**

Run: `python -c "import ast; ast.parse(open('sources/prices.py').read()); print('OK')"`
from `vercel-demo/`. Expected: `OK`. (Real execution is not possible — `yfinance`
imports `pandas`, blocked on this machine.)

- [ ] **Step 3: Manual trace**

Trace `fetch_price_history("RELIANCE.NS")` end to end: calls
`fetch_ohlcv_history("RELIANCE.NS", "6mo")["close"]` → identical closes list to the
pre-refactor version, since `valid_rows` selection is unchanged (still driven by
`close == close` only) → confirms zero behavior change for every existing caller.
Trace a row where `Close` is valid but `Volume` is NaN → that row is *kept* (mask is
close-only) → `result["volume"][i]` is `NaN` at that index → any consumer of `volume`
(Task 3's `momentum_screen.py`) must tolerate this, which the `compute_volume_increase`
and `compute_volume_confirmation` functions in Task 3 are written to do (they operate
on raw floats and don't special-case NaN beyond what Python's arithmetic already does —
confirm in Task 3's trace that a stray NaN volume doesn't crash, only produces a
NaN-tainted output for that one derived value, which Task 4's per-symbol try/except
already isolates from the rest of the batch).

- [ ] **Step 4: Commit**

```bash
git add sources/prices.py
git commit -m "Extend price fetching to full OHLCV, refactor close-only path onto it"
```

---

### Task 3: Scoring & quality-filter module (`momentum_screen.py`)

**Files:**
- Create: `vercel-demo/momentum_screen.py`

**Interfaces:**
- Produces: `compute_ema_trend(closes) -> dict`, `compute_rsi(closes, period=14) -> float`,
  `compute_returns(closes) -> dict`, `compute_volume_increase(volumes, lookback=10) -> float`,
  `compute_volume_confirmation(closes, volumes, deliveries, lookback=3) -> str`,
  `evaluate_quality_gates(fundamentals, nse_flags, avg_daily_traded_value) -> dict`,
  `compute_risk_management(entry_price) -> dict`, `build_symbol_metrics(...) -> dict`,
  `compute_momentum_scores(pool) -> dict`.
- Consumed by: Task 4 (`api/cron/momentum_screen.py`).
- This file has **zero pandas/psycopg2/yfinance/requests imports** — pure functions
  over plain Python lists/dicts/floats. This is deliberate: it is the one file in this
  whole feature that can be verified with real `pytest`-style execution on this dev
  machine.

- [ ] **Step 1: Write `momentum_screen.py`**

```python
from __future__ import annotations

from typing import Dict, List, Optional

UNKNOWN = "unknown"


# --- Trend & momentum indicators -------------------------------------------

def _ema_series(values: List[float], period: int) -> List[float]:
    multiplier = 2 / (period + 1)
    ema_values = [sum(values[:period]) / period]
    for value in values[period:]:
        ema_values.append((value - ema_values[-1]) * multiplier + ema_values[-1])
    return ema_values


def compute_ema_trend(closes: List[float]) -> Dict[str, object]:
    if len(closes) < 50:
        raise ValueError(f"Need at least 50 closes for EMA20/50 trend, got {len(closes)}")
    ema20 = _ema_series(closes, 20)[-1]
    ema50 = _ema_series(closes, 50)[-1]
    price = closes[-1]
    passes = price > ema20 and price > ema50 and ema20 > ema50
    return {"ema20": round(ema20, 2), "ema50": round(ema50, 2), "price": round(price, 2), "passes": passes}


def compute_rsi(closes: List[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        raise ValueError(f"Need at least {period + 1} closes for RSI{period}, got {len(closes)}")
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(d, 0.0) for d in deltas]
    losses = [max(-d, 0.0) for d in deltas]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for gain, loss in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def _rsi_factor_score(rsi: float) -> float:
    """1.0 at the center of the strategy's 55-70 'sweet spot' band, tapering
    to 0 outside a wider window either side."""
    center, half_width = 62.5, 7.5
    if 55 <= rsi <= 70:
        return round(1.0 - 0.3 * (abs(rsi - center) / half_width), 4)
    if rsi < 55:
        return round(max(0.0, 0.7 * (rsi - 30) / 25), 4)
    return round(max(0.0, 0.7 * (100 - rsi) / 30), 4)


def compute_returns(closes: List[float]) -> Dict[str, float]:
    if len(closes) < 23:  # ~1 month of trading days, with headroom
        raise ValueError(f"Need at least 23 closes for return calculations, got {len(closes)}")

    def _return(days_back: int) -> float:
        return round((closes[-1] - closes[-1 - days_back]) / closes[-1 - days_back], 4)

    return {
        "return_1d": _return(1),
        "return_3d": _return(3),
        "return_7d": _return(7),
        "return_1m": _return(21),  # ~21 trading days per calendar month
    }


# --- Volume ------------------------------------------------------------

def compute_volume_increase(volumes: List[float], lookback: int = 10) -> float:
    if len(volumes) < lookback + 1:
        raise ValueError(f"Need at least {lookback + 1} volume points, got {len(volumes)}")
    recent_avg = sum(volumes[-lookback:]) / lookback
    today = volumes[-1]
    if recent_avg == 0 or recent_avg != recent_avg or today != today:  # guards NaN/zero
        return 0.0
    return round((today - recent_avg) / recent_avg, 4)


def compute_volume_confirmation(
    closes: List[float],
    volumes: List[float],
    deliveries: Optional[List[float]],
    lookback: int = 3,
) -> str:
    """"full" | "partial" | "none" — rising price + rising volume + rising
    delivery % over the recent window (delivery % is optional: bhavcopy
    only carries the latest day, so a multi-day delivery series may not be
    available; the confirmation still works off price+volume alone then)."""
    if len(closes) < lookback + 1 or len(volumes) < lookback + 1:
        return "none"
    price_rising = closes[-1] > closes[-1 - lookback]
    volume_rising = volumes[-1] > volumes[-1 - lookback]
    signals = [price_rising, volume_rising]
    if deliveries and len(deliveries) >= lookback + 1:
        signals.append(deliveries[-1] > deliveries[-1 - lookback])
    if all(signals):
        return "full"
    if any(signals):
        return "partial"
    return "none"


# --- Quality gates -----------------------------------------------------

def evaluate_quality_gates(
    fundamentals: Dict[str, Optional[float]],
    nse_flags: Dict[str, Optional[bool]],
    avg_daily_traded_value: Optional[float],
) -> Dict[str, object]:
    """
    fundamentals: {"market_cap_cr", "promoter_holding_pct", "debt_to_equity",
                    "earnings_growth_pct"} -> float | None
    nse_flags: {"asm", "gsm", "fo_ban"} -> bool | None (True = restricted/banned)
    avg_daily_traded_value: float | None, in Rs Crore

    A gate whose underlying value is None is recorded as "unknown", and
    "unknown" counts as not-passing for the overall gate — a filter that
    can't be verified is not the same as a filter that passed.
    """
    detail: Dict[str, str] = {}

    def _gate(name: str, value, passes_fn) -> None:
        detail[name] = UNKNOWN if value is None else ("pass" if passes_fn(value) else "fail")

    _gate("market_cap", fundamentals.get("market_cap_cr"), lambda v: v > 5000)
    _gate("avg_daily_traded_value", avg_daily_traded_value, lambda v: v > 10)
    _gate("asm", nse_flags.get("asm"), lambda v: v is False)
    _gate("gsm", nse_flags.get("gsm"), lambda v: v is False)
    _gate("fo_ban", nse_flags.get("fo_ban"), lambda v: v is False)
    _gate("promoter_holding", fundamentals.get("promoter_holding_pct"), lambda v: v > 40)
    _gate("debt_to_equity", fundamentals.get("debt_to_equity"), lambda v: v < 1.0)
    _gate("earnings_growth", fundamentals.get("earnings_growth_pct"), lambda v: v >= 0)

    passes_all = all(v == "pass" for v in detail.values())
    return {"detail": detail, "passes": passes_all}


# --- Risk management -----------------------------------------------------

def compute_risk_management(entry_price: float) -> Dict[str, float]:
    return {
        "stop_loss": round(entry_price * 0.95, 2),
        "target_low": round(entry_price * 1.10, 2),
        "target_high": round(entry_price * 1.15, 2),
    }


# --- Per-symbol assembly -----------------------------------------------

def build_symbol_metrics(
    closes: List[float],
    volumes: List[float],
    deliveries: Optional[List[float]],
    fundamentals: Dict[str, Optional[float]],
    nse_flags: Dict[str, Optional[bool]],
    avg_daily_traded_value: Optional[float],
) -> Dict[str, object]:
    """Everything computable for one symbol except the pool-relative
    composite score (see compute_momentum_scores, which needs every
    symbol's metrics at once to normalize against the pool)."""
    returns = compute_returns(closes)
    rsi = compute_rsi(closes)
    ema_trend = compute_ema_trend(closes)
    volume_increase = compute_volume_increase(volumes)
    volume_confirmation = compute_volume_confirmation(closes, volumes, deliveries)
    quality_gates = evaluate_quality_gates(fundamentals, nse_flags, avg_daily_traded_value)
    risk = compute_risk_management(closes[-1])
    delivery_pct = deliveries[-1] if deliveries else None

    return {
        "returns": returns,
        "rsi": rsi,
        "rsi_factor": _rsi_factor_score(rsi),
        "ema_trend": ema_trend,
        "volume_increase": volume_increase,
        "volume_confirmation": volume_confirmation,
        "delivery_pct": delivery_pct,
        "quality_gates": quality_gates,
        "risk": risk,
        "current_price": round(closes[-1], 2),
    }


# --- Pool-wide composite score -------------------------------------------

_SCORE_WEIGHTS = {
    "return_1m": 0.30,
    "return_7d": 0.25,
    "return_3d": 0.15,
    "return_1d": 0.10,
    "volume_increase": 0.10,
    "delivery_pct": 0.05,
    "rsi_factor": 0.05,
}


def _normalize_pool(values: Dict[str, float]) -> Dict[str, float]:
    """Min-max normalize a {symbol: raw_value} dict to [0, 1] across the pool."""
    if not values:
        return {}
    lo, hi = min(values.values()), max(values.values())
    if hi == lo:
        return {symbol: 0.5 for symbol in values}
    return {symbol: round((v - lo) / (hi - lo), 4) for symbol, v in values.items()}


def compute_momentum_scores(pool: Dict[str, Dict[str, object]]) -> Dict[str, Optional[float]]:
    """
    pool: {symbol: build_symbol_metrics(...) result}
    Returns {symbol: composite_score} (0-1 range), normalized against the
    pool's own return/volume/delivery distribution for this run. A symbol
    missing some factors (e.g. no delivery_pct) still gets a score,
    renormalized over the factors it does have, rather than being
    penalized to zero or excluded outright — matches the rest of this
    app's graceful-degradation philosophy.
    """
    factor_sources = {
        "return_1m": lambda m: m["returns"]["return_1m"],
        "return_7d": lambda m: m["returns"]["return_7d"],
        "return_3d": lambda m: m["returns"]["return_3d"],
        "return_1d": lambda m: m["returns"]["return_1d"],
        "volume_increase": lambda m: m["volume_increase"],
        "delivery_pct": lambda m: m["delivery_pct"],
    }

    normalized_factors: Dict[str, Dict[str, float]] = {symbol: {} for symbol in pool}

    for factor, extractor in factor_sources.items():
        raw = {}
        for symbol, metrics in pool.items():
            value = extractor(metrics)
            if value is not None:
                raw[symbol] = value
        for symbol, score in _normalize_pool(raw).items():
            normalized_factors[symbol][factor] = score

    for symbol, metrics in pool.items():
        normalized_factors[symbol]["rsi_factor"] = metrics["rsi_factor"]

    scores: Dict[str, Optional[float]] = {}
    for symbol, factors in normalized_factors.items():
        weighted_sum = 0.0
        weight_used = 0.0
        for factor, weight in _SCORE_WEIGHTS.items():
            if factor in factors:
                weighted_sum += factors[factor] * weight
                weight_used += weight
        scores[symbol] = round(weighted_sum / weight_used, 4) if weight_used > 0 else None
    return scores
```

- [ ] **Step 2: Write a real, executable test file — `tests/test_momentum_screen.py`**

This is the one backend file in the whole feature that can be verified with real
execution, so it gets real automated tests, not just manual tracing. Place at repo
root `tests/test_momentum_screen.py` (matching the existing `tests/` layout), adjusting
`sys.path` to reach `vercel-demo/`:

```python
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vercel-demo"))

from momentum_screen import (
    compute_ema_trend,
    compute_returns,
    compute_risk_management,
    compute_rsi,
    compute_volume_confirmation,
    compute_volume_increase,
    evaluate_quality_gates,
    compute_momentum_scores,
    build_symbol_metrics,
)


def _rising_closes(n, start=100.0, step=1.0):
    return [start + i * step for i in range(n)]


def test_compute_returns_basic():
    closes = _rising_closes(30)  # closes[i] = 100 + i
    result = compute_returns(closes)
    assert result["return_1d"] == round((closes[-1] - closes[-2]) / closes[-2], 4)
    assert result["return_3d"] == round((closes[-1] - closes[-4]) / closes[-4], 4)
    assert result["return_7d"] == round((closes[-1] - closes[-8]) / closes[-8], 4)
    assert result["return_1m"] == round((closes[-1] - closes[-22]) / closes[-22], 4)


def test_compute_returns_too_few_closes_raises():
    try:
        compute_returns(_rising_closes(10))
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_compute_rsi_all_gains_is_100():
    closes = _rising_closes(20)  # strictly increasing -> no losses at all
    assert compute_rsi(closes) == 100.0


def test_compute_rsi_all_losses_is_0():
    closes = list(reversed(_rising_closes(20)))  # strictly decreasing
    assert compute_rsi(closes) == 0.0


def test_compute_ema_trend_uptrend_passes():
    closes = _rising_closes(60)  # steadily rising -> price > EMA20 > EMA50
    result = compute_ema_trend(closes)
    assert result["passes"] is True
    assert result["price"] > result["ema20"] > result["ema50"]


def test_compute_ema_trend_downtrend_fails():
    closes = list(reversed(_rising_closes(60)))
    result = compute_ema_trend(closes)
    assert result["passes"] is False


def test_compute_volume_increase_rising():
    volumes = [100.0] * 10 + [200.0]  # today is double the trailing average
    assert compute_volume_increase(volumes) == 1.0


def test_compute_volume_confirmation_full():
    closes = [100.0, 101.0, 102.0, 103.0]
    volumes = [1000.0, 1000.0, 1000.0, 2000.0]
    deliveries = [50.0, 50.0, 50.0, 60.0]
    assert compute_volume_confirmation(closes, volumes, deliveries) == "full"


def test_compute_volume_confirmation_none():
    closes = [103.0, 102.0, 101.0, 100.0]
    volumes = [2000.0, 1500.0, 1200.0, 1000.0]
    assert compute_volume_confirmation(closes, volumes, None) == "none"


def test_evaluate_quality_gates_all_pass():
    fundamentals = {
        "market_cap_cr": 6000.0,
        "promoter_holding_pct": 50.0,
        "debt_to_equity": 0.5,
        "earnings_growth_pct": 10.0,
    }
    nse_flags = {"asm": False, "gsm": False, "fo_ban": False}
    result = evaluate_quality_gates(fundamentals, nse_flags, avg_daily_traded_value=15.0)
    assert result["passes"] is True
    assert all(v == "pass" for v in result["detail"].values())


def test_evaluate_quality_gates_unknown_excludes():
    fundamentals = {
        "market_cap_cr": 6000.0,
        "promoter_holding_pct": None,  # missing data
        "debt_to_equity": 0.5,
        "earnings_growth_pct": 10.0,
    }
    nse_flags = {"asm": False, "gsm": False, "fo_ban": False}
    result = evaluate_quality_gates(fundamentals, nse_flags, avg_daily_traded_value=15.0)
    assert result["passes"] is False
    assert result["detail"]["promoter_holding"] == "unknown"


def test_evaluate_quality_gates_fo_ban_fails():
    fundamentals = {
        "market_cap_cr": 6000.0,
        "promoter_holding_pct": 50.0,
        "debt_to_equity": 0.5,
        "earnings_growth_pct": 10.0,
    }
    nse_flags = {"asm": False, "gsm": False, "fo_ban": True}  # banned
    result = evaluate_quality_gates(fundamentals, nse_flags, avg_daily_traded_value=15.0)
    assert result["passes"] is False
    assert result["detail"]["fo_ban"] == "fail"


def test_compute_risk_management():
    result = compute_risk_management(100.0)
    assert result == {"stop_loss": 95.0, "target_low": 110.0, "target_high": 115.0}


def test_compute_momentum_scores_ranks_stronger_symbol_higher():
    strong_closes = _rising_closes(30, start=100.0, step=2.0)
    weak_closes = _rising_closes(30, start=100.0, step=0.1)
    volumes = [1000.0] * 30

    pool = {
        "STRONG": build_symbol_metrics(strong_closes, volumes, None, {}, {}, None),
        "WEAK": build_symbol_metrics(weak_closes, volumes, None, {}, {}, None),
    }
    scores = compute_momentum_scores(pool)
    assert scores["STRONG"] > scores["WEAK"]


def test_compute_momentum_scores_missing_factor_still_scores():
    closes = _rising_closes(30)
    volumes = [1000.0] * 30
    metrics = build_symbol_metrics(closes, volumes, None, {}, {}, None)
    # delivery_pct is None (no deliveries passed) — must not crash or
    # produce None for the whole score.
    assert metrics["delivery_pct"] is None
    scores = compute_momentum_scores({"ONLY": metrics})
    assert scores["ONLY"] is not None


if __name__ == "__main__":
    import sys as _sys
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except AssertionError as exc:
            failures += 1
            print(f"FAIL {test.__name__}: {exc}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    _sys.exit(1 if failures else 0)
```

- [ ] **Step 3: Run the tests for real**

Run: `python tests/test_momentum_screen.py` from the repo root.
Expected: `15/15 passed`, exit code 0. This module has zero pandas/psycopg2/network
dependency, so this must be a real, green run — not a syntax-only check. If pytest is
available, `pytest tests/test_momentum_screen.py -v` also works; the `__main__` block
exists so it runs with neither pytest nor any other dependency installed.

- [ ] **Step 4: Commit**

```bash
git add momentum_screen.py ../tests/test_momentum_screen.py
git commit -m "Add momentum scoring/quality-filter module with real executable tests"
```
(Run from `vercel-demo/`; the test file lives one level up at repo-root `tests/`, hence
the `../tests/...` path in the `git add`.)

---

### Task 4: Cron endpoint (`api/cron/momentum_screen.py`) + schema + Vercel Cron config

**Files:**
- Create: `vercel-demo/api/cron/momentum_screen.py`
- Modify: `vercel-demo/schema.sql`
- Modify: `vercel-demo/vercel.json`

**Interfaces:**
- Produces: `GET /api/cron/momentum_screen` — runs the full screen, upserts
  `momentum_rankings`, returns `200 {"run_date": "...", "symbols_scored": N, "symbols_failed": M}`
  or `500` with an error/traceback on total failure.
- Consumes: `sources.nse` (Task 1), `sources.prices.fetch_ohlcv_history` (Task 2),
  `momentum_screen` (Task 3), `db.get_connection()` (existing).

- [ ] **Step 1: Add the `momentum_rankings` table to `schema.sql`**

Append to the existing `vercel-demo/schema.sql` (which already has `holdings` and
`watchlist`):

```sql
CREATE TABLE IF NOT EXISTS momentum_rankings (
    id SERIAL PRIMARY KEY,
    run_date DATE NOT NULL,
    symbol TEXT NOT NULL,
    sector TEXT,
    pe_ratio NUMERIC,
    current_price NUMERIC NOT NULL,
    return_1d NUMERIC,
    return_3d NUMERIC,
    return_7d NUMERIC,
    return_1m NUMERIC,
    passes_quality_gates BOOLEAN NOT NULL,
    passes_trend_gate BOOLEAN NOT NULL,
    quality_gate_detail JSONB NOT NULL,
    momentum_score NUMERIC,
    volume_confirmation TEXT NOT NULL,
    stop_loss NUMERIC,
    target_low NUMERIC,
    target_high NUMERIC,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_momentum_rankings_run_date ON momentum_rankings(run_date);
```

- [ ] **Step 2: Write `api/cron/momentum_screen.py`**

```python
from __future__ import annotations

import json
import os
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import db
import momentum_screen
import yfinance as yf
from sources import nse as nse_source
from sources import prices as prices_source


def _fetch_fundamentals(yf_symbol: str) -> dict:
    """Best-effort — yfinance .info coverage for NSE tickers is
    inconsistent; any missing field is None, never assumed to fail a
    gate (see momentum_screen.evaluate_quality_gates)."""
    try:
        info = yf.Ticker(yf_symbol).info
    except Exception:
        return {
            "market_cap_cr": None, "promoter_holding_pct": None,
            "debt_to_equity": None, "earnings_growth_pct": None,
            "sector": None, "pe_ratio": None,
        }

    market_cap = info.get("marketCap")
    market_cap_cr = (market_cap / 1e7) if isinstance(market_cap, (int, float)) else None
    promoter_holding = info.get("heldPercentInsiders")
    promoter_holding_pct = (promoter_holding * 100) if isinstance(promoter_holding, (int, float)) else None
    debt_to_equity_raw = info.get("debtToEquity")
    # ASSUMPTION, not independently verified from this environment:
    # yfinance commonly reports debtToEquity as a percentage (e.g. 45.2
    # meaning a ratio of 0.452), not a raw ratio — normalized here to
    # match this project's <1.0 threshold convention. If live data proves
    # this wrong for NSE tickers specifically, the gate's threshold will
    # silently almost-always-pass or almost-always-fail — see Task 9's
    # setup checklist, which flags this as a first-deploy verification
    # item alongside the ASM/GSM URLs.
    debt_to_equity = (debt_to_equity_raw / 100) if isinstance(debt_to_equity_raw, (int, float)) else None
    earnings_growth = info.get("earningsGrowth")
    earnings_growth_pct = (earnings_growth * 100) if isinstance(earnings_growth, (int, float)) else None

    return {
        "market_cap_cr": market_cap_cr,
        "promoter_holding_pct": promoter_holding_pct,
        "debt_to_equity": debt_to_equity,
        "earnings_growth_pct": earnings_growth_pct,
        "sector": info.get("sector"),
        "pe_ratio": info.get("trailingPE"),
    }


def _fetch_one(bare_symbol: str, nse_flags: dict, bhavcopy: dict) -> tuple:
    yf_symbol = f"{bare_symbol}.NS"
    ohlcv = prices_source.fetch_ohlcv_history(yf_symbol)
    fundamentals = _fetch_fundamentals(yf_symbol)

    bhav_row = bhavcopy.get(bare_symbol)
    deliveries = [bhav_row["delivery_pct"]] if bhav_row else None
    volumes = ohlcv["volume"]
    if bhav_row and bhav_row.get("volume"):
        # Prefer bhavcopy's official traded quantity for today's volume
        # figure over yfinance's, which can lag/differ for NSE tickers.
        volumes = volumes[:-1] + [bhav_row["volume"]]

    avg_price = sum(ohlcv["close"][-10:]) / len(ohlcv["close"][-10:])
    avg_volume = sum(volumes[-10:]) / len(volumes[-10:])
    avg_daily_traded_value_cr = (avg_price * avg_volume) / 1e7

    metrics = momentum_screen.build_symbol_metrics(
        closes=ohlcv["close"],
        volumes=volumes,
        deliveries=deliveries,
        fundamentals=fundamentals,
        nse_flags=nse_flags,
        avg_daily_traded_value=avg_daily_traded_value_cr,
    )
    metrics["sector"] = fundamentals["sector"]
    metrics["pe_ratio"] = fundamentals["pe_ratio"]
    return bare_symbol, metrics


def run_screen() -> dict:
    symbols = nse_source.fetch_nifty200_symbols()

    fo_ban = nse_source.fetch_fo_ban_symbols()
    asm = nse_source.fetch_asm_symbols()
    gsm = nse_source.fetch_gsm_symbols()
    trading_day = nse_source.latest_trading_day()
    bhavcopy = nse_source.fetch_bhavcopy(trading_day)

    pool: dict = {}
    failed: list = []
    with ThreadPoolExecutor(max_workers=10) as pool_executor:
        nse_flags_by_symbol = {
            symbol: {"asm": symbol in asm, "gsm": symbol in gsm, "fo_ban": symbol in fo_ban}
            for symbol in symbols
        }
        futures = {
            pool_executor.submit(_fetch_one, symbol, nse_flags_by_symbol[symbol], bhavcopy): symbol
            for symbol in symbols
        }
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                bare_symbol, metrics = future.result()
                pool[bare_symbol] = metrics
            except Exception as exc:
                failed.append({"symbol": symbol, "error": str(exc)})

    scores = momentum_screen.compute_momentum_scores(pool)

    rows = []
    for symbol, metrics in pool.items():
        rows.append((
            trading_day,
            symbol,
            metrics.get("sector"),
            metrics.get("pe_ratio"),
            metrics["current_price"],
            metrics["returns"]["return_1d"],
            metrics["returns"]["return_3d"],
            metrics["returns"]["return_7d"],
            metrics["returns"]["return_1m"],
            metrics["quality_gates"]["passes"],
            metrics["ema_trend"]["passes"],
            json.dumps(metrics["quality_gates"]["detail"]),
            scores.get(symbol),
            metrics["volume_confirmation"],
            metrics["risk"]["stop_loss"],
            metrics["risk"]["target_low"],
            metrics["risk"]["target_high"],
        ))

    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM momentum_rankings WHERE run_date = %s", (trading_day,))
            cur.executemany(
                "INSERT INTO momentum_rankings "
                "(run_date, symbol, sector, pe_ratio, current_price, return_1d, return_3d, "
                "return_7d, return_1m, passes_quality_gates, passes_trend_gate, "
                "quality_gate_detail, momentum_score, volume_confirmation, stop_loss, "
                "target_low, target_high) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                rows,
            )
        conn.commit()
    finally:
        conn.close()

    return {"run_date": trading_day.isoformat(), "symbols_scored": len(rows), "symbols_failed": len(failed), "failed": failed}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            payload = run_screen()
            status = 200
        except Exception as exc:
            payload = {"error": str(exc), "traceback": traceback.format_exc()}
            status = 500
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)
```

- [ ] **Step 3: Add the Vercel Cron entry to `vercel.json`**

Current `vercel.json`:
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
Replace with:
```json
{
  "framework": "vite",
  "functions": {
    "api/*.py": {
      "maxDuration": 60
    }
  },
  "crons": [
    {
      "path": "/api/cron/momentum_screen",
      "schedule": "30 13 * * 1-5"
    }
  ]
}
```
`"30 13 * * 1-5"` is UTC cron syntax for 13:30 UTC = 19:00 IST, Monday-Friday (NSE
trading days) — after NSE's EOD bhavcopy is typically published. Vercel Cron schedules
are always UTC regardless of project region.

- [ ] **Step 4: Verify syntax**

Run: `python -c "import ast; ast.parse(open('api/cron/momentum_screen.py').read()); print('OK')"`
from `vercel-demo/`. Expected: `OK`. Also validate `vercel.json` is well-formed JSON:
`python -c "import json; json.load(open('vercel.json')); print('OK')"`.

- [ ] **Step 5: Manual trace**

Trace `run_screen()` when `nse_source.fetch_nifty200_symbols()` raises `RuntimeError`
(NSE blocked entirely) → propagates uncaught out of `run_screen()` → `do_GET` catches
generic `Exception` → `500` with traceback → **the previous run_date's rows are left
untouched in the table** (the `DELETE ... WHERE run_date = %s` for the new date never
executes, since we never got a `trading_day` to delete/insert against) → confirms
`api/momentum.py`'s "serve the last successful run" fallback (Task 5) has real data to
fall back to. Trace one symbol's `_fetch_one` raising inside the `ThreadPoolExecutor` →
caught by the per-future `except Exception`, added to `failed`, loop continues for
every other future → confirms one bad symbol doesn't abort the run. Trace the SQL
`executemany` parameter order against the column list in the `INSERT` — count both:
17 columns listed, 17 values placed into each tuple in `rows`, same order — confirms no
off-by-one column/value mismatch.

- [ ] **Step 6: Commit**

```bash
git add api/cron/momentum_screen.py schema.sql vercel.json
git commit -m "Add daily momentum-screen cron job, schema, and Vercel Cron config"
```

---

### Task 5: Read API (`api/momentum.py`)

**Files:**
- Create: `vercel-demo/api/momentum.py`

**Interfaces:**
- Produces: `GET /api/momentum?tab=screener|1d|3d|7d|1m` →
  `200 {"run_date": "...", "stale": bool, "rows": [...]}` or `503` if no cached data
  exists at all yet (first deploy, before the first cron run).
- No `X-Device-Id` required — this is public, non-per-device data.

- [ ] **Step 1: Write `api/momentum.py`**

```python
from __future__ import annotations

import datetime
import json
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import db

_VALID_TABS = {"screener", "1d", "3d", "7d", "1m"}
_SORT_COLUMN = {"1d": "return_1d", "3d": "return_3d", "7d": "return_7d", "1m": "return_1m"}
_STALE_AFTER_DAYS = 2


def _row_to_dict(row) -> dict:
    return {
        "symbol": row["symbol"],
        "sector": row["sector"],
        "pe_ratio": float(row["pe_ratio"]) if row["pe_ratio"] is not None else None,
        "current_price": float(row["current_price"]),
        "return_1d": float(row["return_1d"]) if row["return_1d"] is not None else None,
        "return_3d": float(row["return_3d"]) if row["return_3d"] is not None else None,
        "return_7d": float(row["return_7d"]) if row["return_7d"] is not None else None,
        "return_1m": float(row["return_1m"]) if row["return_1m"] is not None else None,
        "passes_quality_gates": row["passes_quality_gates"],
        "passes_trend_gate": row["passes_trend_gate"],
        "quality_gate_detail": row["quality_gate_detail"],
        "momentum_score": float(row["momentum_score"]) if row["momentum_score"] is not None else None,
        "volume_confirmation": row["volume_confirmation"],
        "stop_loss": float(row["stop_loss"]) if row["stop_loss"] is not None else None,
        "target_low": float(row["target_low"]) if row["target_low"] is not None else None,
        "target_high": float(row["target_high"]) if row["target_high"] is not None else None,
        "screener_url": f"https://www.screener.in/company/{row['symbol']}/",
    }


def get_momentum(tab: str) -> dict:
    if tab not in _VALID_TABS:
        raise ValueError(f"tab must be one of {sorted(_VALID_TABS)}, got {tab!r}")

    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT MAX(run_date) AS latest FROM momentum_rankings")
            latest_row = cur.fetchone()
            run_date = latest_row["latest"] if latest_row else None
            if run_date is None:
                raise LookupError("No momentum screen has run yet")

            if tab == "screener":
                cur.execute(
                    "SELECT * FROM momentum_rankings WHERE run_date = %s "
                    "AND passes_quality_gates = TRUE AND passes_trend_gate = TRUE "
                    "ORDER BY momentum_score DESC NULLS LAST LIMIT 20",
                    (run_date,),
                )
            else:
                column = _SORT_COLUMN[tab]
                cur.execute(
                    f"SELECT * FROM momentum_rankings WHERE run_date = %s "
                    f"ORDER BY {column} DESC NULLS LAST LIMIT 20",
                    (run_date,),
                )
            rows = cur.fetchall()
    finally:
        conn.close()

    stale = (datetime.date.today() - run_date).days > _STALE_AFTER_DAYS
    return {"run_date": run_date.isoformat(), "stale": stale, "rows": [_row_to_dict(r) for r in rows]}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            query = parse_qs(urlparse(self.path).query)
            tab = query.get("tab", ["screener"])[0]
            payload = get_momentum(tab)
            status = 200
        except ValueError as exc:
            payload = {"error": str(exc)}
            status = 400
        except LookupError as exc:
            payload = {"error": str(exc)}
            status = 503
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

Note the `f"SELECT * FROM momentum_rankings WHERE run_date = %s ORDER BY {column} DESC..."`
uses an f-string for the `ORDER BY` column — this is **not** a SQL injection risk
despite the f-string, because `column` only ever comes from `_SORT_COLUMN[tab]`, a
fixed dict indexed by `tab` which was already validated against the closed
`_VALID_TABS` set immediately above; `column`'s value is always one of the 4 literal
strings hardcoded in `_SORT_COLUMN`, never client-supplied text.

- [ ] **Step 2: Verify syntax**

Run: `python -c "import ast; ast.parse(open('api/momentum.py').read()); print('OK')"`
from `vercel-demo/`. Expected: `OK`.

- [ ] **Step 3: Manual trace**

Trace `get_momentum("bogus")` → `tab not in _VALID_TABS` → `ValueError` → `do_GET`
catches it → `400`. Trace `get_momentum("screener")` when the table is empty (no cron
has ever run) → `latest_row["latest"]` is `None` → `LookupError` → `do_GET` catches it
→ `503` (distinct from `500`, so the frontend can show "screening hasn't run yet" vs.
"something broke"). Trace the `stale` computation with `run_date` 3 days ago →
`(today - run_date).days = 3 > 2` → `stale: True`. Confirm the `f"...ORDER BY {column}..."`
argument really can only be one of `"return_1d"/"return_3d"/"return_7d"/"return_1m"` by
tracing `_SORT_COLUMN[tab]` with `tab` already constrained to `_VALID_TABS - {"screener"}`
at the point that branch executes.

- [ ] **Step 4: Commit**

```bash
git add api/momentum.py
git commit -m "Add GET /api/momentum reading cached rankings, no live fetch"
```

---

### Task 6: Frontend — Momentum section shell + Screener tab

**Files:**
- Create: `vercel-demo/src/components/MomentumSection.jsx`
- Create: `vercel-demo/src/components/MomentumScreenerTab.jsx`
- Modify: `vercel-demo/src/index.css`

**Interfaces:**
- Produces: `<MomentumSection />` — self-contained (owns its own sub-tab state,
  fetches from `/api/momentum`). Consumed by Task 8 (`App.jsx`).
- Consumes: no `apiFetch`/`X-Device-Id` — plain `fetch()`, matching `/api/dashboard`'s
  public, non-per-device pattern.

- [ ] **Step 1: Write `src/components/MomentumScreenerTab.jsx`**

```jsx
const GATE_LABELS = {
  market_cap: "Market cap > ₹5,000 Cr",
  avg_daily_traded_value: "Avg daily traded value > ₹10 Cr",
  asm: "Not on ASM list",
  gsm: "Not on GSM list",
  fo_ban: "Not in F&O ban",
  promoter_holding: "Promoter holding > 40%",
  debt_to_equity: "Debt-to-equity < 1.0",
  earnings_growth: "Stable/positive earnings growth",
};

const VOLUME_BADGE = {
  full: { label: "Volume confirmed", color: "var(--positive)" },
  partial: { label: "Partial volume signal", color: "var(--warning)" },
  none: { label: "No volume confirmation", color: "var(--text-muted)" },
};

function GateBreakdown({ detail }) {
  return (
    <ul className="momentum-gate-list">
      {Object.entries(detail).map(([key, value]) => (
        <li key={key} className={`momentum-gate momentum-gate-${value}`}>
          <span>{GATE_LABELS[key] || key}</span>
          <span className="momentum-gate-status">{value}</span>
        </li>
      ))}
    </ul>
  );
}

export default function MomentumScreenerTab({ rows }) {
  if (rows.length === 0) {
    return <p className="empty-state">No symbols passed every quality gate in the latest run.</p>;
  }
  return (
    <div className="momentum-list">
      {rows.map((row, index) => {
        const badge = VOLUME_BADGE[row.volume_confirmation] || VOLUME_BADGE.none;
        return (
          <div key={row.symbol} className="asset-card momentum-card">
            <div className="asset-card-row">
              <div className="asset-card-main">
                <span className="momentum-rank">#{index + 1}</span>
                <span className="asset-symbol">{row.symbol}</span>
                <span className="momentum-sector">{row.sector || "Sector unknown"}</span>
                {row.pe_ratio != null && <span className="momentum-pe">P/E {row.pe_ratio.toFixed(1)}</span>}
              </div>
              <div className="asset-card-stats">
                <span className="momentum-score">Score {row.momentum_score?.toFixed(3) ?? "–"}</span>
                <span style={{ color: badge.color }}>{badge.label}</span>
                <a href={row.screener_url} target="_blank" rel="noreferrer" className="momentum-link">
                  Details →
                </a>
              </div>
            </div>
            <div className="momentum-risk">
              <span>Entry ₹{row.current_price.toLocaleString("en-IN")}</span>
              <span>Stop-loss ₹{row.stop_loss?.toLocaleString("en-IN")}</span>
              <span>
                Target ₹{row.target_low?.toLocaleString("en-IN")}–{row.target_high?.toLocaleString("en-IN")}
              </span>
            </div>
            <GateBreakdown detail={row.quality_gate_detail} />
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Write `src/components/MomentumSection.jsx`**

```jsx
import { useEffect, useState } from "react";
import MomentumScreenerTab from "./MomentumScreenerTab.jsx";

const SUB_TABS = [
  { key: "screener", label: "Screener" },
  { key: "1d", label: "1 Day Movers" },
  { key: "3d", label: "3 Day Movers" },
  { key: "7d", label: "7 Day Movers" },
  { key: "1m", label: "1 Month Movers" },
];

const RETURN_FIELD = { "1d": "return_1d", "3d": "return_3d", "7d": "return_7d", "1m": "return_1m" };

function MoversTab({ rows, returnField }) {
  if (rows.length === 0) {
    return <p className="empty-state">No data in the latest run.</p>;
  }
  return (
    <div className="momentum-list">
      {rows.map((row, index) => (
        <div key={row.symbol} className="asset-card momentum-card">
          <div className="asset-card-row">
            <div className="asset-card-main">
              <span className="momentum-rank">#{index + 1}</span>
              <span className="asset-symbol">{row.symbol}</span>
              <span className="momentum-sector">{row.sector || "Sector unknown"}</span>
              {row.pe_ratio != null && <span className="momentum-pe">P/E {row.pe_ratio.toFixed(1)}</span>}
            </div>
            <div className="asset-card-stats">
              <span
                className="momentum-return"
                style={{ color: row[returnField] >= 0 ? "var(--positive)" : "var(--negative)" }}
              >
                {row[returnField] != null ? `${(row[returnField] * 100).toFixed(2)}%` : "–"}
              </span>
              <a href={row.screener_url} target="_blank" rel="noreferrer" className="momentum-link">
                Details →
              </a>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export default function MomentumSection() {
  const [activeSubTab, setActiveSubTab] = useState("screener");
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetch(`/api/momentum?tab=${activeSubTab}`)
      .then((res) => res.json())
      .then((body) => {
        if (body.error) throw new Error(body.error);
        setData(body);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [activeSubTab]);

  return (
    <div className="momentum-section">
      <nav className="tabs momentum-subtabs">
        {SUB_TABS.map((tab) => (
          <button
            key={tab.key}
            className={activeSubTab === tab.key ? "tab active" : "tab"}
            onClick={() => setActiveSubTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      {loading && <p>Loading momentum data…</p>}
      {error && <p className="error-text">{error}</p>}

      {data && (
        <>
          <p className="momentum-freshness">
            As of {data.run_date}
            {data.stale && <span className="warning-text"> — data is more than 2 days old</span>}
          </p>
          {activeSubTab === "screener" ? (
            <MomentumScreenerTab rows={data.rows} />
          ) : (
            <MoversTab rows={data.rows} returnField={RETURN_FIELD[activeSubTab]} />
          )}
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Append momentum styles to `src/index.css`**

```css
.momentum-subtabs {
  margin-bottom: 1rem;
}

.momentum-freshness {
  font-size: 0.85rem;
  color: var(--text-muted);
  margin-bottom: 0.75rem;
}

.momentum-list {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.momentum-rank {
  font-weight: 700;
  color: var(--text-muted);
  margin-right: 0.4rem;
}

.momentum-sector,
.momentum-pe {
  font-size: 0.8rem;
  color: var(--text-muted);
  margin-left: 0.6rem;
}

.momentum-score,
.momentum-return {
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.momentum-link {
  color: var(--accent);
  text-decoration: none;
  font-size: 0.85rem;
}

.momentum-risk {
  display: flex;
  gap: 1rem;
  padding: 0 1rem 0.5rem;
  font-size: 0.8rem;
  color: var(--text-muted);
}

.momentum-gate-list {
  list-style: none;
  margin: 0;
  padding: 0 1rem 0.75rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.momentum-gate {
  display: flex;
  gap: 0.3rem;
  font-size: 0.75rem;
  padding: 0.15rem 0.5rem;
  border-radius: 6px;
  background: var(--card-border);
}

.momentum-gate-pass {
  color: var(--positive);
}

.momentum-gate-fail {
  color: var(--negative);
}

.momentum-gate-unknown {
  color: var(--text-muted);
}
```

- [ ] **Step 4: Verify — real build**

Run from `vercel-demo/`: `npm run build`
Expected: exits 0. (`MomentumSection` isn't wired into `App.jsx` yet — Task 8 — so it
won't be reachable in the running app yet, but it must compile cleanly now.)

- [ ] **Step 5: Commit**

```bash
git add src/components/MomentumSection.jsx src/components/MomentumScreenerTab.jsx src/index.css
git commit -m "Add Momentum section shell with sub-tab nav and the Screener tab"
```

---

### Task 7: Frontend — verify the 4 timeframe Movers tabs

**Files:** None new — `MoversTab` (the reusable component for all 4 timeframe tabs)
was already written inside `MomentumSection.jsx` in Task 6, since it's small enough
(~25 lines) that splitting it into its own file would be premature.

**Interfaces:** None new.

This task exists to explicitly verify the 4 timeframe tabs work correctly as their own
reviewable unit, since Task 6 bundled their implementation in with the Screener tab's
shell for file-layout reasons — the review should still treat "does `MoversTab` render
1D/3D/7D/1M correctly" as its own checklist, not assume it was covered by Task 6's
Screener-focused review.

- [ ] **Step 1: Manual trace of `MoversTab` across all 4 periods**

Trace `activeSubTab = "3d"` → `RETURN_FIELD["3d"] = "return_3d"` → `MoversTab` receives
`returnField="return_3d"` → renders `row["return_3d"]` for every row, formatted as a
percentage with sign-colored text (green if `>= 0`, red otherwise) → confirms the same
component correctly parameterizes across all 4 periods via the `RETURN_FIELD` lookup,
with no period-specific logic duplicated 4 times.

Trace a row where `row.return_3d` is `null` (yfinance/NSE data gap for that one
factor, while other factors succeeded) → `row[returnField] != null` is `false` →
renders `"–"` (en dash) instead of crashing on `null.toFixed`.

- [ ] **Step 2: Re-run the build to confirm no regression**

Run from `vercel-demo/`: `npm run build`
Expected: exits 0, identical to Task 6's result (no files changed in this task).

- [ ] **Step 3: No commit for this task**

No files changed — this task is a verification checkpoint only, so the SDD reviewer
gives the 4 timeframe tabs their own explicit sign-off before Task 8 wires the whole
section into the live app.

---

### Task 8: Wire the Momentum section into `App.jsx`

**Files:**
- Modify: `vercel-demo/src/App.jsx`

**Interfaces:** None new — wiring only.

- [ ] **Step 1: Add the import**

Add alongside the existing component imports in `src/App.jsx`:
```jsx
import MomentumSection from "./components/MomentumSection.jsx";
```

- [ ] **Step 2: Extend the `TABS` array**

Current `TABS` (6 entries: intraday/short_term/swing/movers/holdings/watchlist) gets
one more entry appended:
```jsx
const TABS = [
  { key: "intraday", label: "Day Trading" },
  { key: "short_term", label: "Short-Term" },
  { key: "swing", label: "Swing / Long-Term" },
  { key: "movers", label: "Top Movers" },
  { key: "holdings", label: "My Holdings" },
  { key: "watchlist", label: "My Watchlist" },
  { key: "momentum", label: "Momentum" },
];
```

- [ ] **Step 3: Extend the render branch**

Find the render branch (as of the Holdings/Watchlist final-review fix, it looks like
this):
```jsx
      {activeTab === "holdings" ? (
        <Holdings />
      ) : activeTab === "watchlist" ? (
        <PersonalWatchlist />
      ) : (
        <>
          {loading && <p>Loading live market data…</p>}
          ...
```
Add a `momentum` branch alongside `holdings`/`watchlist` (same pattern — self-contained,
no dashboard dependency, must not be nested inside the `{dashboard && ...}`-gated
branch, matching the fix already applied for Holdings/Watchlist):
```jsx
      {activeTab === "holdings" ? (
        <Holdings />
      ) : activeTab === "watchlist" ? (
        <PersonalWatchlist />
      ) : activeTab === "momentum" ? (
        <MomentumSection />
      ) : (
        <>
          {loading && <p>Loading live market data…</p>}
          ...
```
(Everything else in `App.jsx` is unchanged — only the import, the `TABS` array, and
this one additional ternary branch.)

- [ ] **Step 4: Verify — real build**

Run from `vercel-demo/`: `npm run build`
Expected: exits 0, 7 tabs present.

- [ ] **Step 5: Commit**

```bash
git add src/App.jsx
git commit -m "Wire the Momentum section into the tab bar"
```

---

### Task 9: Final verification and setup checklist

**Files:** None new — final review pass over what's already built.

**Interfaces:** None.

- [ ] **Step 1: Full real build, one more time**

Run from `vercel-demo/`: `rm -rf node_modules dist && npm install && npm run build`
Expected: exits 0 end to end.

- [ ] **Step 2: Real test run for the one fully-executable backend file**

Run from the repo root: `python tests/test_momentum_screen.py`
Expected: `15/15 passed`, exit 0.

- [ ] **Step 3: Python syntax check across every other new/modified backend file**

Run from `vercel-demo/`:
```bash
python -c "
import ast
for f in ['sources/nse.py', 'sources/prices.py', 'api/cron/momentum_screen.py', 'api/momentum.py']:
    ast.parse(open(f).read())
    print(f, 'OK')
"
```
Expected: all four print `OK`. (`sources/nse.py` was already verified with a real
import in Task 1 — this re-check just confirms nothing regressed across later tasks.)

- [ ] **Step 4: Setup checklist (for the human partner — cannot be done from this session)**

1. Run the new `momentum_rankings` table's `CREATE TABLE` statement (already appended
   to `vercel-demo/schema.sql` in Task 4) against the same Supabase/Postgres database
   already used for `holdings`/`watchlist` — same manual step as before, same SQL
   editor.
2. Deploy (`npx vercel --prod` from `vercel-demo/`, or however this project is
   currently deployed) so the new `vercel.json` cron entry is registered — Vercel only
   picks up `crons` config from a fresh deployment.
3. **Confirm two unverified assumptions before trusting the Screener tab's gates:**
   - The ASM/GSM URLs in `sources/nse.py` — a best-effort guess at Task 1 time against
     NSE's current Surveillance pages, not independently verified (see that task's
     Global Constraints note).
   - The debt-to-equity unit conversion in `api/cron/momentum_screen.py`'s
     `_fetch_fundamentals` (divides yfinance's `debtToEquity` by 100, assuming it's a
     percentage) — check a few known NSE tickers' actual `debtToEquity` values against
     a source you trust (e.g. Screener.in) to confirm this conversion is correct before
     trusting the debt-to-equity gate's pass/fail results.
4. Either wait for the first scheduled cron run (per `vercel.json`'s
   `"30 13 * * 1-5"` — 19:00 IST on the next trading day), or manually trigger it once
   by visiting `/api/cron/momentum_screen` directly in a browser/curl to populate the
   table immediately rather than waiting.
5. **Watch the first cron run's response/logs for NSE blocking.** If `sources/nse.py`'s
   functions raise (visible in the cron response's `error` field, or in Vercel's
   function logs), that's the anti-bot risk documented in the spec materializing — the
   Screener tab's quality gates will show `"unknown"` for every NSE-sourced filter
   until/unless that's resolved, but the 4 timeframe Movers tabs (yfinance-only) should
   still work.

- [ ] **Step 5: Report results**

Summarize in the task report: build/test/syntax status (Steps 1-3), and that Step 4 is
documented for the human partner to perform post-deployment. No commit needed for this
task.
