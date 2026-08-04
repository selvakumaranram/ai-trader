# Holdings & Personal Watchlist Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two persistent, database-backed features to the dashboard: a Holdings list (stocks you own, with live P&L, LTCG/STCG holding-period context, and a rule-based sell/hold signal) and a personal Watchlist (arbitrary saved symbols with the same buy guidance `/api/search` already gives) — both scoped to an anonymous per-browser device ID, no login.

**Architecture:** A new Vercel Postgres database (two tables: `holdings`, `watchlist`) accessed via `psycopg2-binary`. Two new API endpoint files (`api/holdings.py`, `api/watchlist.py`) each handling GET/POST/DELETE, reusing `recommender.build_asset_payload` for all live scoring (no new scoring logic) and a new small `holdings_logic.py` module for the two genuinely new pieces of business logic (sell signal, LTCG holding-period math). The frontend gets two new tabs, a `deviceId.js` helper (random ID in `localStorage`, sent as `X-Device-Id`), and a shared `apiFetch` wrapper.

**Tech Stack:** Python 3.14 (existing `api/*.py` pattern), `psycopg2-binary` (new dependency), Vercel Postgres (Neon-backed), React (existing components reused: `AssetCard`, `WhyPanel`).

## Global Constraints

- **Database provisioning is a manual, human step — no task in this plan provisions it.** Tasks write code that expects a Postgres connection string to exist in an environment variable; the human partner must create the database in the Vercel dashboard (Storage tab) and run `vercel-demo/schema.sql` once via a Postgres client, before any of this code can actually be exercised end-to-end. Task 9 documents this.
- **The exact env var name is not knowable in advance.** `db.py` (Task 2) checks `DATABASE_URL` first, then `POSTGRES_URL` as a fallback — whichever Vercel actually populates once the database is attached. Do not assume one name and hardcode it as the only option.
- **`psycopg2-binary` cannot be verified on this machine at all — do not attempt to import or run it locally.** This machine has a confirmed Windows Application Control Policy blocking compiled Python extensions (documented throughout this project's history for pandas); `psycopg2` is also a compiled C extension and is very likely to hit the same wall, or a different one. Every task touching `db.py` or the two new API files is verified via `python -c "import ast; ast.parse(...)"` (syntax only — this never imports the module) plus careful manual tracing, exactly like every other backend file on this branch. Real, executed database verification only happens after deployment with a real database attached (Task 9's manual checklist).
- Reuse `recommender.build_asset_payload` (already extracted during the dashboard's final review) for all scoring in the new endpoints — do not write a third copy of that ~20-line assembly logic.
- New sell-signal and holding-period logic lives in a new `vercel-demo/holdings_logic.py` module, not in `recommender.py` — keeps `recommender.py` scoped to watchlist/scoring concerns, matching the "each file has one clear responsibility" principle already established on this branch.
- Every write endpoint (`POST`/`DELETE`) validates its input and returns a clear 4xx with a message — never a raw 500 for a predictable bad request. `POST` endpoints attempt a live price fetch before persisting (fail loudly, no garbage rows). `DELETE` is ownership-scoped at the SQL level (`WHERE id = %s AND device_id = %s`) — never trust a client-supplied ID alone.
- `GET` endpoints tolerate per-row fetch failures (one delisted/broken symbol goes into a `failed` list, doesn't fail the whole response) — matching `/api/dashboard`'s established pattern.
- Frontend (Node/Vite/React) files have no environment blocker — Node v24.18.0/npm work fine here; every frontend task is verified with a real `npm run build`.
- Reuse the existing color tokens and the existing `AssetCard`/`WhyPanel` components as-is (no signature changes to either) — the new UI is built by composing them, not modifying them.
- No automated test suite, consistent with the rest of `vercel-demo/` (an explicit, already-established decision).
- Spec: `docs/superpowers/specs/2026-08-04-holdings-watchlist-design.md`.
- All work happens inside `vercel-demo/` (paths below are relative to that directory unless stated otherwise).

---

### Task 1: Shared backend prep — fallback-keyword helper, sell/holding-period logic

**Files:**
- Modify: `vercel-demo/recommender.py`
- Modify: `vercel-demo/api/search.py`
- Create: `vercel-demo/holdings_logic.py`
- Modify: `vercel-demo/requirements.txt`

**Interfaces:**
- Produces: `recommender.derive_fallback_keyword(symbol: str) -> str` — the suffix-stripping (`.NS`/`.BO`/`-USD`) + lowercasing logic, extracted so it has one home instead of being reimplemented per caller. Consumed by `api/search.py` (Task 1 itself, refactored), `api/holdings.py` (Task 3), `api/watchlist.py` (Task 4).
- Produces: `holdings_logic.compute_sell_signal(scores: dict) -> dict` returning `{"action", "reason"}`. Consumed by Task 3.
- Produces: `holdings_logic.compute_holding_period(buy_date: date, symbol: str) -> dict` returning `{"days_held", "ltcg_applicable", "ltcg_eligible", "days_to_ltcg"}`. Consumed by Task 3.

- [ ] **Step 1: Add `derive_fallback_keyword` to `recommender.py`**

Add `import re` to the top-level imports (currently `from __future__ import annotations`, `import os`, `from typing import Dict, List`, `from sources import news as news_source`, `from sources import prices as prices_source` — add `import re` alongside `import os`).

Add this function immediately before `_compute_momentum`:

```python
_SYMBOL_SUFFIX_RE = re.compile(r"\.(NS|BO)$|-USD$", re.IGNORECASE)


def derive_fallback_keyword(symbol: str) -> str:
    return _SYMBOL_SUFFIX_RE.sub("", symbol).lower()
```

- [ ] **Step 2: Refactor `api/search.py` to reuse it**

In `vercel-demo/api/search.py`, remove this line (no longer needed — `re` is now only used inside `recommender.py`):
```python
_SUFFIX_RE = re.compile(r"\.(NS|BO)$|-USD$", re.IGNORECASE)
```
Also remove the now-unused `import re` line at the top of the file.

Replace this line inside `search_symbol`:
```python
    keyword = _SUFFIX_RE.sub("", symbol).lower()
```
with:
```python
    keyword = recommender.derive_fallback_keyword(symbol)
```

- [ ] **Step 3: Create `holdings_logic.py`**

```python
from __future__ import annotations

from datetime import date
from typing import Dict, Optional


def compute_sell_signal(scores: Dict[str, Dict[str, object]]) -> Dict[str, str]:
    short_term_score = scores["short_term"]["score"]
    swing_score = scores["swing"]["score"]

    if short_term_score < 0 and swing_score < 0:
        return {
            "action": "Consider selling",
            "reason": "Both short-term and long-term signals have turned negative.",
        }
    if short_term_score < 0 <= swing_score:
        return {
            "action": "Short-term weakness",
            "reason": "Short-term signal is negative but the long-term signal is still positive — your call whether to ride it out.",
        }
    if swing_score < 0 <= short_term_score:
        return {
            "action": "Long-term weakness",
            "reason": "Long-term signal is negative but short-term is still positive — may be worth watching closely.",
        }
    return {"action": "Hold", "reason": "Both short-term and long-term signals remain positive."}


def compute_holding_period(buy_date: date, symbol: str) -> Dict[str, Optional[object]]:
    days_held = (date.today() - buy_date).days
    # India's 365-day LTCG rule is specific to Indian equity (.NS/.BO). US
    # stocks (unsuffixed, e.g. AAPL) and crypto (-USD) both fall outside it
    # -- "not crypto" is not the same test as "is Indian equity" and would
    # mislabel a US holding with a tax rule that doesn't apply to it.
    ltcg_applicable = symbol.upper().endswith((".NS", ".BO"))
    if not ltcg_applicable:
        return {
            "days_held": days_held,
            "ltcg_applicable": False,
            "ltcg_eligible": None,
            "days_to_ltcg": None,
        }
    ltcg_eligible = days_held >= 365
    days_to_ltcg = max(0, 365 - days_held)
    return {
        "days_held": days_held,
        "ltcg_applicable": True,
        "ltcg_eligible": ltcg_eligible,
        "days_to_ltcg": days_to_ltcg,
    }
```

- [ ] **Step 4: Add `psycopg2-binary` to `requirements.txt`**

In `vercel-demo/requirements.txt`, add `psycopg2-binary>=2.9` to the requirements list (alongside `yfinance`, `feedparser`, `vaderSentiment`).

- [ ] **Step 5: Verify syntax**

Run from `vercel-demo/`:
```bash
python -c "
import ast
for f in ['recommender.py', 'api/search.py', 'holdings_logic.py']:
    ast.parse(open(f).read())
    print(f, 'OK')
"
```
Expected: all three print `OK`.

- [ ] **Step 6: Manual trace**

Confirm `derive_fallback_keyword("RELIANCE.NS")` → `"reliance"`, `derive_fallback_keyword("BTC-USD")` → `"btc"` (same behavior as the old `_SUFFIX_RE` in `search.py`, just relocated). Confirm `api/search.py` has no remaining reference to `_SUFFIX_RE` or a bare `import re`. Trace `compute_sell_signal({"short_term": {"score": -0.05}, "swing": {"score": 0.1}})` → `{"action": "Short-term weakness", ...}` (first score negative, second not). Trace `compute_holding_period(date(2025, 1, 1), "RELIANCE.NS")` with "today" far enough past 2026-01-01 that `days_held >= 365` → `.NS` suffix → `ltcg_applicable: True`, `ltcg_eligible: True`. Trace `compute_holding_period(date(2026, 7, 1), "BTC-USD")` → `-USD` suffix, not `.NS`/`.BO` → `ltcg_applicable: False`, `ltcg_eligible: None`, `days_to_ltcg: None`. Trace `compute_holding_period(date(2025, 1, 1), "AAPL")` (unsuffixed US equity) → also not `.NS`/`.BO` → `ltcg_applicable: False`, `ltcg_eligible: None`, `days_to_ltcg: None` — confirms US equities correctly get the same "not applicable" treatment as crypto, not the Indian-equity LTCG framing.

- [ ] **Step 7: Commit**

```bash
git add recommender.py api/search.py holdings_logic.py requirements.txt
git commit -m "Extract derive_fallback_keyword, add holdings_logic (sell signal + LTCG math)"
```

---

### Task 2: Database schema and connection helper

**Files:**
- Create: `vercel-demo/schema.sql`
- Create: `vercel-demo/db.py`

**Interfaces:**
- Produces: `db.get_connection()` — returns a `psycopg2` connection with `RealDictCursor` (rows come back as dicts, not tuples), reading the connection string from `DATABASE_URL` or `POSTGRES_URL`. Raises `RuntimeError` with a clear message if neither is set. Consumed by Task 3 (`api/holdings.py`) and Task 4 (`api/watchlist.py`).

- [ ] **Step 1: Write `schema.sql`**

```sql
CREATE TABLE IF NOT EXISTS holdings (
    id SERIAL PRIMARY KEY,
    device_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    buy_price NUMERIC NOT NULL,
    quantity NUMERIC NOT NULL,
    buy_date DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_holdings_device_id ON holdings(device_id);

CREATE TABLE IF NOT EXISTS watchlist (
    id SERIAL PRIMARY KEY,
    device_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (device_id, symbol)
);
CREATE INDEX IF NOT EXISTS idx_watchlist_device_id ON watchlist(device_id);
```

- [ ] **Step 2: Write `db.py`**

```python
from __future__ import annotations

import os

import psycopg2
import psycopg2.extras


def get_connection():
    dsn = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
    if not dsn:
        raise RuntimeError(
            "No database connection string found. Set DATABASE_URL or POSTGRES_URL "
            "to the pooled Postgres connection string from the Vercel dashboard's "
            "Storage tab."
        )
    return psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)
```

- [ ] **Step 3: Verify syntax**

Run from `vercel-demo/`: `python -c "import ast; ast.parse(open('db.py').read()); print('OK')"`
Expected: `OK`. Do not attempt `python -c "import db"` or anything that would actually import `psycopg2` — per the Global Constraints, this cannot be verified on this machine.

- [ ] **Step 4: Manual trace**

Confirm `get_connection()` checks `DATABASE_URL` first, falls back to `POSTGRES_URL`, and raises a clear `RuntimeError` (not a bare `KeyError` or silent `None` DSN passed to `psycopg2.connect`) when neither is set. Confirm `schema.sql`'s two `CREATE TABLE IF NOT EXISTS` statements are idempotent (safe to run more than once) and that `watchlist`'s `UNIQUE (device_id, symbol)` constraint matches the spec's decision that a symbol is either watched or not, no duplicate rows.

- [ ] **Step 5: Commit**

```bash
git add schema.sql db.py
git commit -m "Add Postgres schema and connection helper for holdings/watchlist"
```

---

### Task 3: `api/holdings.py`

**Files:**
- Create: `vercel-demo/api/holdings.py`

**Interfaces:**
- Produces: `GET /api/holdings` (header `X-Device-Id` required) → `200 {"holdings": [...], "failed": [...]}`. Each holding: `{id, symbol, buy_price, quantity, buy_date, current_price, unrealized_pnl, unrealized_pnl_pct, days_held, ltcg_applicable, ltcg_eligible, days_to_ltcg, momentum, momentum_detail, sentiment, day_change_pct, matched_headlines, scores, sell_signal}`.
- Produces: `POST /api/holdings` (header + JSON body `{symbol, buy_price, quantity, buy_date}`) → `201` with the inserted row `{id, symbol, buy_price, quantity, buy_date}`, or `400`/`502` on validation/fetch failure.
- Produces: `DELETE /api/holdings?id=N` (header required) → `204` on success, `404` if no matching row for this device.
- Consumes: `db.get_connection()` (Task 2), `recommender.build_asset_payload`/`derive_fallback_keyword` (existing + Task 1), `holdings_logic.compute_sell_signal`/`compute_holding_period` (Task 1), `sources.prices.fetch_price_history`, `sources.news.fetch_headlines`.

- [ ] **Step 1: Write `api/holdings.py`**

```python
from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import db
import recommender
from holdings_logic import compute_holding_period, compute_sell_signal
from sources import news as news_source
from sources import prices as prices_source

# Demo-only override: see api/dashboard.py for why.
recommender.RSS_FEEDS = ["https://finance.yahoo.com/news/rssindex"]


def _device_id_from_headers(headers) -> str:
    device_id = (headers.get("X-Device-Id") or "").strip()
    if not device_id:
        raise ValueError("Missing X-Device-Id header")
    return device_id


def _build_holding_result(row, headlines):
    symbol = row["symbol"]
    asset = {"symbol": symbol, "type": None, "keywords": [recommender.derive_fallback_keyword(symbol)]}
    closes = prices_source.fetch_price_history(symbol)
    payload = recommender.build_asset_payload(asset, closes, headlines)

    current_price = closes[-1]
    buy_price = float(row["buy_price"])
    quantity = float(row["quantity"])
    period = compute_holding_period(row["buy_date"], symbol)
    sell_signal = compute_sell_signal(payload["scores"])

    return {
        "id": row["id"],
        "symbol": symbol,
        "buy_price": buy_price,
        "quantity": quantity,
        "buy_date": row["buy_date"].isoformat(),
        "current_price": round(current_price, 2),
        "unrealized_pnl": round((current_price - buy_price) * quantity, 2),
        "unrealized_pnl_pct": round((current_price - buy_price) / buy_price * 100, 2),
        "days_held": period["days_held"],
        "ltcg_applicable": period["ltcg_applicable"],
        "ltcg_eligible": period["ltcg_eligible"],
        "days_to_ltcg": period["days_to_ltcg"],
        "momentum": payload["momentum"],
        "momentum_detail": payload["momentum_detail"],
        "sentiment": payload["sentiment"],
        "day_change_pct": payload["day_change_pct"],
        "matched_headlines": payload["matched_headlines"],
        "scores": payload["scores"],
        "sell_signal": sell_signal,
    }


def list_holdings(device_id):
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, symbol, buy_price, quantity, buy_date FROM holdings "
                "WHERE device_id = %s ORDER BY created_at DESC",
                (device_id,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    try:
        headlines = news_source.fetch_headlines(recommender.RSS_FEEDS)
    except RuntimeError:
        headlines = []

    holdings = []
    failed = []
    for row in rows:
        try:
            holdings.append(_build_holding_result(row, headlines))
        except Exception as exc:
            failed.append({"id": row["id"], "symbol": row["symbol"], "error": str(exc)})
    return {"holdings": holdings, "failed": failed}


def add_holding(device_id, body):
    symbol = str(body.get("symbol", "")).strip().upper()
    if not symbol:
        raise ValueError("symbol is required")

    try:
        buy_price = float(body["buy_price"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("buy_price must be a positive number")
    if buy_price <= 0:
        raise ValueError("buy_price must be a positive number")

    try:
        quantity = float(body["quantity"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("quantity must be a positive number")
    if quantity <= 0:
        raise ValueError("quantity must be a positive number")

    try:
        buy_date = datetime.strptime(str(body.get("buy_date", "")), "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("buy_date must be in YYYY-MM-DD format")
    if buy_date > date.today():
        raise ValueError("buy_date cannot be in the future")

    # Fail loudly if the symbol isn't fetchable, before persisting anything.
    prices_source.fetch_price_history(symbol)

    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO holdings (device_id, symbol, buy_price, quantity, buy_date) "
                "VALUES (%s, %s, %s, %s, %s) RETURNING id, symbol, buy_price, quantity, buy_date",
                (device_id, symbol, buy_price, quantity, buy_date),
            )
            row = cur.fetchone()
        conn.commit()
    finally:
        conn.close()

    return {
        "id": row["id"],
        "symbol": row["symbol"],
        "buy_price": float(row["buy_price"]),
        "quantity": float(row["quantity"]),
        "buy_date": row["buy_date"].isoformat(),
    }


def delete_holding(device_id, holding_id):
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM holdings WHERE id = %s AND device_id = %s RETURNING id",
                (holding_id, device_id),
            )
            row = cur.fetchone()
        conn.commit()
    finally:
        conn.close()
    if row is None:
        raise LookupError("Holding not found")


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            device_id = _device_id_from_headers(self.headers)
            payload = list_holdings(device_id)
            status = 200
        except ValueError as exc:
            payload = {"error": str(exc)}
            status = 400
        except Exception as exc:
            payload = {"error": str(exc), "traceback": traceback.format_exc()}
            status = 500
        self._send_json(status, payload)

    def do_POST(self):
        try:
            device_id = _device_id_from_headers(self.headers)
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            payload = add_holding(device_id, body)
            status = 201
        except ValueError as exc:
            payload = {"error": str(exc)}
            status = 400
        except RuntimeError as exc:
            payload = {"error": str(exc)}
            status = 502
        except Exception as exc:
            payload = {"error": str(exc), "traceback": traceback.format_exc()}
            status = 500
        self._send_json(status, payload)

    def do_DELETE(self):
        try:
            device_id = _device_id_from_headers(self.headers)
            query = parse_qs(urlparse(self.path).query)
            raw_id = query.get("id", [""])[0]
            if not raw_id.isdigit():
                raise ValueError("Query parameter 'id' must be a positive integer")
            delete_holding(device_id, int(raw_id))
            payload = {"deleted": True}
            status = 204
        except ValueError as exc:
            payload = {"error": str(exc)}
            status = 400
        except LookupError as exc:
            payload = {"error": str(exc)}
            status = 404
        except Exception as exc:
            payload = {"error": str(exc), "traceback": traceback.format_exc()}
            status = 500
        self._send_json(status, payload)

    def _send_json(self, status, payload):
        body = b"" if status == 204 else json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "X-Device-Id, Content-Type")
        self.end_headers()
        if body:
            self.wfile.write(body)
```

- [ ] **Step 2: Verify syntax**

Run: `python -c "import ast; ast.parse(open('api/holdings.py').read()); print('OK')"` from `vercel-demo/`.
Expected: `OK`.

- [ ] **Step 3: Manual trace**

Trace `add_holding` with a missing `buy_price` key in `body` → `KeyError` caught by the `except (KeyError, TypeError, ValueError)` → re-raised as `ValueError("buy_price must be a positive number")` → `do_POST` catches `ValueError` → `400`. Trace with `buy_date` one day in the future → passes the `strptime` parse, fails the `buy_date > date.today()` check → `ValueError` → `400`. Trace `delete_holding` for an `id` that exists but belongs to a different `device_id` → the `WHERE id = %s AND device_id = %s` matches zero rows → `cur.fetchone()` returns `None` → `LookupError("Holding not found")` → `do_DELETE` catches `LookupError` → `404` (confirms cross-device deletion is impossible even with a guessed ID). Trace `list_holdings` when `fetch_headlines` raises `RuntimeError` → caught, `headlines = []` — every holding's `sentiment` still computes via `build_asset_payload` (which handles an empty headline list as neutral, established in Task 1 of the earlier dashboard plan), so the endpoint degrades gracefully rather than 500ing.

- [ ] **Step 4: Commit**

```bash
git add api/holdings.py
git commit -m "Add GET/POST/DELETE /api/holdings (P&L, LTCG context, sell signal)"
```

---

### Task 4: `api/watchlist.py`

**Files:**
- Create: `vercel-demo/api/watchlist.py`

**Interfaces:**
- Produces: `GET /api/watchlist` (header required) → `200 {"watchlist": [...], "failed": [...]}`. Each item: `{id, symbol, momentum, momentum_detail, sentiment, day_change_pct, matched_headlines, scores}` — same shape as one `/api/dashboard` asset entry, plus `id`.
- Produces: `POST /api/watchlist` (header + JSON body `{symbol}`) → `201` with `{id, symbol}`, `409` if already present for this device, `502` on fetch failure.
- Produces: `DELETE /api/watchlist?id=N` (header required) → `204`, `404` if not found for this device.
- Consumes: same shared pieces as Task 3.

- [ ] **Step 1: Write `api/watchlist.py`**

```python
from __future__ import annotations

import json
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import db
import recommender
from sources import news as news_source
from sources import prices as prices_source

# Demo-only override: see api/dashboard.py for why.
recommender.RSS_FEEDS = ["https://finance.yahoo.com/news/rssindex"]


def _device_id_from_headers(headers) -> str:
    device_id = (headers.get("X-Device-Id") or "").strip()
    if not device_id:
        raise ValueError("Missing X-Device-Id header")
    return device_id


def list_watchlist(device_id):
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, symbol FROM watchlist WHERE device_id = %s ORDER BY created_at DESC",
                (device_id,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    try:
        headlines = news_source.fetch_headlines(recommender.RSS_FEEDS)
    except RuntimeError:
        headlines = []

    watchlist = []
    failed = []
    for row in rows:
        symbol = row["symbol"]
        try:
            asset = {
                "symbol": symbol,
                "type": None,
                "keywords": [recommender.derive_fallback_keyword(symbol)],
            }
            closes = prices_source.fetch_price_history(symbol)
            payload = recommender.build_asset_payload(asset, closes, headlines)
            watchlist.append({"id": row["id"], **payload})
        except Exception as exc:
            failed.append({"id": row["id"], "symbol": symbol, "error": str(exc)})
    return {"watchlist": watchlist, "failed": failed}


def add_to_watchlist(device_id, body):
    symbol = str(body.get("symbol", "")).strip().upper()
    if not symbol:
        raise ValueError("symbol is required")

    # Fail loudly if the symbol isn't fetchable, before persisting anything.
    prices_source.fetch_price_history(symbol)

    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM watchlist WHERE device_id = %s AND symbol = %s",
                (device_id, symbol),
            )
            if cur.fetchone() is not None:
                raise LookupError("already in your watchlist")
            cur.execute(
                "INSERT INTO watchlist (device_id, symbol) VALUES (%s, %s) RETURNING id, symbol",
                (device_id, symbol),
            )
            row = cur.fetchone()
        conn.commit()
    finally:
        conn.close()

    return {"id": row["id"], "symbol": row["symbol"]}


def delete_from_watchlist(device_id, watchlist_id):
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM watchlist WHERE id = %s AND device_id = %s RETURNING id",
                (watchlist_id, device_id),
            )
            row = cur.fetchone()
        conn.commit()
    finally:
        conn.close()
    if row is None:
        raise LookupError("Watchlist entry not found")


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            device_id = _device_id_from_headers(self.headers)
            payload = list_watchlist(device_id)
            status = 200
        except ValueError as exc:
            payload = {"error": str(exc)}
            status = 400
        except Exception as exc:
            payload = {"error": str(exc), "traceback": traceback.format_exc()}
            status = 500
        self._send_json(status, payload)

    def do_POST(self):
        try:
            device_id = _device_id_from_headers(self.headers)
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            payload = add_to_watchlist(device_id, body)
            status = 201
        except ValueError as exc:
            payload = {"error": str(exc)}
            status = 400
        except LookupError as exc:
            payload = {"error": str(exc)}
            status = 409
        except RuntimeError as exc:
            payload = {"error": str(exc)}
            status = 502
        except Exception as exc:
            payload = {"error": str(exc), "traceback": traceback.format_exc()}
            status = 500
        self._send_json(status, payload)

    def do_DELETE(self):
        try:
            device_id = _device_id_from_headers(self.headers)
            query = parse_qs(urlparse(self.path).query)
            raw_id = query.get("id", [""])[0]
            if not raw_id.isdigit():
                raise ValueError("Query parameter 'id' must be a positive integer")
            delete_from_watchlist(device_id, int(raw_id))
            payload = {"deleted": True}
            status = 204
        except ValueError as exc:
            payload = {"error": str(exc)}
            status = 400
        except LookupError as exc:
            payload = {"error": str(exc)}
            status = 404
        except Exception as exc:
            payload = {"error": str(exc), "traceback": traceback.format_exc()}
            status = 500
        self._send_json(status, payload)

    def _send_json(self, status, payload):
        body = b"" if status == 204 else json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "X-Device-Id, Content-Type")
        self.end_headers()
        if body:
            self.wfile.write(body)
```

- [ ] **Step 2: Verify syntax**

Run: `python -c "import ast; ast.parse(open('api/watchlist.py').read()); print('OK')"` from `vercel-demo/`.
Expected: `OK`.

- [ ] **Step 3: Manual trace**

Trace `add_to_watchlist` when the symbol already exists for this `device_id` → the `SELECT 1 ...` finds a row → `LookupError("already in your watchlist")` raised **before** any `INSERT` is attempted → `do_POST` catches `LookupError` → `409`. Confirm this check-then-insert happens inside the same connection/transaction (no race between the `SELECT` and `INSERT` from this single request), and that the table's `UNIQUE (device_id, symbol)` constraint (Task 2) is a backstop against genuine concurrent double-adds even though the explicit check handles the common case with a friendly message rather than a raw constraint-violation error. Trace `list_watchlist` per-item failure: if `fetch_price_history` raises for one row, that row goes to `failed`, the loop continues to the next row (not aborted) — same pattern independently verified in Task 3.

- [ ] **Step 4: Commit**

```bash
git add api/watchlist.py
git commit -m "Add GET/POST/DELETE /api/watchlist"
```

---

### Task 5: Frontend — device ID and shared API helper

**Files:**
- Create: `vercel-demo/src/lib/deviceId.js`
- Create: `vercel-demo/src/lib/api.js`

**Interfaces:**
- Produces: `getDeviceId(): string` — reads/creates a persistent random ID in `localStorage`. Consumed by `api.js` (this task) and indirectly by every holdings/watchlist component.
- Produces: `apiFetch(path: string, options？: RequestInit): Promise<any>` — wraps `fetch`, attaches `X-Device-Id` (and `Content-Type: application/json` when a body is present), throws with the server's `error` message on a non-OK response, returns `null` for a `204`. Consumed by Task 6 (Holdings) and Task 7 (PersonalWatchlist).

- [ ] **Step 1: Write `src/lib/deviceId.js`**

```js
export function getDeviceId() {
  let id = localStorage.getItem("quantdesk_device_id");
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem("quantdesk_device_id", id);
  }
  return id;
}
```

- [ ] **Step 2: Write `src/lib/api.js`**

```js
import { getDeviceId } from "./deviceId.js";

export async function apiFetch(path, options = {}) {
  const headers = {
    "X-Device-Id": getDeviceId(),
    ...(options.body ? { "Content-Type": "application/json" } : {}),
    ...options.headers,
  };

  const res = await fetch(path, { ...options, headers });

  if (res.status === 204) {
    return null;
  }

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || `Request failed (${res.status})`);
  }
  return data;
}
```

- [ ] **Step 3: Verify — real build**

Run from `vercel-demo/`: `npm run build`
Expected: exits 0 (these two files aren't imported anywhere yet, so this just confirms no syntax errors).

- [ ] **Step 4: Commit**

```bash
git add src/lib/deviceId.js src/lib/api.js
git commit -m "Add device-ID identity and shared apiFetch helper"
```

---

### Task 6: Frontend — Holdings tab

**Files:**
- Create: `vercel-demo/src/components/HoldingCard.jsx`
- Create: `vercel-demo/src/components/Holdings.jsx`
- Modify: `vercel-demo/src/index.css`

**Interfaces:**
- Consumes: `apiFetch` (Task 5), `WhyPanel` (existing, unmodified).
- Produces: `<Holdings />` — self-contained (fetches on mount, owns its own add-form/list/delete state). Consumed by Task 8 (`App.jsx`).

- [ ] **Step 1: Write `src/components/HoldingCard.jsx`**

```jsx
import { useState } from "react";
import WhyPanel from "./WhyPanel.jsx";

const SELL_SIGNAL_COLORS = {
  "Consider selling": "var(--negative)",
  "Short-term weakness": "var(--warning)",
  "Long-term weakness": "var(--warning)",
  Hold: "var(--positive)",
};

export default function HoldingCard({ holding, onDelete }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="asset-card holding-card">
      <div className="asset-card-row" onClick={() => setExpanded(!expanded)}>
        <div className="asset-card-main">
          <span className="asset-symbol">{holding.symbol}</span>
          <span className="holding-qty">
            {holding.quantity} @ ₹{holding.buy_price}
          </span>
        </div>
        <div className="asset-card-stats">
          <span
            className="holding-pnl"
            style={{ color: holding.unrealized_pnl >= 0 ? "var(--positive)" : "var(--negative)" }}
          >
            {holding.unrealized_pnl >= 0 ? "+" : ""}
            ₹{holding.unrealized_pnl.toLocaleString("en-IN")} ({holding.unrealized_pnl_pct.toFixed(1)}%)
          </span>
          <span
            className="asset-action"
            style={{ color: SELL_SIGNAL_COLORS[holding.sell_signal.action] || "var(--text-muted)" }}
          >
            {holding.sell_signal.action}
          </span>
          <span className="asset-expand-icon">{expanded ? "▲" : "▼"}</span>
        </div>
      </div>
      <div className="holding-meta">
        <span>{holding.days_held} days held</span>
        {holding.ltcg_applicable ? (
          <span>
            {holding.ltcg_eligible ? "Long-term eligible" : `${holding.days_to_ltcg} days to long-term`}
          </span>
        ) : (
          <span>N/A — India LTCG applies to .NS/.BO equity only</span>
        )}
        <button
          type="button"
          className="delete-button"
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
        >
          Remove
        </button>
      </div>
      {expanded && (
        <div className="holding-why">
          <p className="why-sell-reason">{holding.sell_signal.reason}</p>
          <WhyPanel asset={holding} style="short_term" />
          <WhyPanel asset={holding} style="swing" />
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Write `src/components/Holdings.jsx`**

```jsx
import { useEffect, useState } from "react";
import { apiFetch } from "../lib/api.js";
import HoldingCard from "./HoldingCard.jsx";

export default function Holdings() {
  const [holdings, setHoldings] = useState(null);
  const [failed, setFailed] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ symbol: "", buy_price: "", quantity: "", buy_date: "" });
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState(null);

  const load = () => {
    setLoading(true);
    apiFetch("/api/holdings")
      .then((data) => {
        setHoldings(data.holdings);
        setFailed(data.failed);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleAdd = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setFormError(null);
    try {
      await apiFetch("/api/holdings", {
        method: "POST",
        body: JSON.stringify({
          symbol: form.symbol.trim(),
          buy_price: Number(form.buy_price),
          quantity: Number(form.quantity),
          buy_date: form.buy_date,
        }),
      });
      setForm({ symbol: "", buy_price: "", quantity: "", buy_date: "" });
      load();
    } catch (err) {
      setFormError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id) => {
    try {
      await apiFetch(`/api/holdings?id=${id}`, { method: "DELETE" });
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="holdings-tab">
      <form className="add-form" onSubmit={handleAdd}>
        <input
          type="text"
          placeholder="Symbol (e.g. RELIANCE.NS)"
          value={form.symbol}
          onChange={(e) => setForm({ ...form, symbol: e.target.value })}
          required
        />
        <input
          type="number"
          step="0.01"
          placeholder="Buy price"
          value={form.buy_price}
          onChange={(e) => setForm({ ...form, buy_price: e.target.value })}
          required
        />
        <input
          type="number"
          step="1"
          placeholder="Quantity"
          value={form.quantity}
          onChange={(e) => setForm({ ...form, quantity: e.target.value })}
          required
        />
        <input
          type="date"
          value={form.buy_date}
          onChange={(e) => setForm({ ...form, buy_date: e.target.value })}
          required
        />
        <button type="submit" disabled={submitting}>
          {submitting ? "Adding…" : "Add holding"}
        </button>
      </form>
      {formError && <p className="error-text">{formError}</p>}

      {loading && <p>Loading your holdings…</p>}
      {error && <p className="error-text">{error}</p>}
      {failed.length > 0 && (
        <p className="warning-text">
          {failed.length} holding(s) unavailable right now: {failed.map((f) => f.symbol).join(", ")}
        </p>
      )}

      {holdings && holdings.length === 0 && <p className="empty-state">No holdings yet — add one above.</p>}
      {holdings && holdings.length > 0 && (
        <div className="holdings-list">
          {holdings.map((h) => (
            <HoldingCard key={h.id} holding={h} onDelete={() => handleDelete(h.id)} />
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Append holdings styles to `src/index.css`**

```css
.add-form {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-bottom: 1rem;
}

.add-form input {
  padding: 0.55rem 0.75rem;
  border-radius: 8px;
  border: 1px solid var(--card-border);
  background: var(--card);
  color: var(--text);
  font-size: 0.9rem;
}

.add-form button {
  padding: 0.55rem 1.1rem;
  border-radius: 8px;
  border: none;
  background: var(--accent);
  color: #07111f;
  font-weight: 600;
  cursor: pointer;
}

.add-form button:disabled {
  opacity: 0.6;
  cursor: default;
}

.empty-state {
  color: var(--text-muted);
  font-style: italic;
}

.holdings-list {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.holding-qty {
  font-size: 0.8rem;
  color: var(--text-muted);
}

.holding-pnl {
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.holding-meta {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0 1rem 0.75rem;
  font-size: 0.8rem;
  color: var(--text-muted);
}

.delete-button {
  margin-left: auto;
  padding: 0.3rem 0.75rem;
  border-radius: 6px;
  border: 1px solid var(--negative);
  background: transparent;
  color: var(--negative);
  cursor: pointer;
  font-size: 0.8rem;
}

.holding-why {
  padding: 0 1rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.why-sell-reason {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.85rem;
  font-style: italic;
}
```

- [ ] **Step 4: Verify — real build**

Run from `vercel-demo/`: `npm run build`
Expected: exits 0. (`Holdings`/`HoldingCard` aren't rendered anywhere yet — Task 8 wires them in — so this only confirms no syntax errors.)

- [ ] **Step 5: Commit**

```bash
git add src/components/HoldingCard.jsx src/components/Holdings.jsx src/index.css
git commit -m "Add Holdings tab (add form, P&L, LTCG context, sell signal, delete)"
```

---

### Task 7: Frontend — personal Watchlist tab

**Files:**
- Create: `vercel-demo/src/components/PersonalWatchlist.jsx`
- Modify: `vercel-demo/src/index.css`

**Interfaces:**
- Consumes: `apiFetch` (Task 5), `AssetCard` (existing, unmodified).
- Produces: `<PersonalWatchlist />` — self-contained. Consumed by Task 8.

- [ ] **Step 1: Write `src/components/PersonalWatchlist.jsx`**

```jsx
import { useEffect, useState } from "react";
import { apiFetch } from "../lib/api.js";
import AssetCard from "./AssetCard.jsx";

const STYLES = ["intraday", "short_term", "swing"];

export default function PersonalWatchlist() {
  const [items, setItems] = useState(null);
  const [failed, setFailed] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [symbol, setSymbol] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState(null);

  const load = () => {
    setLoading(true);
    apiFetch("/api/watchlist")
      .then((data) => {
        setItems(data.watchlist);
        setFailed(data.failed);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleAdd = async (e) => {
    e.preventDefault();
    if (!symbol.trim()) return;
    setSubmitting(true);
    setFormError(null);
    try {
      await apiFetch("/api/watchlist", {
        method: "POST",
        body: JSON.stringify({ symbol: symbol.trim() }),
      });
      setSymbol("");
      load();
    } catch (err) {
      setFormError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id) => {
    try {
      await apiFetch(`/api/watchlist?id=${id}`, { method: "DELETE" });
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="watchlist-tab">
      <form className="add-form" onSubmit={handleAdd}>
        <input
          type="text"
          placeholder="Symbol to watch (e.g. TATASTEEL.NS)"
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          required
        />
        <button type="submit" disabled={submitting}>
          {submitting ? "Adding…" : "Add to watchlist"}
        </button>
      </form>
      {formError && <p className="error-text">{formError}</p>}

      {loading && <p>Loading your watchlist…</p>}
      {error && <p className="error-text">{error}</p>}
      {failed.length > 0 && (
        <p className="warning-text">
          {failed.length} symbol(s) unavailable right now: {failed.map((f) => f.symbol).join(", ")}
        </p>
      )}

      {items && items.length === 0 && (
        <p className="empty-state">Your watchlist is empty — add a symbol above.</p>
      )}
      {items && items.length > 0 && (
        <div className="watchlist-list">
          {items.map((item) => (
            <div key={item.id} className="watchlist-item">
              <div className="watchlist-item-header">
                <span className="watchlist-item-symbol">{item.symbol}</span>
                <button type="button" className="delete-button" onClick={() => handleDelete(item.id)}>
                  Remove
                </button>
              </div>
              <div className="watchlist-item-cards">
                {STYLES.map((style) => (
                  <AssetCard key={style} asset={item} style={style} suggested={undefined} showStyleLabel />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Append watchlist-tab styles to `src/index.css`**

```css
.watchlist-list {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.watchlist-item-header {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 0.5rem;
}

.watchlist-item-symbol {
  font-weight: 700;
  font-size: 1.1rem;
}

.watchlist-item-cards {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
```

- [ ] **Step 3: Verify — real build**

Run from `vercel-demo/`: `npm run build`
Expected: exits 0.

- [ ] **Step 4: Commit**

```bash
git add src/components/PersonalWatchlist.jsx src/index.css
git commit -m "Add personal Watchlist tab (add form, 3-style cards per symbol, delete)"
```

---

### Task 8: Wire both new tabs into `App.jsx`

**Files:**
- Modify: `vercel-demo/src/App.jsx`

**Interfaces:** None new — this task only wires together components already built.

- [ ] **Step 1: Add imports**

In `src/App.jsx`, add these two imports alongside the existing component imports:
```jsx
import Holdings from "./components/Holdings.jsx";
import PersonalWatchlist from "./components/PersonalWatchlist.jsx";
```

- [ ] **Step 2: Extend the `TABS` array**

Replace the current `TABS` array (4 entries: `intraday`/`short_term`/`swing`/`movers`) with:
```jsx
const TABS = [
  { key: "intraday", label: "Day Trading" },
  { key: "short_term", label: "Short-Term" },
  { key: "swing", label: "Swing / Long-Term" },
  { key: "movers", label: "Top Movers" },
  { key: "holdings", label: "My Holdings" },
  { key: "watchlist", label: "My Watchlist" },
];
```

- [ ] **Step 3: Extend the render branch**

Replace:
```jsx
          {activeTab === "movers" ? (
            <TopMovers assets={dashboard.assets} />
          ) : (
            <StyleSection assets={dashboard.assets} style={activeTab} capital={capital} />
          )}
```
with:
```jsx
          {activeTab === "movers" ? (
            <TopMovers assets={dashboard.assets} />
          ) : activeTab === "holdings" ? (
            <Holdings />
          ) : activeTab === "watchlist" ? (
            <PersonalWatchlist />
          ) : (
            <StyleSection assets={dashboard.assets} style={activeTab} capital={capital} />
          )}
```

`Holdings` and `PersonalWatchlist` are self-contained (they fetch their own data via `apiFetch`, independent of `dashboard.assets`) — no new props needed on either.

- [ ] **Step 4: Verify — real build**

Run from `vercel-demo/`: `npm run build`
Expected: exits 0, 6 tabs present.

- [ ] **Step 5: Commit**

```bash
git add src/App.jsx
git commit -m "Wire Holdings and personal Watchlist into the tab bar"
```

---

### Task 9: Final verification and database setup checklist

**Files:** None new — final review pass over what's already built.

**Interfaces:** None.

- [ ] **Step 1: Full real build, one more time**

Run from `vercel-demo/`: `rm -rf node_modules dist && npm install && npm run build`
Expected: exits 0 end to end.

- [ ] **Step 2: Python syntax check across all new/modified backend files**

Run from `vercel-demo/`:
```bash
python -c "
import ast
for f in ['recommender.py', 'holdings_logic.py', 'db.py', 'api/search.py', 'api/holdings.py', 'api/watchlist.py']:
    ast.parse(open(f).read())
    print(f, 'OK')
"
```
Expected: all six print `OK`.

- [ ] **Step 3: Database setup checklist (for the human partner — cannot be done from this session)**

Document these steps in the task report; they must be performed manually before the new endpoints can work at all:

1. In the Vercel dashboard, open the project's **Storage** tab → create a new **Postgres** database → attach it to this project.
2. Note which environment variable name Vercel populated for the connection strings (visible in the Storage tab's connection-details panel — commonly `DATABASE_URL` or `POSTGRES_URL`, but confirm the actual name rather than assuming). Use the **pooled** variant if more than one is offered.
3. Using any Postgres client (Vercel's own dashboard query editor is simplest), run the full contents of `vercel-demo/schema.sql` once against the new database to create the `holdings` and `watchlist` tables.
4. Redeploy (or trigger a new deployment) so the running functions pick up the new environment variable.

- [ ] **Step 4: Manual verification checklist (for the human partner, once Step 3 is done and deployed)**

1. Open **My Holdings**, add a holding (a real symbol, a plausible buy price, quantity, and a past date) — confirm it appears with live current price, P&L, days-held, LTCG context, and a sell signal (not a raw error).
2. Add the *same* symbol to **My Watchlist** — confirm it appears there too, independently, with its own 3-style cards.
3. Delete the holding, then delete the watchlist entry — confirm each disappears immediately and doesn't reappear on next load.
4. Reload the page entirely (not just re-render) — confirm both lists (if you re-add an entry first) persist, proving the database round-trip actually works rather than just React state.
5. Try adding an obviously invalid symbol (e.g. `ZZZZZZZ`) to each list — confirm a clear rejection message, not a silently-saved broken row.
6. Open the dashboard in a different browser or an incognito window — confirm both lists show empty there, proving device-ID scoping actually isolates data per browser rather than sharing one global list.

- [ ] **Step 5: Report results**

Summarize in the task report: build/syntax status (Steps 1-2), and that Steps 3-4 are documented for the human partner to perform post-deployment (this session cannot provision cloud infrastructure or exercise a live database). No commit needed for this task.
