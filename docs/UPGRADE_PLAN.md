# QuantDesk Upgrade: Stock Research & Recommendation System

> How to use: save this file as `D:\ai-trader\docs\UPGRADE_PLAN.md`, open Claude Code in `D:\ai-trader`, and say:
> **"Read docs/UPGRADE_PLAN.md. Do Phase 0 only, then stop and show me what you found."**
> Then go phase by phase. Never ask for all phases at once.

---

## Context (for Claude Code)

You are working in my repo `D:\ai-trader` (QuantDesk). Read the code before changing anything.

- Stack: Python backend, PostgreSQL, React frontend, deployed on Vercel. Market data via Zerodha Kite Connect.
- It already has: momentum screening, holdings view, and a backtesting engine. A reworked momentum strategy backtested to ~175% over 10 years (~10–11%/yr). That is roughly index-level, so beating the index is the real bar.
- I have the `day-trader-skill` pack installed (`trader-scanner`, `trader-news`, `trader-entry`, `trader-exit`, `trader-timemachine`, `trader-risk`, `trader-budget`, `trader-broker`, `trader-alerts`, `trader-analyst`, `trader-pelosi`). They are built for **US day trading** (Yahoo, Nasdaq, SEC EDGAR, Alpaca). Use them as **design references and code patterns**, not as-is.

### My goal
Turn QuantDesk into a **research and recommendation system for Indian stocks, mainly for long-term investing**. It should give me a ranked list of stocks worth studying (value + quality + growth, with momentum as a timing filter), explain *why* each one is on the list, and alert me. I am **learning**, so teaching me is part of the job.

### Hard rules
1. **No live order placement.** Research, backtests, paper portfolios and alerts only. No code path may call Kite `place_order` / `modify_order` / GTT endpoints.
2. **Learning mode:** for every concept you introduce (P/E, ROCE, CAGR, drawdown, look-ahead bias…), add a short beginner explanation to `docs/learn/` (one file per topic, plain English, one Indian-stock example).
3. **Every recommendation must show its reasons**: which filters it passed, its scores, and the data date.
4. Data sources must be **pluggable** (one interface, swappable providers). Check each source's terms of use before scraping. Prefer official or explicitly permitted sources. If a source isn't allowed, stop and tell me rather than working around it.
5. Benchmark everything against **buy-and-hold** (Nifty 50 TRI, and Nifty Midcap 150 TRI for mid-cap strategies) **after costs** (brokerage, STT, slippage).
6. Small commits, tests for every calculation, and stop at the end of each phase for my review.

---

## Phase 0: Study (no code changes)

1. Map my current repo: modules, data flow, DB tables, how the backtest engine works, and where the momentum strategy lives.
2. Read every `trader-*/SKILL.md` and its Python file. For each, write a short explanation for a beginner: what problem it solves, how it works, what's reusable for an Indian long-term research system, and what isn't.
3. Write `docs/ARCHITECTURE.md` (my system today) and `docs/SKILLS_REVIEW.md` (the skill pack mapped onto my system).
4. Propose the target architecture as a diagram plus a list of new modules. **Stop here.**

## Phase 1: Universe + fundamentals data

1. **Universe:** all NSE-listed equities, tagged Large/Mid/Small cap using AMFI's official semi-annual market-cap categorisation (Large = top 100, Mid = 101–250, Small = 251+). Store the category history with dates.
2. **Fundamentals provider interface** returning: price, market cap, P/E, P/B, revenue, net profit, EPS, ROE, ROCE, debt/equity, operating cash flow, promoter holding and pledge %, all with **period** and **publication date**.
   - Candidate sources to evaluate (check terms first): NSE/BSE corporate filings (quarterly results XBRL), company annual reports, and yfinance `.NS` tickers (unofficial, fine for prototyping). Recommend one and tell me the trade-offs.
3. Store everything **point-in-time** (what was known on which date). This matters for Phase 3.
4. Learn docs: `market-cap.md`, `pe-ratio.md`, `roe-roce.md`, `debt-equity.md`, `promoter-pledge.md`.

## Phase 2: The screener + recommendation score

Port the *pattern* from `trader-scanner` (scan a whole universe, then rank) to fundamentals.

