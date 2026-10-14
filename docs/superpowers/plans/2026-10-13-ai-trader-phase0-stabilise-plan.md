# AI Trader Phase 0: Stabilise the Existing Repository (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing QuantDesk code base a safe foundation for AI Trader:
- one canonical code path;
- API errors that never leak internals;
- a fail-closed cron endpoint;
- no wildcard CORS;
- pinned dependencies;
- CI.

Every existing feature must keep working.

**Architecture:** `vercel-demo/` becomes the single canonical Python source tree, because Vercel deploys it. The root-level duplicates (`recommender.py`, `backtest.py`, `sources/`) are removed after their CLI behaviour is ported. A small `vercel-demo/http_utils.py` module centralises:
- JSON responses;
- request-body limits;
- device-ID parsing;
- CORS policy;
- safe internal-error handling.

Every `api/*.py` handler uses it. Handler tests drive the real `BaseHTTPRequestHandler` subclasses in-process through a test harness, with no socket, database, or network.

**Tech Stack:**
- Python with `http.server` handlers (the Vercel `/api` directory convention), psycopg2, yfinance, feedparser, VADER;
- pytest;
- React 18 + Vite 5;
- GitHub Actions.

**Spec:** [AI_Trader_README.md](../../../AI_Trader_README.md) §11 "Phase 0 — Stabilise the existing repository" and §13. Context: [docs/AI_TRADER_PROJECT_DISCOVERY.md](../../AI_TRADER_PROJECT_DISCOVERY.md) §11, §12, and §16 row 0.

## Global Constraints

- Phase 0 scope (spec, verbatim): "Inspect Git state and user changes, establish a test/build baseline, consolidate duplicate code paths carefully, improve API error handling, require cron authentication, configure safe CORS, pin dependencies, and add CI."
- Gate (spec, verbatim): "Existing features still work; tests and frontend build pass; sensitive data is protected; no regression is knowingly hidden."
- "Start with Phase 0 only." Do not start Kite, options, Claude, or any Phase 1+ work.
- "Never place live trades or enable live order execution."
- "Do not ask for API secrets in chat." Never print `.env` values or secret environment variables.
- "Make small, reviewable changes with tests." "Run the relevant tests and build after each phase."
- Final report must list "exact files changed, tests run, outcomes, assumptions, and remaining risks."
- Do not change strategy or scoring behaviour. Known strategy bugs (dead delivery-% confirmation branch, promoter-holding proxy) are recorded as remaining risks, not fixed here.
- Work on branch `phase0-stabilise`. Do not push, merge, or deploy without the user's explicit approval.
- Baseline before any change (verified 2026-10-13): `python -m pytest -q` gives **34 passed**, and `npm run build` in `vercel-demo/` **succeeds**.

## Review Focus

1. **The legitimate Vercel cron call must still succeed.** With `CRON_SECRET` set, a request carrying `Authorization: Bearer <secret>` must run the screen (200). Only missing or wrong tokens are refused. Tested in Task 5.
2. **Garbled or oversized request bodies** (non-numeric `Content-Length`, invalid JSON, a JSON array, or a body over 64 KiB) must return 400 or 413, never 500. Oversized bodies must not be read into memory. Tested in Tasks 3 and 4.
3. **Bad backtest query parameters** (`short=abc`, `short >= long`, or a long window greater than the available history) must return 400 with a readable message, never 500 with a traceback. Tested in Task 4.
4. **An unexpected exception anywhere** must return `{"error": "Internal server error"}` to the client, while the full traceback goes to the server log (stderr / Vercel function logs). Tested in Tasks 3 and 4.
5. **The same-origin SPA must keep working with no CORS headers.** An `Origin` listed in `ALLOWED_ORIGINS` gets it echoed back, and an unlisted origin gets nothing. Tested in Tasks 3 and 4.

---

## File structure

| File | Action | Responsibility |
|---|---|---|
| `tests/conftest.py` | Create | Puts `vercel-demo/` first on `sys.path` so tests import the canonical modules. |
| `tests/api_harness.py` | Create | Loads `api/*.py` modules by path and drives a handler in-process. Provides a fake DB connection. |
| `vercel-demo/http_utils.py` | Create | `HttpError`, `device_id_from_headers`, `read_json_object`, `allowed_origin`, `internal_error`, `send_json`, `send_text`, `bearer_token_matches`. |
| `vercel-demo/recommender.py` | Modify | Canonical `RSS_FEEDS`. Gains `write_dashboard` and dashboard output in `main` (ported from root). |
| `vercel-demo/backtest.py` | Modify | Gains the CLI `main` (ported from root). |
| `vercel-demo/api/{dashboard,search,holdings,watchlist,momentum,backtest}.py` | Modify | Use `http_utils`. Remove the RSS monkeypatch. No tracebacks or wildcard CORS. Backtest parameter validation. |
| `vercel-demo/api/cron/momentum_screen.py` | Modify | Fail closed without `CRON_SECRET`. Constant-time token compare. |
| `vercel-demo/requirements.txt` | Modify | Exact pins. |
| `vercel-demo/.python-version` | Create | `3.12` (the Vercel default; makes it explicit). |
| `requirements.txt` (root) | Modify | `-r vercel-demo/requirements.txt` |
| `requirements-dev.txt` | Create | Runtime requirements + pytest. |
| `.github/workflows/ci.yml` | Create | pytest job + frontend build job. |
| `recommender.py`, `backtest.py`, `sources/` (root) | Delete | Superseded duplicates. |
| `tests/test_core.py`, `tests/test_prices.py`, `tests/test_news.py`, `tests/test_momentum_screen.py` | Modify | Target canonical modules. |
| `tests/test_http_utils.py`, `tests/test_api_handlers.py`, `tests/test_cron_auth.py`, `tests/test_holdings_logic.py`, `tests/test_nse.py` | Create | New coverage. |
| `README.md` | Modify | Accurate structure, commands, env vars, Phase 0 notes. |

---

### Task 1: Branch, baseline, and commit pending repository hygiene

