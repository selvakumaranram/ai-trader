# AI Trader (QuantDesk): Project Discovery

| | |
|---|---|
| Discovery date | 2026-10-13 |
| Repository | `D:\ai-trader`, branch `master`, HEAD `d5bb50c` (2026-08-05) |
| Method | Read-only inspection of all 65 tracked files, the full git history (59 commits), and the existing offline test suite (`python -m pytest -q`). Web research against official docs where reachable. |
| Status labels | **Implemented**: code exists and was traced end to end. **Partial**: code exists but is incomplete or has a known gap. **Missing**: no code. **Unverified**: code exists, but its live behavior could not be confirmed from this environment (needs network, a deployed database, or a production run). |

> Not financial advice. This document describes software. It makes no claims about strategy performance. The repository contains **no backtest results**, and none are reported here.

---

## 1. Executive summary

The repository is **QuantDesk**. The name "AI Trader" appears nowhere in the code. QuantDesk is a **research and screening dashboard**, not a trading system. It has two layers:

1. **A root-level Python CLI** (`recommender.py`, `backtest.py`, `sources/`) that ranks 8 assets (crypto, US and Indian equities) by a blend of price momentum and VADER headline sentiment. It also suggests rupee allocations and runs a single-symbol SMA-crossover backtest.
2. **A Vercel web app** (`vercel-demo/`), the more developed and actively maintained part. It has:
   - a React/Vite single-page app;
   - 7 Python serverless endpoints;
   - a Postgres database (holdings, watchlist, momentum rankings);
   - a daily cron job that screens the Nifty 200 using a rule-based momentum strategy with NSE quality filters, fixed-percentage stop-loss and target levels, and client-side position sizing.

**What does not exist:** there is no Claude/LLM integration, no Zerodha Kite Connect integration, no options logic of any kind (option chains, Greeks, IV, OI), no order execution, no paper trading, no trade monitoring or alerts, and no trade journal. "AI" in the current product means the VADER lexicon sentiment scorer only.

**Engineering quality:** good for its scope. Error handling is careful and degrades gracefully, the design specs are explicit, and **34 of 34 unit tests pass**. However:

- most of the deployed web-app code paths have no tests;
- the root and `vercel-demo/` code bases have drifted apart and duplicate each other;
- data comes from **unofficial sources**: yfinance, which is for personal use only, and NSE website endpoints, whose Terms of Use prohibit automated collection;
- several security defaults are weak for anything beyond a personal demo.

---

## 2. Original purpose and product vision (inferred)

From [README.md](../README.md), the four design specs under [docs/superpowers/specs/](superpowers/specs/), and the commit history:

- **Stated principle:** "research first, execution second." Outputs are framed as research prompts ("Research LONG" / "Watchlist"), not trade signals.
- **Phase 1 (built):** a research and recommendation engine for intraday, short-term, and swing styles across crypto, US equities, and Indian equities.
- **Phase 2 (planned in the README, not started):**
  1. backtesting foundation (VectorBT/PyBroker);
  2. strategy library;
  3. paper trading (Kite WebSocket, Freqtrade dry-run);
  4. execution via OpenAlgo + pykiteconnect;
  5. risk engine with a kill switch;
  6. tiny go-live, only after beating buy-and-hold out-of-sample after costs.
- The README has an explicit "Reality Check" section. It anchors to realistic returns and warns that sentiment is not a signal.
- **Options trading is not mentioned anywhere in the repository.** The options-focused "AI Trader" workflow in your brief is a new direction relative to the codebase.

Development timeline (from git):

| Date | Milestone |
|---|---|
| 2026-08-03 | Baseline skeleton imported. Fake scoring replaced with real yfinance prices and RSS/VADER sentiment. Backtest syntax bug fixed. |
| 2026-08-03/04 | Vercel deployment, then the React dashboard (3 style tabs, Top Movers, any-symbol search, client-side sizing). |
| 2026-08-04/05 | Holdings and personal Watchlist backed by Postgres, with anonymous device-ID identity. |
| 2026-08-05 | Momentum Screener: NSE data source, scoring module, daily cron, `/api/momentum`, Momentum UI section. |
| since 2026-08-05 | No commits. Working tree: `.gitignore` modified (adds `.env`), and `Momentum_Based_Short_Term_Stock_Strategy.md` is untracked. |

---

## 3. Existing features and implementation status