1. **Configurable filters** (YAML or DB), defaults for a "quality mid-cap at a fair price" screen:
   - Market cap category = Mid (configurable)
   - P/E below its **sector median** (not an absolute number; a "low" P/E differs a lot between IT and banks)
   - Revenue CAGR 3y ≥ 12%, profit CAGR 3y ≥ 12%
   - ROCE ≥ 15% (banks/NBFCs: use ROE/ROA instead, and skip debt/equity)
   - Debt/equity ≤ 0.5, positive operating cash flow in 3 of the last 3 years
   - Promoter pledge ≤ 5%
2. **Composite score** (0–100) = Value + Quality + Growth + Momentum (reuse my existing momentum code), with weights in config.
3. **Red-flag checks** that remove or penalise a stock: falling promoter holding, rising receivables faster than revenue, auditor changes, repeated losses, pledge spikes. Explain each red flag in `docs/learn/`.
4. Output a ranked table on the React dashboard: name, sector, score breakdown, filters passed/failed, data date, and a 3–4 line plain-English "why it's here" summary.
5. Learn docs: `value-vs-quality-vs-growth.md`, `sector-relative-valuation.md`.

## Phase 3: Backtest the screener honestly

Port the idea of `trader-timemachine` (replay history and show honest odds) to long-term investing.

1. Backtest: each quarter, run the screener **using only data published before that date**, buy the top N equal-weighted, rebalance quarterly, over 10 years.
2. Avoid the two classic traps and explain them to me in `docs/learn/backtest-biases.md`:
   - **Look-ahead bias:** using results before they were published.
   - **Survivorship bias:** only testing companies that still exist today. Include stocks that were delisted or fell out of the mid-cap band.
3. Report: CAGR, max drawdown, worst year, volatility, win rate per rebalance, turnover, and costs, vs Nifty Midcap 150 TRI and Nifty 50 TRI.
4. Add a Monte Carlo / bootstrap view (like `trader-timemachine`): resample the historical rebalance returns and show the range of outcomes, not just one number.
5. Show results for 2–3 parameter sets, and warn me if I'm overfitting (great backtest, fragile to small parameter changes).

## Phase 4: Discovery feed (internet, YouTube, news)

The aim is to treat recommendations from the internet as an **"attention signal"**, never a buy signal.

1. **Company news & filings:** adapt `trader-news` and `trader-analyst` to NSE/BSE corporate announcements and quarterly results: what changed this quarter vs last and vs a year ago.
2. **Insider / promoter activity:** adapt the `trader-pelosi` idea to India: SEBI insider-trading (PIT) disclosures, SAST filings, and NSE bulk/block deals.
3. **YouTube / web mentions:** use the official YouTube Data API (search + video titles/descriptions; respect API terms and quotas) and reputable news RSS. Extract stock names mentioned and store: source, date, stance (bullish/bearish/neutral).
4. **Track the recommenders:** for every channel/source, record how their mentioned stocks performed 3/6/12 months later vs the index. Over time this shows me whose ideas were actually any good.
5. A mentioned stock only appears on my list if it **also passes the Phase 2 screener**. Show the mention as context.

## Phase 5: Alerts + paper portfolio

1. Adapt `trader-alerts`: a Telegram bot that sends a weekly digest (new stocks entering/leaving the top list, with reasons) and event alerts (results published, red flag triggered, price hits my watch level).
2. Adapt `trader-budget` + `trader-risk` into a **paper portfolio**: position sizing by fixed amount per stock, max % per stock and per sector. Track it live vs the index for at least 6 months before I consider real money.
3. Learn docs: `position-sizing.md`, `diversification.md`, `when-to-sell.md`.

## Phase 6 (later, optional): the trading lab

Keep short-term / Nifty options work as a **separate, paper-only module** for learning. Use the `trader-*` intraday pipeline (signal → entry → exit → timemachine → risk) on Nifty index data. No live orders.

---

## At the end of every phase
- Summarise what you built, what you learned about the data, and what surprised you.
- List the new `docs/learn/` files so I can study them.
- Give me 3 questions to check my understanding.
- Wait for my go-ahead.
