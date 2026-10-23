# QuantDesk — Research-Driven Trading System

A solo-developer trading system that starts as an **honest research & recommendation engine** and grows into a **full algo-trading platform** — for Indian equities (Zerodha), US stocks, and crypto.

Built around one principle: **research first, execution second.** The system tells you *what to look at and how much to risk* before anything gets automated.

> ⚠️ **Not financial advice.** This is a learning + engineering project. Every output is a research prompt, not a trade signal. Paper trade before risking real money, and start with capital you can afford to lose. Doubling money monthly is impossible — anchor to realistic returns (see [Reality Check](#reality-check)).

---

## What it does

**Phase 1 — Research & Recommendation (built) ✅**
Ranks a watchlist for **intraday, crypto, and short-term equity** by combining:
- **Price momentum** — recent return + trend vs the 50-day average.
- **News sentiment** — headlines matched to each ticker and scored.
- **Position sizing** — suggests a rupee allocation per idea from your capital, with hard risk caps.

**Phase 2 — Full Algo Trading (planned) 🔜**
Turns researched ideas into backtested, paper-traded, then (optionally) live strategies via Zerodha Kite Connect / OpenAlgo. Every strategy must beat buy-and-hold *after costs, out-of-sample* before any real money is deployed.

---

## Repository structure

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

---

## Phase 1: Research & Recommendation

### Features
- Ranks any universe of crypto / Indian equity / US equity assets.
- **Style knob** (`intraday` / `short_term` / `swing`) shifts how much recent momentum matters.
- **Capital-aware position sizing** — conviction-weighted allocation with risk guardrails:
  - deploys at most **60%** of capital (keeps a cash buffer),
  - caps any single idea at **20%** of capital,
  - only sizes *long* ideas (shorts need separate margin/risk handling),
  - drops dust allocations below a minimum ticket.
- Outputs a **console table** and a **standalone HTML dashboard**.

### Example (₹25,000 capital)
```
RANK ASSET     TYPE         SCORE   SUGGEST   ACTION
1    BTC       crypto       +0.65  Rs 5,000   Research LONG
2    NVDA      equity_us    +0.45  Rs 3,500   Research LONG
3    INFY      equity_in    +0.43  Rs 3,300   Research LONG
4    RELIANCE  equity_in    +0.42  Rs 3,200   Research LONG
...
Suggested deployed: Rs 15,000  |  Cash buffer: Rs 10,000
```

> Scores now come from live price and news data, so exact numbers will
> differ every run — the table above is illustrative, not a fixed sample.

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

---

## Phase 2: Full Algo Trading (roadmap)

> The current, authoritative roadmap is [AI_Trader_README.md](AI_Trader_README.md) (NIFTY/BANKNIFTY long options, research + paper trading first). The list below is the original QuantDesk plan, kept for context.

Grounded in the accompanying research report. Ordered so nothing risky ships early:

1. **Backtesting foundation** — extend `backtest.py`; migrate to **VectorBT** / **PyBroker** for fast, validated research. Drill look-ahead bias, costs, slippage, and walk-forward validation.
2. **Strategy library** — codify intraday + short-term equity + crypto strategies as pluggable modules driven by the Phase 1 research signals.
3. **Paper trading** — simulate against live prices: Kite Connect WebSocket for Indian equities, **Freqtrade dry-run** for crypto. No real money.
4. **Execution layer** — **OpenAlgo + pykiteconnect** for Zerodha order routing, once a strategy is validated.
5. **Risk engine** — per-trade risk limits, max daily loss, position caps, kill-switch.
6. **Go-live (tiny)** — real capital only for strategies that beat buy-and-hold out-of-sample after realistic costs.

---

## Tech stack

- **Language:** Python 3.12 (pinned in `vercel-demo/.python-version`; CI runs 3.12)
- **Data:** yfinance / Kite Connect (prices), RSS + Reddit API + YouTube Data API (news & sentiment)
- **Sentiment:** VADER (lexicon-based, current) → FinBERT / LLM (future upgrade path)
- **Backtesting:** VectorBT / PyBroker / QuantConnect LEAN; Freqtrade for crypto
- **Execution:** OpenAlgo + pykiteconnect (Zerodha)
- **Dashboard:** standalone HTML now → FastAPI + Next.js later
- **Storage (planned):** PostgreSQL + TimescaleDB, Redis cache

---

## Data sources (legal & scalable only)

| Source | Use | Notes |
|---|---|---|
| RSS feeds | news | free, no key — works out of the box |
| Reddit API (PRAW) | retail sentiment | r/IndianStreetBets, r/wallstreetbets, r/CryptoCurrency |
| YouTube Data API | creator sentiment | free daily quota |
| yfinance / Kite Connect | prices | Kite for live Indian ticks |
| Finnhub / Alpha Vantage | news + fundamentals | free tiers |

> ❌ **No Instagram / Twitter comment scraping.** It violates platform terms, gets blocked by bot detection, breaks constantly, and risks bans + legal exposure. The official APIs above give the same signal reliably. This is a deliberate design choice, not a limitation.

---

## Quick start

```bash
pip install -r requirements-dev.txt
python -m pytest -q
python vercel-demo/recommender.py             # prints rankings + writes vercel-demo/dashboard.html
python vercel-demo/backtest.py RELIANCE.NS 20 50
cd vercel-demo && npm ci && npm run build      # frontend
```

Then edit `CAPITAL` and `UNIVERSE` at the top of `vercel-demo/recommender.py` to match yours.
Both scripts fetch live prices and news over the network on every run — there
is no offline or cached mode. A fetch failure aborts the run with an error
naming the symbol or feed that failed.

### Run the dashboard locally

The Python API normally runs only on Vercel. For local testing, `vercel-demo/dev_server.py` serves the same `api/*.py` handlers on `127.0.0.1:3001`, and Vite proxies `/api` to it in dev mode:

```bash
# terminal 1: API (reads DATABASE_URL / CRON_SECRET from the repo-root .env, never prints values)
python vercel-demo/dev_server.py

# terminal 2: UI
cd vercel-demo && npm run dev       # open http://localhost:5173
```

The dashboard, search and Top Movers need only internet access. Holdings, Watchlist and Momentum use the database in `DATABASE_URL`. To run the momentum screen locally (takes a few minutes; hits NSE and Yahoo):

```bash
curl -H "Authorization: Bearer $CRON_SECRET" http://127.0.0.1:3001/api/cron/momentum_screen
```

**Data tab:** if the AI Trader core service (`D:\ai-trader-core`, `python -m aitrader serve`) is running on
127.0.0.1:8765, a **Data** tab appears (Kite login, data coverage, job buttons, quality issues). It never appears on the
deployed Vercel site. A **Backtest** tab appears too: it runs strategy backtests on the local service and shows each
trade on a chart.

### Configuration (environment variables)

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` / `POSTGRES_URL` | for holdings, watchlist, momentum | Postgres connection string. Keep it in `.env` or Vercel env vars, never in git. |
| `CRON_SECRET` | **yes, for the momentum cron** | The cron endpoint refuses to run (503) without it. Vercel Cron sends it automatically as a Bearer token once set. |
| `ALLOWED_ORIGINS` | no | Comma-separated origins whose **simple GET** requests (dashboard, search, momentum, backtest) get a CORS header. Preflighted requests (holdings/watchlist with `X-Device-Id`, JSON POSTs, DELETE) are not supported cross-origin, because there is no `OPTIONS` handler. The same-origin UI needs nothing. |

### Phase 0 changes (2026-10)

Intentional behaviour changes from the AI Trader Phase 0 stabilisation:

- The root CLI moved to `vercel-demo/` (single source of truth). It now ranks the 40-asset universe using the working Yahoo RSS feed, and drops NaN closes instead of aborting.
- API 500 responses return `{"error": "Internal server error"}`; full details go to the server log only.
- No wildcard CORS. Cross-origin simple GETs are opt-in via `ALLOWED_ORIGINS`; preflighted cross-origin requests are not supported.
- The momentum cron requires `CRON_SECRET` (**set it in Vercel before deploying**, or the daily screen will not run).
- `/api/backtest` validates `short`/`long` and returns 400 for bad values.
- Adding a duplicate watchlist symbol returns 409, even under a concurrent double-submit.
- POST bodies over 64 KiB are rejected with 413.

---

## Reality Check

- **Realistic return:** long-run equity indices do roughly **8–12% per year** — with big drawdowns. That's the honest benchmark, and beating it consistently is hard.
- **Doubling monthly is a scam signal.** 100%/month compounds to >400,000%/year. No one sustains it.
- **Base rate:** most retail algo strategies *underperform* buy-and-hold after costs. Expect your first strategies to lose to a simple index fund — that's normal.
- **Sentiment ≠ signal.** Social spikes are often manufactured (pump-and-dump). Treat every score as a reason to *investigate*, never a trigger to *trade*.
- **Discipline > cleverness.** Paper trade for months. Size small. Never up-size to chase losses.

---

## Compliance

Comply with **SEBI** regulations (India), your broker's algo/API terms, and every data provider's Terms of Service. This project is for research and education.

---

## License

MIT (suggested) — add a `LICENSE` file before publishing.