| # | Feature | Location | Status | Notes |
|---|---|---|---|---|
| F1 | Momentum + sentiment ranking CLI (8 assets) | [recommender.py](../recommender.py) | **Implemented** but practically **broken by default** | `RSS_FEEDS` URLs are dead (documented in [api/dashboard.py:16-19](../vercel-demo/api/dashboard.py#L16-L19)). `fetch_headlines` raises `RuntimeError` when every feed fails, so the CLI aborts. |
| F2 | Static HTML dashboard writer | [recommender.py:118](../recommender.py#L118) | Implemented | Writes a gitignored `dashboard.html`. |
| F3 | SMA-crossover backtest vs buy-and-hold (1 symbol, 1y) | [backtest.py](../backtest.py), [vercel-demo/api/backtest.py](../vercel-demo/api/backtest.py) | **Partial** | No costs or slippage. Trades execute on the same bar's close that generated the signal. Reports only the final value; no drawdown, trade list, or win rate. Unused variable `entry_price`. |
| F4 | Web dashboard: Day Trading / Short-Term / Swing tabs (40 assets) | [api/dashboard.py](../vercel-demo/api/dashboard.py), [StyleSection.jsx](../vercel-demo/src/components/StyleSection.jsx) | Implemented, live behavior **Unverified** | One live fetch per page load: 40 yfinance downloads plus 1 RSS feed (Yahoo Finance, overridden in code). |
| F5 | "Why" explanation panel | [WhyPanel.jsx](../vercel-demo/src/components/WhyPanel.jsx) | Implemented | Deterministic text: 10-day return, trend vs SMA50, matched headlines. No AI. |
| F6 | Top Movers (gainers/losers by day % change) | [TopMovers.jsx](../vercel-demo/src/components/TopMovers.jsx) | Implemented | Limited to the 40-asset universe. |
| F7 | Any-symbol search | [api/search.py](../vercel-demo/api/search.py) | Implemented | Sentiment keyword is the ticker itself, so sentiment is usually neutral (a disclosed limitation). |
| F8 | Capital input + client-side position sizing | [positionSizing.js](../vercel-demo/src/lib/positionSizing.js) | Implemented | Caps: at most 60% deployed, 20% per idea, minimum ticket 2% of capital. Conviction-weighted by score, not risk-based (no stop-distance sizing). |
| F9 | My Holdings: manual entry, P&L, LTCG countdown, sell signal | [api/holdings.py](../vercel-demo/api/holdings.py), [holdings_logic.py](../vercel-demo/holdings_logic.py) | Implemented, **Unverified** (needs a database) | The sell signal uses only momentum/sentiment score signs. It ignores the buy price, so there is no stop-loss relative to entry. |
| F10 | My Watchlist | [api/watchlist.py](../vercel-demo/api/watchlist.py) | Implemented, **Unverified** | |
| F11 | Device-ID identity (no login) | [deviceId.js](../vercel-demo/src/lib/deviceId.js) | Implemented | A random UUID stored in localStorage. See §12. |
| F12 | NSE data adapter: Nifty 200, F&O ban, ASM, GSM, bhavcopy | [sources/nse.py](../vercel-demo/sources/nse.py) | Implemented, **Unverified** | The ASM/GSM URLs are marked "NOT independently confirmed" in code. NSE may block cloud IPs (spec §Risks). |
| F13 | Momentum scoring module (returns, RSI, EMA20/50 trend, volume, quality gates, risk levels, pool-normalized score) | [momentum_screen.py](../vercel-demo/momentum_screen.py) | Implemented and tested | MACD and ATR from the strategy doc are **not** implemented. Stop-loss and targets are fixed at −5% / +10% / +15% of last close. |
| F14 | Daily cron screen → `momentum_rankings` | [api/cron/momentum_screen.py](../vercel-demo/api/cron/momentum_screen.py), [vercel.json](../vercel-demo/vercel.json) | Implemented, **Unverified** | Runs at 13:30 UTC (19:00 IST) on weekdays. Requires a provisioned database, the schema applied, and optionally `CRON_SECRET`. |
| F15 | Momentum UI: Screener + 1D/3D/7D/1M Movers | [MomentumSection.jsx](../vercel-demo/src/components/MomentumSection.jsx), [api/momentum.py](../vercel-demo/api/momentum.py) | Implemented | Reads cached rows only. Shows a staleness warning after 2 days. |
| F16 | Momentum-strategy backtest tab | spec §Backtest | **Missing** | In scope in the design spec (decision 7), but explicitly deferred to "a separate, later plan" in the implementation plan. No code exists. |
| F17 | Paper trading, execution, risk engine, kill switch | README Phase 2 | **Missing** | |
| F18 | Reddit / YouTube / Finnhub sentiment sources | README "Data sources" | **Missing** | Only RSS is implemented. |
| F19 | `strategies/`, `engine/`, `data/` directories | README tree | **Missing** | The directories do not exist. |
| F20 | Claude / LLM integration | n/a | **Missing** | No `anthropic` import, prompt, or agent anywhere. |
| F21 | Kite Connect / OpenAlgo integration | n/a | **Missing** | No `kiteconnect` dependency or code. |
| F22 | Options analytics (chain, Greeks, IV, OI, strategies) | n/a | **Missing** | The only F&O-related data is the F&O **ban list**, used as an exclusion filter. |

---

## 4. Technology stack and dependencies

| Layer | Technology | Source of truth |
|---|---|---|
| Language (backend) | Python. Local interpreter is 3.14.6. The README says "3.10+". The Vercel Python runtime version is not pinned anywhere. | [README.md](../README.md) |
| HTTP handlers | Standard library `http.server.BaseHTTPRequestHandler`, using the Vercel Python serverless convention. No framework. | `vercel-demo/api/*.py` |
| Market data | `yfinance>=0.2` (prices, OHLCV, `.info` fundamentals). NSE archive CSVs via `requests>=2.31`. | [vercel-demo/requirements.txt](../vercel-demo/requirements.txt) |
| News / sentiment | `feedparser>=6.0`, `vaderSentiment>=3.3.2` | same |
| Database | PostgreSQL via `psycopg2-binary>=2.9`. Raw SQL, no ORM, no migration tool. Connection from `DATABASE_URL` or `POSTGRES_URL`. | [db.py](../vercel-demo/db.py), [schema.sql](../vercel-demo/schema.sql) |
| Frontend | React 18.3, Vite 5.4, `@vitejs/plugin-react` 4.3. Plain CSS. No router, no state library, no TypeScript. | [package.json](../vercel-demo/package.json) |
| Hosting | Vercel: Vite static build, Python functions (60 s max), cron function (300 s max), Vercel Cron. | [vercel.json](../vercel-demo/vercel.json) |
| Tests | pytest. 34 tests in `tests/`. No frontend tests, no CI. | [tests/](../tests/) |
| Local Node | v24.18.0. `node_modules/` and `dist/` exist locally and are gitignored. | |

Dependency hygiene: every Python dependency is a floor (`>=`), with no lock file, so builds are not reproducible. The frontend has a `package-lock.json`.

---

## 5. Architecture and component responsibilities

```
                          Browser (React SPA, vercel-demo/src)
                 ┌──────────────────────────────────────────────────┐
                 │ App.jsx: 7 tabs · CapitalInput · SearchBox       │
                 │ positionSizing.js (client-side sizing)            │
                 │ deviceId.js → X-Device-Id header (apiFetch)       │
                 └───────┬──────────────┬──────────────┬────────────┘
                         │              │              │
          /api/dashboard │  /api/search │ /api/holdings│ /api/watchlist   /api/momentum
          (live fetch)   │  (live)      │ (DB + live)  │ (DB + live)      (DB read only)
                         ▼              ▼              ▼                       ▼
                 ┌──────────────────────────────────────────┐      ┌──────────────────┐
                 │ recommender.py (vercel-demo copy)        │      │ Postgres         │
                 │  _compute_momentum · build_asset_payload │      │  holdings        │
                 │ sources/prices.py (yfinance OHLCV)       │◄────►│  watchlist       │
                 │ sources/news.py (RSS + VADER)            │      │  momentum_rankings│
                 │ holdings_logic.py (sell signal, LTCG)    │      └────────▲─────────┘
                 └──────────────────────────────────────────┘               │
                                                                            │ DELETE+INSERT
   Vercel Cron 13:30 UTC Mon-Fri → /api/cron/momentum_screen ───────────────┘
        sources/nse.py (Nifty200, F&O ban, ASM, GSM, bhavcopy)
        yfinance OHLCV + .info fundamentals (200 symbols, 10 threads)
        momentum_screen.py (pure scoring functions)

   Root CLI (separate, older copy):  recommender.py · backtest.py · sources/{prices,news}.py
```

| Component | Responsibility |
|---|---|
| `sources/prices.py` | Downloads 6 months of history from yfinance. Normalizes the single-column DataFrame quirk. Drops NaN-close rows (vercel-demo) or raises on NaN (root). |
| `sources/news.py` | Fetches RSS, matches headlines by word-boundary keyword, scores mean VADER compound in [−1, 1]. |
| `sources/nse.py` | Cookie-primed NSE session. Fetches the Nifty 200 list, F&O ban, ASM/GSM lists, and the latest-trading-day bhavcopy (volume, delivery %). Detects anti-bot HTML responses. |
| `recommender.py` | Momentum = 0.5 × 10-day return + 0.5 × (price / SMA50 − 1), clipped to ±1. Style mix of momentum and sentiment. "Research LONG" when score ≥ 0.15. |
| `momentum_screen.py` | Pure functions: returns (1/3/7/21 trading days), Wilder RSI14, EMA20/50 trend gate, volume increase, volume confirmation, 8 quality gates (unknown counts as fail), fixed % risk levels, pool min-max normalized weighted score. |
| `holdings_logic.py` | Sell signal from signs of the short-term and swing scores. LTCG 365-day countdown, applied to `.NS`/`.BO` symbols only. |
| `api/*.py` | Thin handlers: validation, thread-pool fan-out (10 workers), JSON responses, per-item failure lists, warnings. |

---

## 6. Main data flows

**A. Dashboard load** (`GET /api/dashboard`)
1. Fetch the Yahoo RSS feed. On failure, continue with a warning.
2. Download 6 months of prices in parallel for 40 assets.
3. For each asset, score 3 styles (intraday / short_term / swing).
4. Return `{assets, failed, warning}`.
5. The browser ranks the top 10 per style and sizes positions from the user's capital.

There is no caching, so every page load triggers about 41 external fetches.

**B. Holdings** (`GET/POST/DELETE /api/holdings`, keyed by `X-Device-Id`)
- POST validates the input, makes a live price fetch to prove the symbol works, then inserts.
- GET reads rows, re-scores each holding live, computes P&L, the LTCG countdown, and the sell signal.

**C. Momentum screen** (cron)
1. Open an NSE session and load the Nifty 200 list. This step is mandatory.
2. Load the F&O ban, ASM, and GSM lists. Each one degrades to `unknown` independently if it fails.
3. Walk back up to 10 days to find the latest bhavcopy.
4. Per symbol, in parallel: yfinance OHLCV and `.info`. Attach bhavcopy volume and delivery % only when its date matches yfinance's last bar.
5. `build_symbol_metrics`, then pool-wide `compute_momentum_scores`.
6. In one transaction, `DELETE` rows for `run_date` and then `INSERT`.

**D. Momentum read** (`GET /api/momentum?tab=…`)
- Uses the latest `run_date`.
- The Screener tab shows rows that pass both quality and trend gates, ordered by score, top 20.
- The Movers tabs show market-cap-passing rows ordered by return, top 20.
- The browser sizes positions for Screener rows.

---

## 7. Existing AI and trading strategy logic

**AI:** none in the LLM sense. The only machine scoring is **VADER**, a rule-based lexicon sentiment model, applied to RSS headlines. The README names FinBERT/LLM as a "future upgrade path".

**Strategies, exactly as coded:**

| Strategy | Entry logic | Exit / risk logic | Validation |
|---|---|---|---|
| Style ranking | Score = w_m × momentum + w_s × sentiment. Weights: intraday 0.8/0.2, short_term 0.7/0.3, swing 0.55/0.45. "Research LONG" when ≥ 0.15. | None. | Unit tests on the momentum math only. No backtest. |
| SMA crossover (`backtest.py`) | Long when SMA(short) > SMA(long). | Flat when SMA(short) < SMA(long). | Single symbol, 1 year, no costs, same-bar execution. |
| Momentum screener | Must pass all 8 quality gates **and** price > EMA20 > EMA50. Ranked by weighted score: 1M 30%, 7D 25%, 3D 15%, 1D 10%, volume increase 10%, delivery % 5%, RSI factor 5%. | Stop −5%, targets +10% and +15% of **last close**. The trailing stop mentioned in the strategy doc is **not** implemented. | Unit tests on the functions. The **backtest is missing**. |
| Holdings sell signal | n/a | "Consider selling" when both the short-term and swing scores are below 0. | None. |

Observations about the strategy code:

- **Delivery % never contributes to volume confirmation.** `deliveries` is passed as a one-element list ([api/cron/momentum_screen.py:93](../vercel-demo/api/cron/momentum_screen.py#L93)). `compute_volume_confirmation` needs `lookback + 1 = 4` points ([momentum_screen.py:98](../vercel-demo/momentum_screen.py#L98)), so the "rising delivery %" branch is dead in production. The delivery-% **level** is still used as a score factor.
- **"Promoter holding" is a proxy.** The value comes from yfinance `heldPercentInsiders`, which is not the same as SEBI-disclosed promoter holding. Because `unknown` counts as fail, sparse yfinance coverage (`.info` for NSE tickers) can shrink the Screener to few or zero rows. The debt-to-equity /100 normalization is a code-documented **assumption**.
- **The "7 Day" return is 7 trading days** (about 9 to 10 calendar days), and "1 Month" is 21 trading days.
- **"Entry" in the UI is the last close.** There is no entry-trigger rule, such as a breakout level, limit range, or time-of-day.
- **Position sizing is not risk-based.** It ignores stop distance and volatility.

---

## 8. Broker and market-data integration status

| Integration | Status | Detail |
|---|---|---|
| Zerodha Kite Connect | **Missing** | Mentioned in the README roadmap and in an "out of scope" line in the dashboard spec only. |
| OpenAlgo | **Missing** | README roadmap only. |
| yfinance (Yahoo) | Implemented | Daily bars only. Used for every price in the app. Unofficial, "intended for personal use only" (see §14). |
| NSE website archives | Implemented, **Unverified** | Unofficial endpoints. NSE's Terms of Use prohibit automated data collection (see §14). Cloud-IP blocking risk is acknowledged in the spec. |
| RSS news | Implemented | The root config's feeds are dead. The web app hard-overrides them to Yahoo Finance RSS in 4 files. |
| Intraday / real-time data | **Missing** | Despite the "Day Trading" tab label, all data is end-of-day daily bars. |
| Options-chain data | **Missing** | |

---

## 9. Database schema and domain models

Source: [vercel-demo/schema.sql](../vercel-demo/schema.sql). The schema is applied manually. There are no migrations.

| Table | Key columns | Constraints | Purpose |
|---|---|---|---|
| `holdings` | `device_id`, `symbol`, `buy_price NUMERIC`, `quantity NUMERIC`, `buy_date DATE` | index on `device_id` | Manually entered positions. |
| `watchlist` | `device_id`, `symbol` | `UNIQUE(device_id, symbol)` | Personal watchlist. |
| `momentum_rankings` | `run_date`, `symbol`, `sector`, `pe_ratio`, `current_price`, `return_1d/3d/7d/1m`, `passes_quality_gates`, `passes_trend_gate`, `quality_gate_detail JSONB`, `momentum_score`, `volume_confirmation`, `stop_loss`, `target_low`, `target_high` | `UNIQUE(run_date, symbol)`, index on `run_date` | One snapshot per trading day. Prior days are retained; a same-day rerun replaces that day. |

Domain models are plain dicts. There are no dataclasses or Pydantic models.

The main implicit shapes are:
- the **asset payload**, from `build_asset_payload`: `symbol, type, momentum, momentum_detail, sentiment, day_change_pct, matched_headlines, scores{style:{score, action}}`;
- **symbol metrics**, from `build_symbol_metrics`.

Missing entities needed for the target product: instruments, candles, option-chain snapshots, signals/setups, decisions (accepted or rejected, with reason), orders, fills, positions, alerts, LLM requests/responses, and strategy versions.

`momentum_rankings` is the only existing table that is useful as a historical signal log.

---

## 10. Current APIs and integrations

| Method & path | Auth | Request | Response | Errors |
|---|---|---|---|---|
| `GET /api/dashboard` | none | n/a | `{assets[], failed[], warning}` | 500 with traceback |
| `GET /api/search?symbol=` | none | symbol | asset payload + `warning` | 400, 502, 500 with traceback |
| `GET /api/backtest?symbol=&short=&long=` | none | | `text/plain` summary | 500 with traceback, including for non-integer params |
| `GET/POST/DELETE /api/holdings` | `X-Device-Id` | POST `{symbol, buy_price, quantity, buy_date}`; DELETE `?id=` | list / created row / 204 | 400, 404, 502, 500 with traceback |
| `GET/POST/DELETE /api/watchlist` | `X-Device-Id` | POST `{symbol}`; DELETE `?id=` | list / created / 204 | 400, 404, 409, 502, 500 with traceback |
| `GET /api/momentum?tab=screener\|1d\|3d\|7d\|1m` | none | | `{run_date, stale, total_screened, rows[]}` | 400, 503 if no run yet, 500 with traceback |
| `GET /api/cron/momentum_screen` | `Bearer CRON_SECRET` **only if the env var is set** | | `{run_date, symbols_scored, symbols_failed, failed, degraded_sources}` | 401, 500 |

Every endpoint except the cron endpoint sends `Access-Control-Allow-Origin: *`. Outbound links go to `screener.in` from momentum rows.

---

## 11. Tests, deployment, and development setup

**Tests** (verified by running them): `python -m pytest -q` gives **34 passed, 2 warnings** (VADER `codecs.open` deprecation) in 31 s. All network calls are monkeypatched.

| Test file | Targets | Gap |
|---|---|---|
| `test_core.py` (5) | **root** `recommender.py`, `backtest.py` | Does not cover the deployed `vercel-demo/recommender.py` (`build_asset_payload`, `derive_fallback_keyword`). |
| `test_news.py` (8) | root `sources/news.py` | Identical to the vercel-demo copy, so coverage transfers. |
| `test_prices.py` (5) | root `sources/prices.py` | Does **not** cover the vercel-demo `fetch_ohlcv_history`, which has different NaN semantics. |
| `test_momentum_screen.py` (16) | `vercel-demo/momentum_screen.py` | Good unit coverage. |

**Untested:**
- `sources/nse.py`;
- `holdings_logic.py`;
- every `api/*.py` handler, including the cron orchestration and SQL;
- `positionSizing.js` and all React components.

There is no CI, linter, formatter, or type checker configured.

**Deployment:** Vercel, configured by `vercel.json`. The memory notes and specs say the Postgres database and schema need **manual provisioning**. Whether a production deployment exists, and whether the cron has ever run successfully against NSE, is **Unverified**.

**Local setup:**
- Root CLI: `pip install -r requirements.txt`, then `python recommender.py` or `python backtest.py RELIANCE.NS 20 50`.
- Web app: in `vercel-demo/`, `npm install` and `npm run dev` for the frontend only. The Python API needs `vercel dev` or a deployment.
- A local `.env` exists containing a `DATABASE_URL` key (value not read or reproduced). Git history check: `.env` **was never committed**. The pending `.gitignore` change that adds `.env` is uncommitted.

**Repo tooling:** `.claude/skills/claude-api/SKILL.md` is misnamed. Its contents are a generic "python-engineering-process" skill, not Claude API guidance.

---

## 12. Security issues and technical debt

### Security (severity is for the current personal-demo context; all of these become blockers before any broker integration)

| # | Issue | Where | Severity |
|---|---|---|---|
| S1 | **Python tracebacks returned to clients** in 500 responses. This leaks file paths, library versions, and possibly connection details from exception text. | all `api/*.py` except cron | High |
| S2 | **The cron endpoint is unauthenticated when `CRON_SECRET` is unset.** Anyone can trigger a 300-second, 200-symbol fan-out against NSE and Yahoo from your IP range, costing compute and risking an IP ban. | [api/cron/momentum_screen.py:226](../vercel-demo/api/cron/momentum_screen.py#L226) | High |
| S3 | **The device ID is the only credential.** It is a bearer-equivalent UUID in localStorage, with no login, expiry, or rotation. Unacceptable for anything holding broker tokens or real positions. | `deviceId.js`, holdings/watchlist | Medium (by design for the demo) |
| S4 | `Access-Control-Allow-Origin: *` on every endpoint. | all API handlers | Medium |
| S5 | No rate limiting. Each public GET fans out to dozens of external requests (amplification). | dashboard, search, holdings | Medium |
| S6 | Unbounded `Content-Length` read on POST. | holdings, watchlist | Low |
| S7 | **Terms-of-service exposure:** NSE scraping and yfinance's personal-use restriction (§14). This is a legal/compliance risk, not a code bug. | `sources/nse.py`, `sources/prices.py` | Medium to High if published or commercialized |
| S8 | Watchlist duplicate check is SELECT-then-INSERT. A race hits the UNIQUE constraint, which surfaces as a 500 with traceback. | [api/watchlist.py:95-104](../vercel-demo/api/watchlist.py#L95-L104) | Low |

No hard-coded secrets were found in tracked files.

### Technical debt

1. **Two divergent code bases.** The root `recommender.py`, `backtest.py`, and `sources/` are older copies of the `vercel-demo/` versions:
   - the universe is 8 vs 40 assets;
   - `derive_fallback_keyword` and `build_asset_payload` exist only in vercel-demo;
   - the NaN policy differs;
   - `write_dashboard` exists only in root.

   The tests mostly target the root copy, while production runs the vercel-demo copy.
2. **Monkeypatched config.** `recommender.RSS_FEEDS` is overridden at import time in 4 API modules. The root config's dead feeds were never fixed.
3. **Duplicated logic:**
   - `_device_id_from_headers` and `_send_json` are duplicated across handlers;
   - position sizing exists in both Python (`MIN_TICKET = 500`) and JS (`minTicket = 2%`), with different semantics.
4. **No caching layer.** Live fetches happen on every request, against unofficial upstreams.
5. **No migrations, no ORM or typed models, no structured logging, no observability.** Cron results are only visible in Vercel logs.
6. **Unpinned Python dependencies.** The Python runtime version is not pinned for Vercel.
7. **The README describes a repository tree** (`dashboard.html`, `strategies/`, `engine/`, `data/`) that does not match reality.
8. **Serverless is a poor fit for the next phase.** Vercel functions are stateless with a 60–300 s timeout. They cannot hold a Kite WebSocket open or monitor trades continuously. SEBI's static-IP requirement for API orders (§14) also needs a fixed egress IP, which a Vercel function does not provide by default. Verify Vercel's current options if you want to stay on it.

---

## 13. Gaps between the existing implementation and the intended product

| Target capability (from your brief) | Current state | Gap |
|---|---|---|
| Obtain market and historical data | Daily bars via yfinance; NSE end-of-day CSVs | No authorized feed. No intraday, tick, or index-option data. No local candle store. |
| Analyse trend, price action, indicators, volume, volatility | EMA20/50, RSI14, SMA50, returns, volume ratio | No ATR, MACD, Bollinger, VWAP, realized volatility, or support/resistance. No multi-timeframe analysis. |
| Options-chain analysis | None | Needs: instruments master, chain assembly, IV, Greeks, OI/ΔOI, PCR, expiry handling, lot sizes. |
| Claude interprets structured market info | None | Needs: an LLM client, a feature-to-prompt contract, structured-output schemas, prompt/version logging, and evals. |
| Generate option setups (instrument, entry, SL, target, R:R, exit) | Equity-only fixed % SL/targets | No setup generator, no R:R computation, no exit conditions, no options instruments. |
| Monitor open trades; alert on SL/target/invalidation | None | Needs a persistent worker, live prices, alert rules, and notification channels. |
| Kite Connect data, then controlled execution | None | Needs: daily OAuth login flow, token storage, rate-limit handling, static IP, order safety (market protection, tags), kill switch. |
| Record signals, decisions, rejections, simulated and actual results | `momentum_rankings` daily snapshots only | No signal/decision/outcome journal, paper-trade ledger, or evaluation reports. |
| Backtesting with realistic costs | SMA toy backtest | Needs an event-driven or vectorized engine with Indian costs (STT, exchange, GST, stamp duty, brokerage), slippage, no look-ahead, walk-forward. **Historical option data is a hard prerequisite** (§14). |

---

## 14. External research findings

Research date: 2026-10-13. I searched selectively and did not read everything published. "Verified" means read on the official page during this session. "Secondary" means taken from broker blogs, news coverage, or search summaries; confirm against primary sources before relying on it.

### 14.1 Anthropic Claude API

| Finding | Source | Status | Relevance |
|---|---|---|---|
| Current models: Opus 5.5 (`claude-opus-5-5`, $4 / $20 per MTok input/output), Sonnet 5.5 (`claude-sonnet-5-5`, $2 / $10), Haiku 5.5 (`claude-haiku-5-5`, from $0.10 / $0.50), and Fable 5.1 for demanding reasoning. All have 1M-token context and tool use. Batch API is 50% off. Prompt-cache reads are discounted. | https://platform.claude.com/docs/en/about-claude/models/overview (fetched 2026-10-13) | Verified | Model choice and cost. Explanations could use Sonnet or Haiku, with Opus reserved for deeper review. Pin model IDs in the signal journal. |
| **Structured outputs:** `output_config.format` with `type: "json_schema"` constrains responses to a schema. `strict: true` on tools validates tool inputs. Python `client.messages.parse()` accepts Pydantic models. No beta header is needed; the old `output_format` parameter is deprecated. Unsupported: numeric `minimum`/`maximum`, string length limits, recursive schemas. Refusals or `max_tokens` can still yield non-conforming output. | https://platform.claude.com/docs/en/build-with-claude/structured-outputs | Verified | Setup and explanation payloads should be schema-constrained. Numeric bounds (for example, SL below entry) must still be **validated in code**, because the schema cannot express them. |
| **Tool use:** client tools return `tool_use` blocks, and your code returns `tool_result`. `tool_choice` supports auto/any/tool/none and `disable_parallel_tool_use`. The SDK "Tool Runner" automates the loop. Server tools such as web search incur extra charges. | https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview | Verified | Claude can call read-only tools (get_features, get_option_chain_summary). **Order placement must never be a Claude-callable tool** in the recommended design. |

### 14.2 Zerodha Kite Connect

| Finding | Source | Status | Relevance |
|---|---|---|---|
| **Login flow:** redirect to `kite.zerodha.com/connect/login?v=3&api_key=…`, receive a one-time `request_token`, compute `checksum = SHA-256(api_key + request_token + api_secret)`, then POST `/session/token` to get an `access_token`. The token **expires at 6 AM the next day** (described as a regulatory requirement). Never expose `api_secret` client-side. | https://kite.trade/docs/connect/v3/user/ | Verified | Requires a daily human login and server-side secret storage. The docs do not describe automated login. |
| **Rate limits:** quote 1 req/s, historical 3 req/s, orders 10 req/s, others 10 req/s. Order caps: 400/min, 5,000/day per user/API key, 25 modifications per order. | https://kite.trade/docs/connect/v3/exceptions/ | Verified | Chain refresh cadence and backfill throughput must be designed around these limits. |
| **WebSocket:** up to 3,000 instruments per connection, 3 connections per API key. Modes are `ltp`, `quote`, and `full`. `full` carries 5-level depth and, from the packet layout, OI. | https://kite.trade/docs/connect/v3/websocket/ | Verified (the OI detail is inferred from the packet layout) | Live monitoring needs a persistent process. |
| **Quotes:** `/quote` takes up to 500 instruments per call and is the only quote endpoint that includes OI. `/quote/ohlc` and `/quote/ltp` take up to 1,000. **No dedicated option-chain endpoint.** The instruments CSV is regenerated daily (fetch around 08:30); use exchange + tradingsymbol as the key because tokens get reused. | https://kite.trade/docs/connect/v3/market-quotes/ | Verified | Option chains must be built in-house from the instruments dump plus `/quote`. |
| **Historical candles:** minute to day intervals, `oi=1` flag. Expired contracts cannot be looked up. `continuous=1` gives day candles for expired **futures** only (NFO/MCX). | https://kite.trade/docs/connect/v3/historical/ | Verified | **Kite does not provide historical data for expired options.** An options backtest needs data you record yourself going forward or a third-party vendor. |
| **Orders:** varieties `regular`, `amo`, `co`, `iceberg`, `auction`; types MARKET/LIMIT/SL/SL-M. `market_protection` takes 0–100 or `-1` (auto) for MARKET and SL-M orders. Optional `tag` (alphanumeric, max 20 chars). A successful placement does not mean execution, so check order history. | https://kite.trade/docs/connect/v3/orders/ | Verified | Every order should carry a strategy/signal tag and explicit market protection, and be reconciled afterward. |
| **Pricing:** data APIs (real-time + historical) cost ₹500/month per app. Order and account APIs have been free since March 2025, and "Personal" apps are free. | https://kite.trade/forum/discussion/15015/revising-kite-connect-fees-from-2000-to-500-per-month (May 2025, Zerodha staff post) | Secondary (official forum, not the pricing page) | A paid Connect app is needed for chain and historical data. Confirm on the developer console. |

### 14.3 SEBI / exchange regulation

| Finding | Source | Status | Relevance |
|---|---|---|---|
| SEBI circular **"Safer participation of retail investors in Algorithmic trading"**, SEBI/HO/MIRSD/MIRSD-PoD/P/CIR/2025/0000013, dated **4 Feb 2025**. Requirements: no open APIs; client-specific API keys; broker-whitelisted static IPs; OAuth + 2FA; orders above an orders-per-second threshold treated as algos needing registration. | Copy on exchange site: https://ncdex.com/public/uploads/circulars/Safer%20participation%20of%20retail%20investors%20in%20Algorithmic%20trading_1738763308.pdf; also https://www.cse-india.com/upload/upload/Feb_042025.pdf | Secondary (exchange-hosted copy found; sebi.gov.in original not fetched) | The framework this project must comply with. |
| Timeline: extended to 1 Oct 2025, then (circular of 30 Sep 2025) a broker glide path with **full applicability from 1 Apr 2026**. | https://taxguru.in/sebi/sebi-extends-algo-trading-implementation-timeline-april-2026.html ; https://upstox.com/news/market-news/financial-regulations/sebi-extends-timeline-for-retail-algo-trading-framework-sets-glide-path-for-brokers/article-182285/ | Secondary | The rules are in force now. Check for later amendments. |
| Zerodha's explainer (31 Mar 2026): from 1 Apr 2026, **all API order users need a static IP** (primary + secondary); **≤ 10 orders/sec needs no strategy registration**; above that, registration and audit through the broker; **plain market orders via API need market protection**; family accounts may share an IP, unrelated users may not. | https://inthemoneybyzerodha.substack.com/p/sebi-algo-trading-changes-april-2026 | Secondary (broker-authored) | Design constraint for execution: run on a static-IP host, stay well below 10 OPS, never send unprotected market orders, and keep the system personal-use only unless registered. |
| SEBI study (July 2025): about **91% of individual equity F&O traders lost money in FY25**, with net losses of about ₹1.05 lakh crore. An earlier study found 93% lost money over FY22–24. | https://www.business-standard.com/markets/news/net-losses-of-traders-in-fo-widens-in-fy25-sebi-study-125070701221_1.html | Secondary (news coverage of SEBI study) | Base rate for options trading. Strong reason for paper trading, journaling, and conservative risk limits. |

### 14.4 Data licensing and backtesting practice

| Finding | Source | Status | Relevance |
|---|---|---|---|
| NSE Terms of Use prohibit "systematic or automated data collection activities (including scraping, data mining, data extraction…)" without permission. | https://www.nseindia.com/static/nse-terms-of-use | Secondary (the page timed out on direct fetch; the clause is quoted from the search index) | `sources/nse.py` is likely in conflict. Replace it with Kite data or licensed sources where possible. |
| yfinance: "intended for research and educational purposes"; "the Yahoo! finance API is intended for personal use only". | https://github.com/ranaroussi/yfinance | Verified | Acceptable for personal research only. Not suitable as a production or commercial feed. |
| Backtesting practice: model costs and slippage, avoid look-ahead (signal on bar *t*, fill on bar *t+1*), use walk-forward or out-of-sample validation. | Already stated in the project's own README and momentum spec. No external source fetched this session. | Recommendation | To check: NSE/Zerodha cost-calculator pages for current STT and charges on options; a survey of historical options-data vendors for NSE. |

---

## 15. Recommended architecture for the next phase

Guiding rule: **deterministic code computes, Claude explains, risk rules gate, a human approves.** Claude never chooses prices or sizes that are not first computed and validated in code, and it never has an order-placing tool.

```
                     ┌──────────────────── always-on service (static-IP VPS) ───────────────────┐
 Kite login (daily)  │                                                                           │
 ───────────────────►│  auth: token vault (encrypted, server-side)                               │
                     │                                                                           │
                     │  ingest:  instruments (08:30) · historical candles · WebSocket ticks      │
                     │      │                     (rate-limited client, Kite primary)            │
                     │      ▼                                                                    │
                     │  store: Postgres (+Timescale optional) — candles, chain snapshots         │
                     │      │                                                                    │
                     │      ▼                                                                    │
                     │  features: indicators, volatility, IV/Greeks (computed locally), OI/PCR   │
                     │      │                                                                    │
                     │      ▼                                                                    │
                     │  setup engine (rule-based, versioned)  →  candidate setups                │
                     │      │                                                                    │
                     │      ▼                                                                    │
                     │  risk engine (hard limits: max loss/trade, per day, lot caps, R:R ≥ x)    │
                     │      │ accepted / rejected(reason)                                         │
                     │      ▼                                                                    │
                     │  Claude layer: structured-output explanation + critique of the setup      │
                     │      (read-only tools; schema-validated; model id + prompt version logged)│
                     │      │                                                                    │
                     │      ▼                                                                    │
                     │  journal: signals · decisions · rejections · LLM I/O · paper fills ·      │
                     │           real fills · outcomes                                           │
                     │      │                                                                    │
                     │      ├──► monitor worker: SL / target / invalidation → alerts             │
                     │      └──► execution adapter (LAST, feature-flagged, human-confirm,         │
                     │           market_protection, order tags, kill switch, ≤ few OPS)          │
                     └───────────────────────────────────────────────────────────────────────────┘
                                         ▲ REST/JSON (auth'd)
                                         │
                               React dashboard (existing SPA, extended)
```

Key decisions to make (recommendations, not yet approved):

1. **Move off pure serverless for the trading core.** A small always-on Python service (for example FastAPI with a worker process) on a host with a static IP. The existing React SPA can remain on Vercel or move with it.
2. **Consolidate on one Python package.** Make `vercel-demo/` the source, retire or port the root copies, and point the tests at it.
3. **Make Kite the primary data source.** Keep yfinance only for non-Indian or research fallback. Phase out NSE scraping.
4. **Store your own option-chain snapshots from day one.** This is the only realistic path to options backtesting without a vendor (Kite cannot return expired option candles).
5. **Use typed domain models** (Pydantic) shared between the setup engine, the Claude structured-output schemas, and the API, plus real migrations (for example Alembic).
6. **Make the journal the primary record.** Every signal is persisted with its inputs, strategy version, risk verdict, Claude output, and eventual outcome, so evaluation is possible without trusting memory.

---

## 16. Prioritised implementation roadmap

Each phase lists what it depends on and its acceptance criteria. Live order execution comes last.

| # | Phase | Depends on | Scope | Acceptance criteria |
|---|---|---|---|---|
| 0 | **Hygiene and consolidation** | none | Single code base. Tests cover deployed modules (`nse.py`, `holdings_logic.py`, handlers with a fake DB). Remove tracebacks from responses. Require `CRON_SECRET`. Pin dependencies and the Python version. Add CI (pytest + build). Commit the `.gitignore` fix. Fix the README tree. | CI green on every push. No duplicate modules. No 500 response contains a traceback. Cron returns 401 without a secret. |
| 1 | **Kite data foundation** | 0; paid Kite Connect app | Daily login flow with an encrypted server-side token store. Instruments sync. Rate-limited historical-candle backfill into Postgres. Data-quality checks (gaps, duplicates, stale). | Backfill of the chosen underlyings (for example NIFTY, BANKNIFTY, and a stock list) is reproducible. Rate limits are never exceeded in logs. The token is never exposed to the browser. |
| 2 | **Signal and decision journal** | 0 | Tables: `strategy_versions`, `signals`, `setups`, `risk_decisions`, `llm_calls`, `paper_trades`, `trades`, `outcomes`. Migrations. Typed models. | Every screen or setup run writes immutable journal rows that can be queried by date, strategy version, and outcome. |
| 3 | **Options analytics** | 1 | Chain assembly from instruments + `/quote` (batched to 500, at most 1 req/s). Local IV and Greeks (Black-76 on futures, or Black-Scholes). OI/ΔOI, PCR, expiry calendar, lot sizes. Scheduled chain **snapshots** persisted. | Chain for a chosen underlying and expiry is rendered. Computed Greeks are within tolerance of a reference calculator on sample contracts. Snapshots accumulate daily. |
| 4 | **Backtest and evaluation harness** | 1, 2 (and 3 for options) | Next-bar fills. Indian cost model. Slippage. Walk-forward. Port the momentum-backtest spec (F16) first, because equity data is available now. Options backtests only on recorded snapshots or vendor data. | Reports trade list, win rate, average R, max drawdown, and costs. A look-ahead unit test is in place. The result is compared to buy-and-hold over the same window. |
| 5 | **Rule-based setup generator + risk engine** | 2, 3 | Deterministic setups (instrument, entry trigger/range, SL, targets, R:R, invalidation, time exit). Hard limits on max loss per trade and per day, max lots, and minimum R:R. Rejections are journaled with reasons. | Each setup is reproducible from stored inputs. The risk engine has 100% branch coverage on its limit rules. |
| 6 | **Claude interpretation layer** | 5 | Anthropic SDK. `output_config.format` JSON schema built from Pydantic models. Read-only tools. Prompt templates are versioned. Input/output, model ID, and token cost are logged to `llm_calls`. A validator re-checks numbers against the setup. An eval set of historical setups is used. | Claude output always parses or fails closed. No Claude output can change a price or size without failing validation. Cost per run is reported. |
| 7 | **Monitoring, alerts, paper trading** | 1, 5 | WebSocket worker. SL, target, and invalidation rules. Notifications (channel to be chosen). Paper-trade ledger fed from live ticks. | Alerts fire within N seconds of the condition in a recorded replay test. Paper P&L reconciles with the journal. Runs unattended through a full trading week. |
| 8 | **Controlled execution (optional)** | 7, plus a paper-trading track record you define | Static-IP host. Human confirmation per order. `market_protection` always set. Order `tag` = signal ID. Kill switch. Daily loss lockout. Order reconciliation. Far below 10 OPS. Personal account only. | A dry-run mode exists. The kill switch is tested. Every live order is traceable to a journaled, human-approved signal. Compliance checklist (§14.3) is signed off. |

The critical path is **0 → 1 → 3 → 5 → 6**. Phase 2 can run in parallel with Phase 1. Phase 4 for equities can start right after Phases 1 and 2.

---

## 17. Open questions (cannot be answered from the repository)

1. **Naming and scope:** is "AI Trader" a rename of QuantDesk, or a new product alongside it? Should crypto and US equities stay in scope, or should the focus become Indian F&O only?
2. **Deployment state:** is the Vercel app deployed? Is Postgres provisioned and the schema applied? Has the cron ever completed against NSE, and what did `degraded_sources` report?
3. **Instruments:** which underlyings (NIFTY, BANKNIFTY, FINNIFTY, stock options)? Weekly or monthly expiries? Option buying only, or also selling and spreads? The margin and risk models differ greatly.
4. **Kite account:** do you have, or will you buy, a Kite Connect **data** subscription? Do you already have a static IP or VPS?
5. **Historical options data:** will you record your own snapshots going forward, or buy vendor data for backtests? What budget?
6. **Execution ambition:** alerts and manual execution only, or eventually semi-automated orders? Will it ever be used for anyone other than you or your family? Third-party use triggers SEBI algo-provider obligations.
7. **Risk policy:** capital, maximum loss per trade and per day, maximum open positions, and minimum R:R you want hard-coded.
8. **Alerts:** preferred channel (Telegram, email, push, SMS) and acceptable latency.
9. **Claude usage:** monthly LLM budget? Do you want Claude only to explain and critique, or also to propose setups for deterministic validation?
10. **Hosting:** stay on Vercel for the UI and add a VPS for the core, or move everything to one host?
11. **Data licensing:** are you willing to drop the NSE-scraping adapter in favour of Kite and licensed sources?
12. **Untracked strategy note:** should `Momentum_Based_Short_Term_Stock_Strategy.md` be committed as the canonical strategy document?

---

### Appendix: what was and was not examined

- **Examined fully:** all 65 tracked files. The four specs and four plans were skimmed for scope and deferral notes rather than read line by line. Also examined: git log (59 commits), `.claude/` settings and skills.
- **Examined partially:** `.env`, for key **names** only (value redacted, not read into this document).
- **Not examined (generated or third-party):** `vercel-demo/node_modules/`, `vercel-demo/dist/` (build output), `__pycache__/`, `.pytest_cache/`, `vercel-demo/package-lock.json` contents, `src/index.css` styling.
- **Not executed:** any network call to yfinance, NSE, RSS, Kite, or the deployed app. Live behavior of those paths is marked **Unverified** above.
