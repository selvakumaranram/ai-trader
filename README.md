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
quantdesk/
├── README.md              # this file
├── recommender.py         # Phase 1: research + recommendation + position sizing
├── backtest.py            # Phase 2 seed: SMA-crossover backtester vs buy-and-hold
├── dashboard.html         # sample output from recommender.py
│
├── sources/               # (planned) data adapters — RSS, Reddit, YouTube, Kite
├── strategies/            # (planned) strategy definitions for backtesting
├── engine/                # (planned) paper-trading + execution loop
└── data/                  # (planned) cached prices, news, sentiment scores
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

### Config (top of `recommender.py`)
| Setting | Meaning |
|---|---|
| `UNIVERSE` | assets to rank (symbol, type, keywords) |
| `RSS_FEEDS` | free news feeds to pull |
| `WEIGHTS` | momentum vs sentiment mix |
| `STYLE` | `intraday` / `short_term` / `swing` |
| `CAPITAL` | rupees to deploy (e.g. 25000) |
| `MAX_DEPLOY_PCT` | max % of capital deployed (default 60%) |
| `MAX_ALLOC_PER_IDEA` | max % in one name (default 20%) |

---

## Phase 2: Full Algo Trading (roadmap)

Grounded in the accompanying research report. Ordered so nothing risky ships early:

1. **Backtesting foundation** — extend `backtest.py`; migrate to **VectorBT** / **PyBroker** for fast, validated research. Drill look-ahead bias, costs, slippage, and walk-forward validation.
2. **Strategy library** — codify intraday + short-term equity + crypto strategies as pluggable modules driven by the Phase 1 research signals.
3. **Paper trading** — simulate against live prices: Kite Connect WebSocket for Indian equities, **Freqtrade dry-run** for crypto. No real money.
4. **Execution layer** — **OpenAlgo + pykiteconnect** for Zerodha order routing, once a strategy is validated.
5. **Risk engine** — per-trade risk limits, max daily loss, position caps, kill-switch.
6. **Go-live (tiny)** — real capital only for strategies that beat buy-and-hold out-of-sample after realistic costs.

---

## Tech stack

- **Language:** Python 3.10+
- **Data:** yfinance / Kite Connect (prices), RSS + Reddit API + YouTube Data API (news & sentiment)
- **Sentiment:** built-in lexicon → VADER → FinBERT / LLM (upgrade path)
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
git clone <your-repo-url> quantdesk && cd quantdesk

# Phase 1 runs with ZERO installs (standard library only):
python recommender.py            # prints watchlist + writes dashboard.html

# Upgrade to real data + better sentiment:
pip install yfinance vaderSentiment feedparser
python recommender.py

# Phase 2 seed — backtesting:
pip install pandas numpy matplotlib
python backtest.py RELIANCE.NS 20 50
```

Then edit `CAPITAL` and `UNIVERSE` at the top of `recommender.py` to match yours.

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