**Files:**
- Modify (commit only): `.gitignore` (adds `.env`; user's existing uncommitted change)
- Add: `docs/AI_TRADER_PROJECT_DISCOVERY.md`, `AI_Trader_README.md`, this plan
- Leave untracked: `Momentum_Based_Short_Term_Stock_Strategy.md` (user's file; not part of this phase)

**Interfaces:** none.

- [ ] **Step 1: Create the branch**

```bash
git checkout -b phase0-stabilise
```

- [ ] **Step 2: Record the baseline**

Run: `python -m pytest -q`
Expected: `34 passed`

Run: `cd vercel-demo && npm run build`
Expected: `✓ built in …`

- [ ] **Step 3: Confirm `.env` is ignored and was never committed**

Run: `git check-ignore .env && git log --all --oneline -- .env`
Expected: prints `.env` and no commits.

- [ ] **Step 4: Commit**

```bash
git add .gitignore docs/AI_TRADER_PROJECT_DISCOVERY.md AI_Trader_README.md docs/superpowers/plans/2026-10-13-ai-trader-phase0-stabilise-plan.md
git commit -m "Add AI Trader brief, discovery report and Phase 0 plan; ignore .env"
```

---

### Task 2: Consolidate onto `vercel-demo/` as the single Python source

**Files:**
- Create: `tests/conftest.py`
- Modify: `vercel-demo/recommender.py`, `vercel-demo/backtest.py`, `vercel-demo/api/dashboard.py:16-19`, `vercel-demo/api/holdings.py:22-23`, `vercel-demo/api/search.py:16-17`, `vercel-demo/api/watchlist.py:19-20`
- Modify: `tests/test_core.py`, `tests/test_prices.py`, `tests/test_news.py`, `tests/test_momentum_screen.py`
- Delete: `recommender.py`, `backtest.py`, `sources/__init__.py`, `sources/news.py`, `sources/prices.py`

**Interfaces:**
- Produces:
  - `recommender.RSS_FEEDS: list[str]` (canonical; no more import-time overrides);
  - `recommender.write_dashboard(rows: list[dict], path: str = "dashboard.html") -> None`;
  - `backtest.main() -> None`.
- CLI commands become `python vercel-demo/recommender.py` and `python vercel-demo/backtest.py SYMBOL SHORT LONG`.

Behaviour changes (intentional, documented in README in Task 8):
- the CLI now ranks the 40-asset universe instead of 8;
- the CLI uses the working Yahoo RSS feed instead of the dead ones;
- price fetching drops NaN-close rows instead of aborting, which matches what production already does.

- [ ] **Step 1: Create `tests/conftest.py`**

```python
import os
import sys

# Tests target the canonical, deployed code under vercel-demo/.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "vercel-demo")))
```

- [ ] **Step 2: Remove the per-file `sys.path` hacks from the existing tests**

In `tests/test_core.py`, `tests/test_news.py`, and `tests/test_prices.py`, delete this line (and the now-unused `os`/`sys` imports if nothing else uses them):

```python
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
```

In `tests/test_momentum_screen.py`, delete:

```python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vercel-demo"))
```

Note: `test_core.py` still needs `import sys` for `monkeypatch.setattr(sys, "argv", ...)`.

- [ ] **Step 3: Update `tests/test_prices.py` fakes for the canonical OHLCV fetcher, and write the new NaN tests**

The canonical `fetch_ohlcv_history` reads Open/High/Low/Volume too. It degrades a missing column to NaN only on `KeyError`, `ValueError`, or `TypeError`, so the fake must raise `KeyError` for non-Close columns instead of failing an `assert`. Replace `_FakeFrame.__getitem__`:

```python
    def __getitem__(self, key):
        if key != "Close":
            raise KeyError(key)
        return self._close
```

Replace `test_fetch_price_history_raises_on_nan_close` with:

```python
def test_fetch_price_history_drops_nan_closes(monkeypatch):
    monkeypatch.setattr(prices.yf, "download", lambda *a, **k: _FakeFrame([100.0, float("nan"), 99.0]))

    assert prices.fetch_price_history("TEST") == [100.0, 99.0]


def test_fetch_price_history_raises_when_every_close_is_nan(monkeypatch):
    monkeypatch.setattr(prices.yf, "download", lambda *a, **k: _FakeFrame([float("nan"), float("nan")]))

    with pytest.raises(RuntimeError):
        prices.fetch_price_history("TEST")
```

- [ ] **Step 4: Add failing tests for the ported CLI pieces to `tests/test_core.py`**

```python
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
```

- [ ] **Step 5: Run the tests to verify they fail**

Run: `python -m pytest -q`
Expected: failures in `test_rss_feeds_are_canonical_not_overridden`, `test_write_dashboard_writes_escaped_html`, and `test_backtest_main_runs_without_syntax_error`. The last one fails because canonical `backtest.py` has no `main`. Note: the root `recommender.py` still exists but is shadowed by `vercel-demo/` on `sys.path`.

- [ ] **Step 6: Make `RSS_FEEDS` canonical in `vercel-demo/recommender.py`**

Replace the `RSS_FEEDS = [...]` block (lines 53-57) with:

```python
# The previous feedburner/moneycontrol URLs returned zero entries and were
# overridden at import time in every API module; this is now the single
# source of truth.
RSS_FEEDS = ["https://finance.yahoo.com/news/rssindex"]
```

Then delete the override comment and assignment from each API module:
- `vercel-demo/api/dashboard.py` lines 16-19;
- `vercel-demo/api/holdings.py` lines 22-23;
- `vercel-demo/api/search.py` lines 16-17;
- `vercel-demo/api/watchlist.py` lines 19-20.

These are the lines that start with `# Demo-only override` and `recommender.RSS_FEEDS = ...`.

- [ ] **Step 7: Port `write_dashboard` into `vercel-demo/recommender.py`**

Add `import html` to the imports. Insert this function above `main`. It is the root version, with `html.escape` added because symbols can come from user search in future:

```python
def write_dashboard(rows: List[Dict[str, object]], path: str = "dashboard.html") -> None:
    items = []
    for row in rows:
        items.append(
            f"<li><strong>{html.escape(str(row['symbol']))}</strong> — {html.escape(str(row['type']))} — "
            f"score {row['score']:.3f} — suggested Rs {int(row['suggested']):,} — {html.escape(str(row['action']))}</li>"
        )

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>QuantDesk Research Dashboard</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem; background: #07111f; color: #e7eefc; }}
    .card {{ background: #10233c; border: 1px solid #2f4b72; border-radius: 12px; padding: 1.5rem; max-width: 840px; }}
    ul {{ line-height: 1.7; }}
    .meta {{ color: #89a6c9; margin-bottom: 1rem; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>QuantDesk Research Dashboard</h1>
    <p class="meta">Capital: Rs {CAPITAL:,.0f} • Style: {STYLE} • Feeds: {len(RSS_FEEDS)}</p>
    <ul>
      {''.join(items)}
    </ul>
  </div>
</body>
</html>
"""
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(page)
```

Append to the end of `main()`:

```python
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard.html")
    write_dashboard(rows, output_path)
    print(f"\nDashboard written to {output_path}")
```

(`os` is already imported in this file. `dashboard.html` is already gitignored in any directory.)

- [ ] **Step 8: Port the CLI `main` into `vercel-demo/backtest.py`**

Add `import sys` to the imports and append:

```python
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

- [ ] **Step 9: Delete the root duplicates**

```bash
git rm recommender.py backtest.py sources/__init__.py sources/news.py sources/prices.py
```

- [ ] **Step 10: Run all tests and the build**

Run: `python -m pytest -q`
Expected: all pass (34 baseline − 1 replaced NaN test + 2 new price tests + 4 new core tests = **39 passed**).

Run: `cd vercel-demo && npm run build`
Expected: success.

Run: `python -c "import ast,glob; [ast.parse(open(f,encoding='utf-8').read()) for f in glob.glob('vercel-demo/api/**/*.py', recursive=True)]"`
Expected: no output (all handlers still parse after the override removal).

- [ ] **Step 11: Commit**

```bash
git add -A tests vercel-demo/recommender.py vercel-demo/backtest.py vercel-demo/api
git commit -m "Consolidate on vercel-demo as the single Python source; port CLI dashboard and backtest main; make RSS_FEEDS canonical"
```

---

### Task 3: Shared HTTP utilities (`vercel-demo/http_utils.py`)

**Files:**
- Create: `vercel-demo/http_utils.py`
- Test: `tests/test_http_utils.py`

**Interfaces:**
- Produces (every later task relies on these exact names):
  - `class HttpError(Exception)`, with attribute `status: int` and a message that is safe to show clients.
  - `MAX_BODY_BYTES: int = 65536`.
  - `device_id_from_headers(headers) -> str`. Raises `HttpError(400, ...)`.
  - `read_json_object(handler) -> dict`. Reads `handler.headers` and `handler.rfile`. Raises `HttpError(400|413, ...)`.
  - `allowed_origin(request_origin: str | None) -> str | None`. Reads env `ALLOWED_ORIGINS` (comma-separated).
  - `internal_error(exc: BaseException) -> dict`. Logs the traceback to stderr and returns `{"error": "Internal server error"}`.
  - `send_json(handler, status: int, payload: dict | None) -> None`. A 204 sends no body.
  - `send_text(handler, status: int, text: str) -> None`.
  - `bearer_token_matches(headers, secret: str) -> bool`.

- [ ] **Step 1: Write the failing tests**

`tests/test_http_utils.py`:

```python
import io
import json
from email.message import Message
from types import SimpleNamespace

import pytest

import http_utils


def _headers(**values):
    message = Message()
    for name, value in values.items():
        message[name.replace("_", "-")] = value
    return message


def _request(body: bytes, content_length=None):
    headers = _headers(**({"Content_Length": content_length} if content_length is not None else {}))
    return SimpleNamespace(headers=headers, rfile=io.BytesIO(body))


def test_device_id_valid():
    assert http_utils.device_id_from_headers(_headers(X_Device_Id="abc-123")) == "abc-123"


@pytest.mark.parametrize("value", ["", "has space", "x" * 65, "semi;colon"])
def test_device_id_rejected(value):
    with pytest.raises(http_utils.HttpError) as info:
        http_utils.device_id_from_headers(_headers(X_Device_Id=value))
    assert info.value.status == 400


def test_device_id_missing():
    with pytest.raises(http_utils.HttpError) as info:
        http_utils.device_id_from_headers(_headers())
    assert info.value.status == 400


def test_read_json_object_valid():
    body = json.dumps({"symbol": "INFY.NS"}).encode()
    assert http_utils.read_json_object(_request(body, str(len(body)))) == {"symbol": "INFY.NS"}


def test_read_json_object_empty_body_is_empty_object():
    assert http_utils.read_json_object(_request(b"", None)) == {}


@pytest.mark.parametrize("body", [b"[1, 2]", b"not json", b'"text"'])
def test_read_json_object_rejects_non_objects(body):
    with pytest.raises(http_utils.HttpError) as info:
        http_utils.read_json_object(_request(body, str(len(body))))
    assert info.value.status == 400


@pytest.mark.parametrize("length", ["abc", "-5"])
def test_read_json_object_rejects_bad_content_length(length):
    with pytest.raises(http_utils.HttpError) as info:
        http_utils.read_json_object(_request(b"{}", length))
    assert info.value.status == 400


def test_read_json_object_rejects_oversized_without_reading():
    request = _request(b"{}", str(http_utils.MAX_BODY_BYTES + 1))
    with pytest.raises(http_utils.HttpError) as info:
        http_utils.read_json_object(request)
    assert info.value.status == 413
    assert request.rfile.tell() == 0


def test_allowed_origin_none_when_unconfigured(monkeypatch):
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    assert http_utils.allowed_origin("https://evil.example") is None


def test_allowed_origin_echoes_only_listed_origins(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://a.example, https://b.example")
    assert http_utils.allowed_origin("https://b.example") == "https://b.example"
    assert http_utils.allowed_origin("https://evil.example") is None
    assert http_utils.allowed_origin(None) is None


def test_internal_error_hides_details_but_logs_them(capsys):
    try:
        raise RuntimeError("password=hunter2 in connection string")
    except RuntimeError as exc:
        payload = http_utils.internal_error(exc)

    assert payload == {"error": "Internal server error"}
    assert "hunter2" in capsys.readouterr().err


def test_bearer_token_matches():
    assert http_utils.bearer_token_matches(_headers(Authorization="Bearer s3cret"), "s3cret")
    assert not http_utils.bearer_token_matches(_headers(Authorization="Bearer wrong"), "s3cret")
    assert not http_utils.bearer_token_matches(_headers(), "s3cret")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_http_utils.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'http_utils'`.

- [ ] **Step 3: Implement `vercel-demo/http_utils.py`**

```python
from __future__ import annotations

import hmac
import json
import os
import re
import sys
import traceback
from typing import Optional

MAX_BODY_BYTES = 64 * 1024
_DEVICE_ID_RE = re.compile(r"^[A-Za-z0-9-]{1,64}$")


class HttpError(Exception):
    """A client-facing error: the message is safe to return in the response."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def device_id_from_headers(headers) -> str:
    device_id = (headers.get("X-Device-Id") or "").strip()
    if not device_id:
        raise HttpError(400, "Missing X-Device-Id header")
    if not _DEVICE_ID_RE.match(device_id):
        raise HttpError(400, "Invalid X-Device-Id header")
    return device_id


def read_json_object(handler) -> dict:
    raw_length = (handler.headers.get("Content-Length") or "0").strip()
    try:
        length = int(raw_length)
    except ValueError:
        raise HttpError(400, "Invalid Content-Length header") from None
    if length < 0:
        raise HttpError(400, "Invalid Content-Length header")
    if length > MAX_BODY_BYTES:
        # Refuse before reading so an oversized body never lands in memory.
        raise HttpError(413, f"Request body exceeds {MAX_BODY_BYTES} bytes")

    raw = handler.rfile.read(length) if length else b""
    try:
        body = json.loads(raw or b"{}")
    except ValueError:
        raise HttpError(400, "Request body must be valid JSON") from None
    if not isinstance(body, dict):
        raise HttpError(400, "Request body must be a JSON object")
    return body


def allowed_origin(request_origin: Optional[str]) -> Optional[str]:
    """The SPA is served from the same origin as the API, so no CORS header
    is needed by default. Cross-origin callers must be listed explicitly in
    ALLOWED_ORIGINS (comma-separated, exact match)."""
    configured = {o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()}
    if request_origin and request_origin in configured:
        return request_origin
    return None


def internal_error(exc: BaseException) -> dict:
    # Full detail goes to the server log (Vercel function logs), never to the client.
    traceback.print_exception(exc, file=sys.stderr)
    return {"error": "Internal server error"}


def _send_cors_headers(handler) -> None:
    origin = allowed_origin(handler.headers.get("Origin"))
    if origin:
        handler.send_header("Access-Control-Allow-Origin", origin)
        handler.send_header("Access-Control-Allow-Headers", "X-Device-Id, Content-Type")
        handler.send_header("Vary", "Origin")


def send_json(handler, status: int, payload: Optional[dict]) -> None:
    body = b"" if status == 204 or payload is None else json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    if body:
        handler.send_header("Content-Type", "application/json; charset=utf-8")
    _send_cors_headers(handler)
    handler.end_headers()
    if body:
        handler.wfile.write(body)


def send_text(handler, status: int, text: str) -> None:
    handler.send_response(status)
    handler.send_header("Content-Type", "text/plain; charset=utf-8")
    _send_cors_headers(handler)
    handler.end_headers()
    handler.wfile.write(text.encode("utf-8"))


def bearer_token_matches(headers, secret: str) -> bool:
    supplied = (headers.get("Authorization") or "").encode("utf-8")
    expected = f"Bearer {secret}".encode("utf-8")
    return hmac.compare_digest(supplied, expected)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_http_utils.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add vercel-demo/http_utils.py tests/test_http_utils.py
git commit -m "Add http_utils: body limits, device-id parsing, opt-in CORS, safe internal errors"
```

---

### Task 4: Route every API handler through `http_utils`

**Files:**
- Create: `tests/api_harness.py`, `tests/test_api_handlers.py`
- Modify: `vercel-demo/api/dashboard.py`, `vercel-demo/api/search.py`, `vercel-demo/api/holdings.py`, `vercel-demo/api/watchlist.py`, `vercel-demo/api/momentum.py`, `vercel-demo/api/backtest.py`

**Interfaces:**
- Consumes: everything listed under Task 3 "Produces".
- Produces:
  - `tests/api_harness.py`: `load_api_module(relative_path: str, module_name: str)`, `call(handler_cls, method, path, headers=None, body=b"") -> Response` (with `.status`, `.headers` (lower-case keys), `.body`, `.json()`, `.text`), and `FakeConnection(on_execute=None)`. Used again in Tasks 5 and 6.
  - `api/backtest.py`: `parse_backtest_query(path: str) -> tuple[str, int, int]` and `MAX_WINDOW = 250`.

- [ ] **Step 1: Write the harness, `tests/api_harness.py`**

```python
"""Drive a vercel-demo/api handler class in-process: no socket, DB or network."""
from __future__ import annotations

import importlib.util
import io
import json
import os
from email.message import Message

API_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "vercel-demo", "api"))


def load_api_module(relative_path: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, os.path.join(API_DIR, relative_path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Response:
    def __init__(self, raw: bytes):
        head, _, self.body = raw.partition(b"\r\n\r\n")
        lines = head.decode("latin-1").split("\r\n")
        self.status = int(lines[0].split()[1])
        self.headers = {}
        for line in lines[1:]:
            name, _, value = line.partition(":")
            self.headers[name.strip().lower()] = value.strip()

    def json(self):
        return json.loads(self.body)

    @property
    def text(self) -> str:
        return self.body.decode("utf-8")


def call(handler_cls, method: str, path: str, headers=None, body: bytes = b"") -> Response:
    handler = handler_cls.__new__(handler_cls)  # skip socket setup in __init__
    message = Message()
    for name, value in (headers or {}).items():
        message[name] = value
    if body and "Content-Length" not in message:
        message["Content-Length"] = str(len(body))
    handler.headers = message
    handler.path = path
    handler.command = method
    handler.request_version = "HTTP/1.1"
    handler.requestline = f"{method} {path} HTTP/1.1"
    handler.client_address = ("127.0.0.1", 0)
    handler.rfile = io.BytesIO(body)
    handler.wfile = io.BytesIO()
    handler.log_message = lambda *args, **kwargs: None
    getattr(handler, f"do_{method}")()
    return Response(handler.wfile.getvalue())


class _FakeCursor:
    def __init__(self, conn):
        self._conn = conn
        self._rows = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self._conn.executed.append((sql, params))
        self._rows = self._conn.on_execute(sql, params) if self._conn.on_execute else []

    def executemany(self, sql, seq):
        self._conn.executed.append((sql, list(seq)))

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


class FakeConnection:
    """on_execute(sql, params) returns the rows for that statement, or raises."""

    def __init__(self, on_execute=None):
        self.on_execute = on_execute
        self.executed = []
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return _FakeCursor(self)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True
```

- [ ] **Step 2: Write the failing handler tests, `tests/test_api_handlers.py`**

```python
import datetime
import json

import pytest

from api_harness import FakeConnection, call, load_api_module

dashboard = load_api_module("dashboard.py", "api_dashboard")
search = load_api_module("search.py", "api_search")
holdings = load_api_module("holdings.py", "api_holdings")
watchlist = load_api_module("watchlist.py", "api_watchlist")
momentum = load_api_module("momentum.py", "api_momentum")
backtest_api = load_api_module("backtest.py", "api_backtest")

DEVICE = {"X-Device-Id": "device-1"}


def _rising(n=60):
    return [100.0 + i * 0.5 for i in range(n)]


@pytest.fixture(autouse=True)
def _no_cors_config(monkeypatch):
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)


def _boom(*args, **kwargs):
    raise Exception("connection to secret-host.internal failed")


def _assert_generic_500(response):
    assert response.status == 500
    assert response.json() == {"error": "Internal server error"}
    assert b"Traceback" not in response.body
    assert b"secret-host" not in response.body


# --- error hygiene -----------------------------------------------------------

def test_dashboard_unexpected_error_is_generic_and_logged(monkeypatch, capsys):
    monkeypatch.setattr(dashboard, "build_dashboard", _boom)
    _assert_generic_500(call(dashboard.handler, "GET", "/api/dashboard"))
    assert "secret-host" in capsys.readouterr().err


def test_holdings_get_db_failure_is_generic(monkeypatch):
    monkeypatch.setattr(holdings.db, "get_connection", _boom)
    _assert_generic_500(call(holdings.handler, "GET", "/api/holdings", DEVICE))


def test_watchlist_get_db_failure_is_generic(monkeypatch):
    monkeypatch.setattr(watchlist.db, "get_connection", _boom)
    _assert_generic_500(call(watchlist.handler, "GET", "/api/watchlist", DEVICE))


def test_momentum_db_failure_is_generic(monkeypatch):
    monkeypatch.setattr(momentum.db, "get_connection", _boom)
    _assert_generic_500(call(momentum.handler, "GET", "/api/momentum?tab=screener"))


def test_search_unexpected_error_is_generic(monkeypatch):
    monkeypatch.setattr(search, "search_symbol", _boom)
    _assert_generic_500(call(search.handler, "GET", "/api/search?symbol=INFY.NS"))


# --- CORS --------------------------------------------------------------------

def test_no_cors_header_by_default(monkeypatch):
    monkeypatch.setattr(search, "search_symbol", lambda s: {"symbol": s})
    response = call(search.handler, "GET", "/api/search?symbol=X", {"Origin": "https://evil.example"})
    assert response.status == 200
    assert "access-control-allow-origin" not in response.headers


def test_listed_origin_is_echoed(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://app.example")
    monkeypatch.setattr(search, "search_symbol", lambda s: {"symbol": s})
    response = call(search.handler, "GET", "/api/search?symbol=X", {"Origin": "https://app.example"})
    assert response.headers["access-control-allow-origin"] == "https://app.example"


# --- input validation ----------------------------------------------------------

def test_search_requires_symbol():
    assert call(search.handler, "GET", "/api/search").status == 400


def test_momentum_rejects_unknown_tab():
    assert call(momentum.handler, "GET", "/api/momentum?tab=bogus").status == 400


def test_holdings_requires_device_id():
    assert call(holdings.handler, "GET", "/api/holdings").status == 400


def test_holdings_post_oversized_body_is_413():
    huge = b"{" + b" " * (70 * 1024) + b"}"
    assert call(holdings.handler, "POST", "/api/holdings", DEVICE, huge).status == 413


def test_holdings_post_invalid_json_is_400():
    assert call(holdings.handler, "POST", "/api/holdings", DEVICE, b"not json").status == 400


def test_holdings_post_bad_price_is_400():
    body = json.dumps({"symbol": "INFY.NS", "buy_price": "abc", "quantity": 1, "buy_date": "2026-01-02"}).encode()
    response = call(holdings.handler, "POST", "/api/holdings", DEVICE, body)
    assert response.status == 400
    assert "buy_price" in response.json()["error"]


def test_holdings_post_success(monkeypatch):
    monkeypatch.setattr(holdings.prices_source, "fetch_price_history", lambda s, period="6mo": _rising())
    row = {"id": 7, "symbol": "INFY.NS", "buy_price": 1500, "quantity": 2, "buy_date": datetime.date(2026, 1, 2)}
    conn = FakeConnection(on_execute=lambda sql, params: [row])
    monkeypatch.setattr(holdings.db, "get_connection", lambda: conn)

    body = json.dumps({"symbol": "infy.ns", "buy_price": 1500, "quantity": 2, "buy_date": "2026-01-02"}).encode()
    response = call(holdings.handler, "POST", "/api/holdings", DEVICE, body)

    assert response.status == 201
    assert response.json()["id"] == 7
    assert conn.committed and conn.closed


def test_holdings_delete_returns_204_without_body(monkeypatch):
    conn = FakeConnection(on_execute=lambda sql, params: [{"id": 5}])
    monkeypatch.setattr(holdings.db, "get_connection", lambda: conn)
    response = call(holdings.handler, "DELETE", "/api/holdings?id=5", DEVICE)
    assert response.status == 204
    assert response.body == b""


def test_holdings_delete_missing_is_404(monkeypatch):
    monkeypatch.setattr(holdings.db, "get_connection", lambda: FakeConnection(on_execute=lambda s, p: []))
    assert call(holdings.handler, "DELETE", "/api/holdings?id=5", DEVICE).status == 404


# --- backtest ------------------------------------------------------------------

@pytest.mark.parametrize("query", ["short=abc", "short=50&long=20", "short=0&long=5", "long=999"])
def test_backtest_rejects_bad_windows(query):
    response = call(backtest_api.handler, "GET", f"/api/backtest?{query}")
    assert response.status == 400
    assert "Traceback" not in response.text


def test_backtest_rejects_window_longer_than_history(monkeypatch):
    monkeypatch.setattr(backtest_api.prices_source, "fetch_price_history", lambda s, period="1y": _rising(30))
    response = call(backtest_api.handler, "GET", "/api/backtest?symbol=X&short=5&long=50")
    assert response.status == 400


def test_backtest_success(monkeypatch):
    monkeypatch.setattr(backtest_api.prices_source, "fetch_price_history", lambda s, period="1y": _rising(120))
    response = call(backtest_api.handler, "GET", "/api/backtest?symbol=TEST&short=5&long=20")
    assert response.status == 200
    assert "Backtest for TEST" in response.text
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python -m pytest tests/test_api_handlers.py -q`
Expected failures:
- the generic-500 tests, because the current body contains `traceback`;
- `test_no_cors_header_by_default`, because a `*` header is present;
- `test_holdings_post_oversized_body_is_413` (currently 201/400/502);
- the backtest validation tests (currently 500).

- [ ] **Step 4: Update `vercel-demo/api/dashboard.py`**

Replace the imports and the `handler` class. Drop `json` and `traceback`, and add `import http_utils` after the `sys.path.insert` line:

```python
import http_utils
import recommender
```

```python
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            payload, status = build_dashboard(), 200
        except Exception as exc:
            payload, status = http_utils.internal_error(exc), 500
        http_utils.send_json(self, status, payload)
```

- [ ] **Step 5: Update `vercel-demo/api/search.py`**

Same import changes. Replace `handler`:

```python
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        raw_symbol = query.get("symbol", [""])[0]
        try:
            if not raw_symbol.strip():
                payload, status = {"error": "Query parameter 'symbol' is required"}, 400
            else:
                payload, status = search_symbol(raw_symbol), 200
        except (RuntimeError, ValueError) as exc:
            payload, status = {"error": str(exc)}, 502
        except Exception as exc:
            payload, status = http_utils.internal_error(exc), 500
        http_utils.send_json(self, status, payload)
```

- [ ] **Step 6: Update `vercel-demo/api/momentum.py`**

Same import changes. Replace `handler`:

```python
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            query = parse_qs(urlparse(self.path).query)
            tab = query.get("tab", ["screener"])[0]
            payload, status = get_momentum(tab), 200
        except ValueError as exc:
            payload, status = {"error": str(exc)}, 400
        except LookupError as exc:
            payload, status = {"error": str(exc)}, 503
        except Exception as exc:
            payload, status = http_utils.internal_error(exc), 500
        http_utils.send_json(self, status, payload)
```

- [ ] **Step 7: Update `vercel-demo/api/holdings.py`**

Remove `import json`, `import re`, `import traceback`, `_DEVICE_ID_RE`, and `_device_id_from_headers`. Add `import http_utils`. Replace the whole `handler` class:

```python
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            device_id = http_utils.device_id_from_headers(self.headers)
            payload, status = list_holdings(device_id), 200
        except http_utils.HttpError as exc:
            payload, status = {"error": str(exc)}, exc.status
        except ValueError as exc:
            payload, status = {"error": str(exc)}, 400
        except Exception as exc:
            payload, status = http_utils.internal_error(exc), 500
        http_utils.send_json(self, status, payload)

    def do_POST(self):
        try:
            device_id = http_utils.device_id_from_headers(self.headers)
            body = http_utils.read_json_object(self)
            payload, status = add_holding(device_id, body), 201
        except http_utils.HttpError as exc:
            payload, status = {"error": str(exc)}, exc.status
        except ValueError as exc:
            payload, status = {"error": str(exc)}, 400
        except RuntimeError as exc:
            payload, status = {"error": str(exc)}, 502
        except Exception as exc:
            payload, status = http_utils.internal_error(exc), 500
        http_utils.send_json(self, status, payload)

    def do_DELETE(self):
        try:
            device_id = http_utils.device_id_from_headers(self.headers)
            query = parse_qs(urlparse(self.path).query)
            raw_id = query.get("id", [""])[0]
            if not raw_id.isdigit():
                raise ValueError("Query parameter 'id' must be a positive integer")
            delete_holding(device_id, int(raw_id))
            payload, status = None, 204
        except http_utils.HttpError as exc:
            payload, status = {"error": str(exc)}, exc.status
        except ValueError as exc:
            payload, status = {"error": str(exc)}, 400
        except LookupError as exc:
            payload, status = {"error": str(exc)}, 404
        except Exception as exc:
            payload, status = http_utils.internal_error(exc), 500
        http_utils.send_json(self, status, payload)
```

- [ ] **Step 8: Update `vercel-demo/api/watchlist.py`**

Remove `import json`, `import re`, `import traceback`, `_DEVICE_ID_RE`, and `_device_id_from_headers`. Add `import http_utils`. Replace the `handler` class with the holdings version from Step 7, with these differences:
- `list_holdings` becomes `list_watchlist`;
- `add_holding` becomes `add_to_watchlist`;
- `delete_holding` becomes `delete_from_watchlist`;
- `do_POST` gains `except LookupError as exc: payload, status = {"error": str(exc)}, 409`, placed **after** the `ValueError` clause and **before** `RuntimeError`.

The full `do_POST` for watchlist:

```python
    def do_POST(self):
        try:
            device_id = http_utils.device_id_from_headers(self.headers)
            body = http_utils.read_json_object(self)
            payload, status = add_to_watchlist(device_id, body), 201
        except http_utils.HttpError as exc:
            payload, status = {"error": str(exc)}, exc.status
        except ValueError as exc:
            payload, status = {"error": str(exc)}, 400
        except LookupError as exc:
            payload, status = {"error": str(exc)}, 409
        except RuntimeError as exc:
            payload, status = {"error": str(exc)}, 502
        except Exception as exc:
            payload, status = http_utils.internal_error(exc), 500
        http_utils.send_json(self, status, payload)
```

- [ ] **Step 9: Rewrite `vercel-demo/api/backtest.py`**

```python
from __future__ import annotations

import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import backtest
import http_utils
from sources import prices as prices_source

MAX_WINDOW = 250  # ~1 year of trading days; the fetch below is period="1y"


def parse_backtest_query(path: str) -> tuple:
    query = parse_qs(urlparse(path).query)
    symbol = query.get("symbol", ["RELIANCE.NS"])[0].strip()
    if not symbol:
        raise ValueError("symbol must not be empty")
    try:
        short_window = int(query.get("short", ["20"])[0])
        long_window = int(query.get("long", ["50"])[0])
    except ValueError:
        raise ValueError("short and long must be whole numbers") from None
    if not 1 <= short_window < long_window <= MAX_WINDOW:
        raise ValueError(f"Windows must satisfy 1 <= short < long <= {MAX_WINDOW}")
    return symbol, short_window, long_window


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            symbol, short_window, long_window = parse_backtest_query(self.path)
            prices = prices_source.fetch_price_history(symbol, period="1y")
            if len(prices) <= long_window:
                raise ValueError(
                    f"Only {len(prices)} price points for {symbol!r}; need more than the long window ({long_window})"
                )
            strategy_value, buy_hold_value, periods = backtest.run_backtest(prices, short_window, long_window)
            text = (
                f"Backtest for {symbol} | periods={periods} | short={short_window} | long={long_window}\n"
                f"Strategy final value: Rs {strategy_value:,.2f}\n"
                f"Buy-and-hold value:  Rs {buy_hold_value:,.2f}\n"
            )
            text += (
                "Outcome: strategy outperformed buy-and-hold.\n"
                if strategy_value > buy_hold_value
                else "Outcome: strategy underperformed buy-and-hold.\n"
            )
            status = 200
        except ValueError as exc:
            text, status = f"Error: {exc}\n", 400
        except RuntimeError as exc:
            text, status = f"Error fetching price data: {exc}\n", 502
        except Exception as exc:
            text, status = f"Error: {http_utils.internal_error(exc)['error']}\n", 500
        http_utils.send_text(self, status, text)
```

- [ ] **Step 10: Run the tests to verify they pass**

Run: `python -m pytest -q`
Expected: all pass.

Run: `grep -rn "traceback\|Allow-Origin\", \"\*\"" vercel-demo/api`
Expected: no matches.

- [ ] **Step 11: Commit**

```bash
git add tests/api_harness.py tests/test_api_handlers.py vercel-demo/api
git commit -m "Route API handlers through http_utils: no traceback leaks, opt-in CORS, body limits, backtest validation"
```

---

### Task 5: Require cron authentication (fail closed)

**Files:**
- Modify: `vercel-demo/api/cron/momentum_screen.py:224-246`
- Test: `tests/test_cron_auth.py`

**Interfaces:**
- Consumes: `http_utils.bearer_token_matches`, `http_utils.send_json`, `http_utils.internal_error`, and `api_harness.call` / `load_api_module`.
- Produces: the cron handler behaviour. 503 if `CRON_SECRET` is unset or empty, 401 if the token is wrong, otherwise it runs `run_screen()`.

> **Deployment impact:** after this change the scheduled screen **will not run** until `CRON_SECRET` is set in the Vercel project's environment variables. Vercel Cron automatically sends `Authorization: Bearer $CRON_SECRET` when that variable exists. This must appear in the final report and the README.

- [ ] **Step 1: Write the failing tests, `tests/test_cron_auth.py`**

```python
import pytest

from api_harness import call, load_api_module

cron = load_api_module("cron/momentum_screen.py", "api_cron_momentum_screen")


@pytest.fixture
def ran(monkeypatch):
    calls = []
    monkeypatch.setattr(cron, "run_screen", lambda: calls.append(1) or {"symbols_scored": 1})
    return calls


def test_refuses_when_secret_not_configured(monkeypatch, ran):
    monkeypatch.delenv("CRON_SECRET", raising=False)
    response = call(cron.handler, "GET", "/api/cron/momentum_screen")
    assert response.status == 503
    assert ran == []


def test_rejects_missing_token(monkeypatch, ran):
    monkeypatch.setenv("CRON_SECRET", "s3cret")
    assert call(cron.handler, "GET", "/api/cron/momentum_screen").status == 401
    assert ran == []


def test_rejects_wrong_token(monkeypatch, ran):
    monkeypatch.setenv("CRON_SECRET", "s3cret")
    response = call(cron.handler, "GET", "/api/cron/momentum_screen", {"Authorization": "Bearer nope"})
    assert response.status == 401
    assert ran == []


def test_runs_with_correct_token(monkeypatch, ran):
    monkeypatch.setenv("CRON_SECRET", "s3cret")
    response = call(cron.handler, "GET", "/api/cron/momentum_screen", {"Authorization": "Bearer s3cret"})
    assert response.status == 200
    assert response.json() == {"symbols_scored": 1}
    assert ran == [1]


def test_screen_failure_reports_message_without_traceback(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "s3cret")

    def _fail():
        raise RuntimeError("Cannot screen without the Nifty 200 universe: blocked")

    monkeypatch.setattr(cron, "run_screen", _fail)
    response = call(cron.handler, "GET", "/api/cron/momentum_screen", {"Authorization": "Bearer s3cret"})
    assert response.status == 500
    assert "Nifty 200" in response.json()["error"]
    assert b"Traceback" not in response.body
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_cron_auth.py -q`
Expected: `test_refuses_when_secret_not_configured` FAILS, because it currently runs the screen and returns 200.

- [ ] **Step 3: Replace the handler in `vercel-demo/api/cron/momentum_screen.py`**

Add `import http_utils` next to `import db`. Replace the whole `handler` class:

```python
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        cron_secret = os.environ.get("CRON_SECRET", "")
        if not cron_secret:
            # Fail closed: an unauthenticated trigger could fan out ~200
            # symbols of NSE/Yahoo traffic on demand.
            http_utils.send_json(self, 503, {"error": "CRON_SECRET is not configured; refusing to run"})
            return
        if not http_utils.bearer_token_matches(self.headers, cron_secret):
            http_utils.send_json(self, 401, {"error": "Unauthorized"})
            return

        try:
            payload, status = run_screen(), 200
        except RuntimeError as exc:
            # Messages raised by run_screen itself; the caller is authenticated.
            http_utils.internal_error(exc)
            payload, status = {"error": str(exc)}, 500
        except Exception as exc:
            payload, status = http_utils.internal_error(exc), 500
        http_utils.send_json(self, status, payload)
```

Delete the old `_send_json` method.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add vercel-demo/api/cron/momentum_screen.py tests/test_cron_auth.py
git commit -m "Cron: refuse to run without CRON_SECRET, constant-time token check"
```

---

### Task 6: Watchlist duplicate insert race returns 409, not 500

**Files:**
- Modify: `vercel-demo/api/watchlist.py` (`add_to_watchlist`, lines ~92-108)
- Test: append to `tests/test_api_handlers.py`

**Interfaces:**
- Consumes: `FakeConnection`, `call`, `watchlist` module (Task 4).
- Produces: `add_to_watchlist` relies on the `UNIQUE (device_id, symbol)` constraint and maps `psycopg2.errors.UniqueViolation` to `LookupError("already in your watchlist")`.

- [ ] **Step 1: Write the failing test** (append to `tests/test_api_handlers.py`)

```python
import psycopg2.errors


def test_watchlist_duplicate_insert_is_409(monkeypatch):
    monkeypatch.setattr(watchlist.prices_source, "fetch_price_history", lambda s, period="6mo": _rising())

    def on_execute(sql, params):
        if sql.lstrip().upper().startswith("INSERT"):
            raise psycopg2.errors.UniqueViolation("duplicate key value violates unique constraint")
        return []

    conn = FakeConnection(on_execute=on_execute)
    monkeypatch.setattr(watchlist.db, "get_connection", lambda: conn)

    response = call(watchlist.handler, "POST", "/api/watchlist", DEVICE, b'{"symbol": "INFY.NS"}')

    assert response.status == 409
    assert response.json() == {"error": "already in your watchlist"}
    assert conn.rolled_back and conn.closed
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_api_handlers.py::test_watchlist_duplicate_insert_is_409 -q`
Expected: FAIL with status 500.

- [ ] **Step 3: Replace the DB block in `add_to_watchlist`**

Add `import psycopg2.errors` to the imports. Replace the `conn = db.get_connection()` … `conn.close()` block with:

```python
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    "INSERT INTO watchlist (device_id, symbol) VALUES (%s, %s) RETURNING id, symbol",
                    (device_id, symbol),
                )
            except psycopg2.errors.UniqueViolation:
                # The UNIQUE (device_id, symbol) constraint is the source of
                # truth; a SELECT-then-INSERT pre-check would race.
                conn.rollback()
                raise LookupError("already in your watchlist") from None
            row = cur.fetchone()
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add vercel-demo/api/watchlist.py tests/test_api_handlers.py
git commit -m "Watchlist: rely on UNIQUE constraint; duplicate insert race returns 409"
```

---

### Task 7: Characterisation tests for untested deployed modules

These tests pin **existing** behaviour, so they are expected to pass on first run. If one fails, the code has a real bug. Stop and report it rather than "fixing" the test.

**Files:**
- Create: `tests/test_holdings_logic.py`, `tests/test_nse.py`

**Interfaces:**
- Consumes: `holdings_logic.compute_sell_signal`, `holdings_logic.compute_holding_period`, `sources.nse._fetch_csv_rows`, `sources.nse._first_column_symbols`, `sources.nse.fetch_bhavcopy`, `sources.nse.latest_trading_day`.

- [ ] **Step 1: Write `tests/test_holdings_logic.py`**

```python
import datetime

import pytest

from holdings_logic import compute_holding_period, compute_sell_signal


def _scores(short_term, swing):
    return {"short_term": {"score": short_term}, "swing": {"score": swing}}


@pytest.mark.parametrize(
    "short_term, swing, action",
    [
        (-0.1, -0.1, "Consider selling"),
        (-0.1, 0.2, "Short-term weakness"),
        (0.2, -0.1, "Long-term weakness"),
        (0.2, 0.2, "Hold"),
        (0.0, 0.0, "Hold"),
    ],
)
def test_sell_signal_branches(short_term, swing, action):
    assert compute_sell_signal(_scores(short_term, swing))["action"] == action


def test_holding_period_indian_equity_before_ltcg():
    buy = datetime.date.today() - datetime.timedelta(days=100)
    result = compute_holding_period(buy, "INFY.NS")
    assert result == {"days_held": 100, "ltcg_applicable": True, "ltcg_eligible": False, "days_to_ltcg": 265}


def test_holding_period_indian_equity_after_ltcg():
    buy = datetime.date.today() - datetime.timedelta(days=400)
    result = compute_holding_period(buy, "TCS.BO")
    assert result["ltcg_eligible"] is True
    assert result["days_to_ltcg"] == 0


def test_holding_period_non_indian_symbol_has_no_ltcg():
    buy = datetime.date.today() - datetime.timedelta(days=10)
    result = compute_holding_period(buy, "AAPL")
    assert result == {"days_held": 10, "ltcg_applicable": False, "ltcg_eligible": None, "days_to_ltcg": None}
```

- [ ] **Step 2: Write `tests/test_nse.py`**

```python
import datetime

import pytest
import requests

from sources import nse


class _Resp:
    def __init__(self, text="", content_type="text/csv", status=200):
        self.text = text
        self.headers = {"Content-Type": content_type}
        self._status = status

    def raise_for_status(self):
        if self._status >= 400:
            raise requests.HTTPError(f"{self._status}")


class _Session:
    def __init__(self, responses):
        self._responses = responses  # url-substring -> _Resp | Exception
        self.requested = []

    def get(self, url, timeout=None):
        self.requested.append(url)
        for key, value in self._responses.items():
            if key in url:
                if isinstance(value, Exception):
                    raise value
                return value
        return _Resp(status=404)


def test_fetch_csv_rows_rejects_html_challenge_pages():
    session = _Session({"x.csv": _Resp("<html>blocked</html>", content_type="text/html")})
    with pytest.raises(RuntimeError, match="anti-bot"):
        nse._fetch_csv_rows(session, "https://nse/x.csv")


def test_fetch_csv_rows_wraps_network_errors():
    session = _Session({"x.csv": requests.ConnectionError("down")})
    with pytest.raises(RuntimeError, match="Failed to fetch"):
        nse._fetch_csv_rows(session, "https://nse/x.csv")


def test_first_column_symbols_drops_junk():
    rows = [{"Sr": "INFY"}, {"Sr": "<div>"}, {"Sr": "m&m"}, {"Sr": ""}]
    assert nse._first_column_symbols(rows) == {"INFY", "M&M"}


def test_fetch_bhavcopy_parses_volume_and_delivery():
    csv_text = "SYMBOL,TTL_TRD_QNTY,DELIV_PER\nINFY,\"1,000\",55.5\nBAD,abc,1\n"
    session = _Session({"sec_bhavdata_full_02012026": _Resp(csv_text)})
    result = nse.fetch_bhavcopy(datetime.date(2026, 1, 2), session)
    assert result == {"INFY": {"volume": 1000.0, "delivery_pct": 55.5}}


def test_latest_trading_day_walks_back_to_last_published_file():
    csv_text = "SYMBOL,TTL_TRD_QNTY,DELIV_PER\nINFY,10,50\n"
    session = _Session({"sec_bhavdata_full_02012026": _Resp(csv_text)})
    day, bhavcopy = nse.latest_trading_day(session, today=datetime.date(2026, 1, 4))
    assert day == datetime.date(2026, 1, 2)
    assert "INFY" in bhavcopy
    assert len(session.requested) == 3  # 04, 03, then 02


def test_latest_trading_day_gives_up_after_ten_days():
    with pytest.raises(RuntimeError, match="10 days"):
        nse.latest_trading_day(_Session({}), today=datetime.date(2026, 1, 20))
```

- [ ] **Step 3: Run the tests**

Run: `python -m pytest tests/test_holdings_logic.py tests/test_nse.py -q`
Expected: all pass. A failure here means a real defect. Report it and do not adjust the assertion to match.

- [ ] **Step 4: Commit**

```bash
git add tests/test_holdings_logic.py tests/test_nse.py
git commit -m "Add characterisation tests for holdings_logic and the NSE adapter"
```

---

### Task 8: Pin dependencies and Python version, add CI, update README

**Files:**
- Modify: `vercel-demo/requirements.txt`, `requirements.txt`, `README.md`
- Create: `vercel-demo/.python-version`, `requirements-dev.txt`, `.github/workflows/ci.yml`

**Interfaces:** none (configuration and docs).

Pins are the versions installed locally on 2026-10-13, against which the suite passes. `.python-version` is honoured by Vercel, with available versions 3.12 (default), 3.13, and 3.14 (https://vercel.com/docs/functions/runtimes/python, updated 2026-08-12). Pinning 3.12 makes the current implicit default explicit, and CI tests on the same version. **Assumption:** the Vercel project's root directory is `vercel-demo/`, where `vercel.json` lives. Confirm in the Vercel dashboard.

- [ ] **Step 1: Pin `vercel-demo/requirements.txt`**

```text
# Exact pins for reproducible Vercel builds (verified locally 2026-10-13).
# Transitive dependencies (e.g. pandas via yfinance) are not pinned yet.
yfinance==1.5.2
feedparser==6.0.12
vaderSentiment==3.3.2
psycopg2-binary==2.9.12
requests==2.34.2
```

- [ ] **Step 2: Create `vercel-demo/.python-version`**

```text
3.12
```

- [ ] **Step 3: Point the root requirements at the canonical file, and add dev requirements**

`requirements.txt`:

```text
# The canonical runtime dependencies live with the deployed code.
-r vercel-demo/requirements.txt
```

`requirements-dev.txt`:

```text
-r requirements.txt
pytest==8.4.2
```

- [ ] **Step 4: Create `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
  pull_request:

jobs:
  python-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version-file: vercel-demo/.python-version
      - run: pip install -r requirements-dev.txt
      - run: python -m pytest -q

  frontend-build:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: vercel-demo
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: npm
          cache-dependency-path: vercel-demo/package-lock.json
      - run: npm ci
      - run: npm run build
```

- [ ] **Step 5: Verify locally that the pinned requirements resolve and the suite passes**

Run: `python -m pip install --dry-run -r requirements-dev.txt`
Expected: resolves with no conflicts ("Would install" lists nothing new, or only already-satisfied pins).

Run: `python -m pytest -q`
Expected: all pass.

Run: `cd vercel-demo && npm ci && npm run build`
Expected: success.

- [ ] **Step 6: Update `README.md`**

Make these edits:

1. **Repository structure.** Replace the existing tree with:

```
ai-trader/
├── AI_Trader_README.md     # product vision & phased requirements for AI Trader
├── docs/                   # discovery report, design specs, implementation plans
├── requirements*.txt       # root installs point at vercel-demo/requirements.txt
├── tests/                  # pytest suite (targets vercel-demo/ code)
└── vercel-demo/            # the canonical app: React/Vite UI + Python API on Vercel
    ├── api/                # serverless handlers (dashboard, search, holdings, watchlist, momentum, backtest, cron)
    ├── sources/            # data adapters: prices (yfinance), news (RSS+VADER), nse
    ├── recommender.py      # momentum+sentiment scoring; also a CLI
    ├── momentum_screen.py  # Nifty 200 momentum screener scoring
    ├── backtest.py         # SMA-crossover backtest; also a CLI
    ├── http_utils.py       # shared API response/error/CORS helpers
    └── schema.sql          # Postgres schema (apply manually)
```

2. **Quick start.** Replace the commands with:

```bash
pip install -r requirements-dev.txt
python -m pytest -q
python vercel-demo/recommender.py             # prints rankings + writes vercel-demo/dashboard.html
python vercel-demo/backtest.py RELIANCE.NS 20 50
cd vercel-demo && npm ci && npm run build      # frontend
```

3. **New section, "Configuration (environment variables)":**

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` / `POSTGRES_URL` | for holdings, watchlist, momentum | Postgres connection string. Keep it in `.env` or Vercel env vars, never in git. |
| `CRON_SECRET` | **yes, for the momentum cron** | The cron endpoint refuses to run (503) without it. Vercel Cron sends it automatically as a Bearer token once set. |
| `ALLOWED_ORIGINS` | no | Comma-separated origins allowed to call the API cross-origin. The same-origin UI needs nothing. |

4. **New section, "Phase 0 changes (2026-10)":** list the intentional behaviour changes:
   - root CLI moved to `vercel-demo/` and now ranks the 40-asset universe using the working Yahoo RSS feed;
   - NaN closes are dropped rather than aborting;
   - API 500s return a generic message and log details server-side;
   - no wildcard CORS;
   - cron requires `CRON_SECRET`;
   - the backtest endpoint validates parameters (400);
   - a duplicate watchlist add returns 409.

5. Under "Phase 2", add one line pointing to `AI_Trader_README.md` as the current roadmap.

- [ ] **Step 7: Commit**

```bash
git add vercel-demo/requirements.txt vercel-demo/.python-version requirements.txt requirements-dev.txt .github/workflows/ci.yml README.md
git commit -m "Pin dependencies and Python 3.12, add CI (pytest + frontend build), update README for Phase 0"
```

---

### Task 9: Phase 0 gate check and report

**Files:** none modified.

- [ ] **Step 1: Run the full gate**

Run: `python -m pytest -q`
Expected: all pass, with the count recorded.

Run: `cd vercel-demo && npm run build`
Expected: success.

Run: `git grep -n -i -E "traceback.format_exc|Allow-Origin\", \"\\*\"" -- vercel-demo`
Expected: no matches.

Run: `git grep -n -E "(api[_-]?key|secret|password)\s*=\s*['\"][^'\"]+" -- . ':!*.md' ':!tests/*'`
Expected: no hard-coded secrets.

- [ ] **Step 2: Write the final report to the user.** It must contain:
- exact files changed (`git diff --stat master...phase0-stabilise`);
- tests run and counts;
- the build result;
- intentional behaviour changes;
- **manual deployment step: set `CRON_SECRET` in Vercel before merging/deploying**;
- assumptions (Vercel root = `vercel-demo/`; CI not yet run on GitHub because pushing needs the user's approval);
- remaining risks: NSE ToS / yfinance personal-use, transitive deps unpinned, device-ID auth, delivery-% dead branch, promoter-holding proxy, no rate limiting.

- [ ] **Step 3: Stop.** Do not push, merge, deploy, or start Phase 1. Phase 1 needs the user's decisions from AI_Trader_README.md §12, including the Kite data subscription and the historical options data source.
