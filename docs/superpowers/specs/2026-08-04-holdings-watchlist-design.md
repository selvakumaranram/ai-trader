# QuantDesk Dashboard: Holdings & Personal Watchlist Design

**Date:** 2026-08-04
**Status:** Approved

## Problem

The dashboard (spec: `2026-08-04-quantdesk-dashboard-design.md`) only shows recommendations for a curated 40-asset watchlist and one-off searches — nothing persists. The user wants two new, persistent features: a **Holdings** list (stocks already owned, with sell/hold guidance and P&L) and a **personal Watchlist** (arbitrary symbols saved for ongoing buy guidance, beyond the curated 40). Both need to survive page reloads and browser restarts, which the dashboard currently cannot do at all — it has no backend storage.

**Naming note:** the app already uses "Watchlist" as an *action label* (`_score_asset`'s two possible actions are `"Research LONG"` and `"Watchlist"`). This spec's new "personal Watchlist" is a different concept — a saved list of symbols. To avoid confusion, UI copy always says "My Watchlist" or "personal watchlist," and code names the new component `PersonalWatchlist.jsx`, not `Watchlist.jsx`. The existing action label is untouched.

## Decisions

Confirmed with the user during brainstorming:

1. **Storage: a real database** (not localStorage-only) — Vercel Postgres (Neon-backed), since holdings/watchlist are structured, queryable rows, not a simple cache.
2. **Identity: anonymous device ID, no login.** On first visit, the browser generates a random ID (`crypto.randomUUID()`), stored in `localStorage`, sent as an `X-Device-Id` header on every holdings/watchlist request. No signup, no password, no cross-device sync — losing the browser's storage loses access to that device's rows (acceptable for a personal demo tool; a real login system is out of scope).
3. **Holdings record:** symbol, buy price, quantity, buy date (not just symbol) — enables P&L and holding-period context.
4. **Sell signal: both the existing scoring engine and tax-timing context**, not one or the other. The scoring half reuses `recommender.build_asset_payload` (already extracted during the dashboard's final review) exactly as `/api/search` does today — no new momentum/sentiment logic. The tax-timing half surfaces India's LTCG/STCG holding-period math (equity held ≥365 days qualifies for long-term capital gains treatment) as context alongside the signal, not a replacement for it.
5. **Holdings and Watchlist are separate lists**, not one unified table with optional fields. A symbol can appear in both (you own some, and are watching for a chance to add more).

## Architecture

### Database

Vercel Postgres, connected via the **pooled** connection string (Vercel/Neon provides both a direct and a PgBouncer-pooled string for serverless use — use the pooled one; serverless functions opening direct connections per invocation can exhaust Postgres's connection limit under concurrent load, a well-known gotcha). Python driver: `psycopg2-binary` (precompiled wheel, no C build toolchain needed at deploy time).

**Environment variable name is not yet known and must be confirmed at setup time, not guessed here.** When a Postgres store is attached to a Vercel project, Vercel auto-populates one or more connection-string env vars, but the exact name(s) depend on the integration path used at provisioning time (commonly seen names include `POSTGRES_URL`, `DATABASE_URL`, `POSTGRES_PRISMA_URL`, `POSTGRES_URL_NON_POOLING` — Vercel's own Storage tab lists exactly which ones exist for a given project once created). The implementation plan must include a step to provision the database first, read the actual variable name(s) from the Vercel dashboard, and use the pooled one — not assume a name in advance.

Schema (`vercel-demo/schema.sql`, run once manually via the Vercel Postgres dashboard's query editor as part of setup — no ORM, no migration tool, this is a two-table personal-scale schema):

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

`holdings` has no uniqueness constraint — the same symbol can appear in multiple rows (separate purchase lots at different prices/dates). `watchlist` has `UNIQUE (device_id, symbol)` — a symbol is either being watched or not, adding it twice is a no-op error (409), not a duplicate row.

### Identity plumbing

`vercel-demo/src/lib/deviceId.js`:
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
Every holdings/watchlist `fetch()` call sends `X-Device-Id: <id>`. Endpoints read this header directly (no cookies, no sessions) — a missing/empty header is a 400.

### API endpoints

All four are new Python files under `vercel-demo/api/`, following the existing `BaseHTTPRequestHandler` pattern. All reuse `recommender.build_asset_payload` for live scoring (no duplicated scoring logic — matches the dedup fix from the dashboard's final review) and the existing per-item failure-tolerance pattern from `/api/dashboard` (one bad symbol goes into a `failed` list, doesn't 500 the whole response).

**`GET /api/holdings`** — list this device's holdings, each enriched with live data:
```json
{
  "holdings": [
    {
      "id": 1, "symbol": "RELIANCE.NS", "buy_price": 2400.50, "quantity": 10, "buy_date": "2025-06-01",
      "current_price": 2550.75, "unrealized_pnl": 1502.50, "unrealized_pnl_pct": 6.26,
      "days_held": 64, "ltcg_applicable": true, "ltcg_eligible": false, "days_to_ltcg": 301,
      "momentum": 0.04, "momentum_detail": {"return_10d": 0.02, "trend_vs_sma50": 0.06},
      "sentiment": 0.1, "day_change_pct": 1.2, "matched_headlines": [...],
      "scores": {"intraday": {...}, "short_term": {...}, "swing": {...}},
      "sell_signal": {"action": "Hold", "reason": "Both short-term and long-term signals remain positive."}
    }
  ],
  "failed": [{"id": 2, "symbol": "XYZ", "error": "..."}]
}
```
`current_price` is `closes[-1]` from the same fetch used for scoring. `ltcg_applicable` is `true` only when the symbol looks like Indian equity (`symbol.upper().endswith((".NS", ".BO"))`, matching the convention already used throughout `UNIVERSE`) — India's 365-day LTCG rule is specific to Indian equity. Both crypto (`-USD`, flat 30% tax, no long-term/short-term distinction) and unsuffixed US equity (a different country's capital-gains rules entirely, e.g. `AAPL`) fall outside it, so `ltcg_eligible`/`days_to_ltcg` are `null` for both — a plain `not symbol.endswith("-USD")` check would incorrectly apply India's LTCG framing to a US stock holding, which this spec deliberately avoids.

**`POST /api/holdings`** — body `{"symbol", "buy_price", "quantity", "buy_date"}` (date as `"YYYY-MM-DD"`). Validates: symbol non-empty; `buy_price > 0`; `quantity > 0`; `buy_date` is a valid date not in the future. **Also attempts a live price fetch before inserting** (`prices_source.fetch_price_history(symbol)`) — if that fails, reject with a clear error rather than silently saving an unfetchable symbol (matches the project's fail-loudly philosophy). On success: `201` with the inserted row (no enrichment — that happens on `GET`).

**`DELETE /api/holdings?id=N`** — deletes the row if it belongs to the requesting `device_id` (WHERE clause includes both `id` and `device_id`, so one device can never delete another's row even if it guessed an ID). `204` on success, `404` if no matching row.

**`GET /api/watchlist`** — list this device's watchlist, each enriched exactly like a `/api/search` result (no `suggested`/sizing, same as search results today):
```json
{
  "watchlist": [
    {"id": 1, "symbol": "TATASTEEL.NS", "momentum": ..., "momentum_detail": {...}, "sentiment": ..., "day_change_pct": ..., "matched_headlines": [...], "scores": {...}}
  ],
  "failed": [...]
}
```

**`POST /api/watchlist`** — body `{"symbol"}`. Same live-fetch validation as holdings. `201` on success, `409` if `(device_id, symbol)` already exists ("already in your watchlist").

**`DELETE /api/watchlist?id=N`** — same ownership-scoped delete as holdings.

### Sell signal (holdings only)

A plain 2×2 rule on the sign of the `short_term` and `swing` scores already computed by `build_asset_payload` — no new scoring model, no invented narrative:

```python
def compute_sell_signal(scores: dict) -> dict:
    short_term_score = scores["short_term"]["score"]
    swing_score = scores["swing"]["score"]

    if short_term_score < 0 and swing_score < 0:
        return {"action": "Consider selling", "reason": "Both short-term and long-term signals have turned negative."}
    if short_term_score < 0 <= swing_score:
        return {"action": "Short-term weakness", "reason": "Short-term signal is negative but the long-term signal is still positive — your call whether to ride it out."}
    if swing_score < 0 <= short_term_score:
        return {"action": "Long-term weakness", "reason": "Long-term signal is negative but short-term is still positive — may be worth watching closely."}
    return {"action": "Hold", "reason": "Both short-term and long-term signals remain positive."}
```

### Holding-period / LTCG math

```python
from datetime import date

def compute_holding_period(buy_date: date, symbol: str) -> dict:
    days_held = (date.today() - buy_date).days
    ltcg_applicable = symbol.upper().endswith((".NS", ".BO"))
    if not ltcg_applicable:
        return {"days_held": days_held, "ltcg_applicable": False, "ltcg_eligible": None, "days_to_ltcg": None}
    ltcg_eligible = days_held >= 365
    days_to_ltcg = max(0, 365 - days_held)
    return {"days_held": days_held, "ltcg_applicable": True, "ltcg_eligible": ltcg_eligible, "days_to_ltcg": days_to_ltcg}
```

This is India-specific (365-day equity LTCG threshold, flat-rate crypto with no LTCG concept) and deliberately simple — it is not tax advice, just a holding-period fact surfaced alongside the signal. The UI must not present it as a recommendation to time a sale around the tax boundary; it's context, matching the spec's "no invented narrative" principle applied to tax as much as to sentiment.

## UI

Two new sections, added as two more tabs alongside the existing 4 (Day Trading / Short-Term / Swing / Top Movers / **My Holdings** / **My Watchlist**):

**My Holdings tab:** an "Add holding" form (symbol, buy price, quantity, buy date, submit), then a list of cards — each showing symbol, current price, unrealized P&L (₹ and %), days held, LTCG status ("Long-term eligible" / "301 days to long-term" / "N/A — crypto" as applicable), the sell signal (action + reason), and a delete button. Reuses `AssetCard`/`WhyPanel` for the momentum/sentiment breakdown (expandable), extended with the P&L/holding-period/sell-signal block above it.

**My Watchlist tab:** an "Add to watchlist" form (symbol, submit), then a list of cards identical in style to search results (reusing `AssetCard`/`WhyPanel` with `suggested={undefined}`, same as `SearchBox` today), plus a delete button per card.

Both tabs show a clear empty state ("No holdings yet — add one above") rather than a blank section, and both surface `failed` entries the same way the dashboard does today (visible, not silently dropped).

## Error handling

- Every write endpoint (`POST`/`DELETE`) validates input and returns a clear 400/404/409 with a message — never a raw 500 for a predictable, well-formed bad request.
- `POST` endpoints validate the symbol is actually fetchable before persisting (no garbage rows).
- `GET` endpoints tolerate per-item fetch failures (delisted ticker, transient error) without failing the whole list — consistent with `/api/dashboard`'s established pattern.
- Ownership is enforced at the SQL level (`WHERE id = %s AND device_id = %s`) on every delete — never trust a client-supplied ID alone.

## Testing

No automated test suite, consistent with the rest of `vercel-demo/` (an explicit, already-established decision, not an oversight here). Verification is: Python `ast.parse` + manual trace for backend files (this machine's pandas DLL block still applies to anything importing `sources.prices`), real `npm run build` for frontend files, and a manual checklist once deployed with a real database attached:
1. Add a holding, confirm it appears with live P&L/sell-signal data.
2. Add the same symbol to the watchlist, confirm it appears separately (both lists show it).
3. Delete a holding and a watchlist item, confirm each disappears.
4. Reload the page, confirm both lists persist (proves the database round-trip, not just React state).
5. Try adding an invalid symbol to each list, confirm a clear rejection, not a silently-saved broken row.
6. Open the dashboard in a different browser (or an incognito window), confirm it shows *empty* holdings/watchlist — proves device-scoping actually isolates data, not a global list.

## Out of scope

- Real user accounts / login — anonymous device ID only, per decision #2.
- Cross-device sync — a direct consequence of no login.
- Editing an existing holding (fix a typo'd price/quantity) — delete and re-add instead. Small enough to add later if it turns out to matter.
- Realized P&L / sell execution tracking (recording that you actually sold, at what price) — this spec only covers unrealized P&L on currently-held positions and a sell/hold *signal*, not a transaction ledger.
- Any actual tax filing support — the LTCG/STCG context is informational, not tax advice, and not scoped to handle every edge case of Indian capital gains law (e.g., grandfathering rules, STT, indexation for debt funds — none of that applies here since this is equity/crypto only).
- Multi-currency support — holdings are assumed to be priced in the same currency the symbol trades in (₹ for `.NS` symbols, $ for US symbols, etc.); no FX conversion or unified-currency P&L rollup.
