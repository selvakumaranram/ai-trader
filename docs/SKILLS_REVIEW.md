# The `trader-*` skill pack, reviewed for QuantDesk

Phase 0 study, written 2026-11-05. I read every `SKILL.md` in full, and every Python file's structure (functions,
data sources, outputs) in `~/.claude/skills/trader-*`.

The pack is built for **US day trading**: buy in the morning, sell before the 4 pm close, Yahoo prices, SEC EDGAR
filings, the Alpaca broker. You want the opposite: **Indian stocks held for years**, chosen on fundamentals. So almost
none of the code runs for you as-is. What carries over is the **design**: how each tool is built, what it refuses to
do, and how it reports honestly.

## How the pack fits together (for a beginner)

```
scanner → news → entry → exit → timemachine → budget → risk → broker      (+ alerts, analyst, pelosi on the side)
"what's    "why is   "when    "where   "what are   "how     "is it    "send it,
moving?"   it        exactly  do I     the odds?"  many     within    only after
           moving?"  to buy?" get out?"            shares?" my rules?" your yes"
```

Each step is a small standalone Python script (standard library only, no API keys) that reads and writes JSON files
in a `trader/` folder, so the next step can pick up where the last one stopped.

---

## The skills one by one

### 1. trader-scanner: "Which charts match my rule today?"
- **Problem:** there are about 5,900 US stocks, and nobody can look at every chart each morning.
- **How:**
  1. It builds the list of tradable stocks from Nasdaq's symbol files, dropping warrants, units and preferreds.
  2. It downloads closing prices 20 tickers per request.
  3. It tags simple chart setups: a 20-day closing-high breakout, a bull flag, a reclaimed 20-day average, and
     oversold readings by RSI.
  4. It writes a watchlist sorted by how much was traded.
- **Reusable for you:**
  - The **scan-then-rank pattern**, which is exactly Phase 2's screener.
  - Its **honesty rules**: say how many were scanned and how many failed ("fetched 4,980 of 5,259"), say "matched a
    rule", never "a buy".
  - **Cleaning the universe** before scanning; your version will drop SME stocks, ETFs and suspended stocks.
- **Not reusable:** the US symbol lists, Yahoo's "spark" endpoint, the intraday opening-range scan and the NYSE clock.
  Your core already has daily bars in Postgres, so you don't need to download prices per scan.

### 2. trader-news: "Did anything happen to my stocks?"
- **Problem:** a chart can look great right before bad news or results.
- **How:**
  1. Per ticker, it reads Yahoo headline RSS and the company's SEC filings feed.
  2. It tags each item (earnings, deal, legal, people, regulatory, macro) and marks important filing types.
  3. It shows only what's new since the last check, using a fingerprint of each item.
  4. It marks stocks that moved 3% or more.
- **Reusable for you:**
  - The **"only new items, never repeat" state file**.
  - **Tagging announcements by type.**
  - **"Filings beat headlines"** and "a headline is a lead, not a fact".
  - India equivalent: NSE/BSE corporate announcements (results, board meetings, auditor changes, credit ratings,
    pledges). That is Phase 4 step 1, and also a source of Phase 2 red flags (auditor change).
- **Not reusable:** the Yahoo RSS URLs, SEC's 8-K item codes and the US time zone.

### 3. trader-analyst: "What did the company actually report?"
- **Problem:** press releases put the best number first.
- **How:**
  1. It reads the numbers a company **filed** with the SEC (XBRL "company facts").
  2. It lines up revenue, margins, net income and EPS quarter by quarter, each against the **same quarter a year
     earlier**, with trailing-twelve-month totals.
  3. It **derives** Q4 as the full year minus three quarters, and labels it "derived".
  4. It flags one-offs (net income above operating income) and says when the data lags the latest filing.
- **Reusable for you** (the most valuable skill for Phase 1):
  - Its whole approach to fundamentals: **filed numbers first**, compare like with like, label anything derived,
    flag one-offs, and say when data is stale.
  - Indian companies file quarterly results with NSE/BSE, in XBRL for listed companies. Its quarter-alignment,
    trailing-twelve-month and year-on-year logic maps almost one-to-one onto a `fundamentals/` provider.
  - Its "what changed this quarter" summary is Phase 4 step 1.
- **Not reusable:** the SEC endpoints, US-GAAP tag names (Indian filings use Ind-AS / different XBRL taxonomies),
  and the 10-Q/10-K/8-K structure.

### 4. trader-pelosi: "What did insiders publicly disclose?"
- **Problem:** members of the US Congress must disclose their trades, but only as PDFs, up to 45 days late.
- **How:**
  1. It reads the House Clerk's yearly index file and notices new reports.
  2. It downloads each PDF and turns it into rows: who, buy or sell, the amount **range**, and how many days late.
  3. It flags stocks you hold.
  4. For the Senate, it refuses to automate a site that requires you to accept terms, and documents a manual route.
- **Reusable for you:**
  - The **"alert once per new filing"** state pattern.
  - The **honesty rules**: show amounts as ranges, show the delay, and say "public and weeks old, not inside
    information".
  - The **terms-of-use discipline**: it won't click through an agreement for you. That's your rule 4.
  - India equivalent (Phase 4 step 2): SEBI insider-trading (PIT) disclosures, SAST takeover-code filings, promoter
    pledge changes, and NSE bulk/block deals.
- **Not reusable:** anything specific to the US Congress or its PDFs.

### 5. trader-timemachine: "What are the honest odds?"
- **Problem:** one good-looking backtest can be luck.
- **How:**
  1. It takes the stock's own last 60 days of 5-minute bars and rebuilds the rest of today **10,000 times** by
     sampling past bars from the same time of day.
  2. It counts how often the target came first, the stop came first, or neither.
  3. It also re-runs the same rule on every real past day ("history").
  4. It prints a verdict that accounts for the reward-to-risk: a 2R target only needs to win 1 time in 3.
  5. It uses a fixed random **seed** so results can be repeated.
- **Reusable for you** (Phase 3 step 4):
  - The **resampling idea**: resample your quarterly rebalance returns thousands of times and show the spread of
    10-year outcomes, not one number.
  - **Show the real history next to the simulation, and say plainly when they disagree.**
  - The fixed seed.
  - Its **verdict wording** ("close to a coin flip", "leans toward…") that never rounds luck up into an edge.
- **Not reusable:** the intraday bar sampling and the target/stop race.

### 6. trader-alerts: "Tell me when something happens."
- **Problem:** nobody can watch prices all day.
- **How:**
  1. Alert rules (above, below, stop, target, % move, time of day, opening bell) live in a JSON file.
  2. A `check` command fetches delayed quotes and rings each alert **once** (state file), with "rearm" if wanted.
  3. It knows NYSE holidays and early closes.
- **Reusable for you** (Phase 5): the **rule types plus a once-only state**, and the "an alert is a fact, never an
  order" wording. Your Telegram digest is a new delivery channel for the same rule engine. Your core already has the
  NSE holiday calendar and a scheduler.
- **Not reusable:** the NYSE clock, the Yahoo and Stooq quote URLs, and the day-trading defaults (flat by close).

### 7. trader-budget: "How much should I buy?"
- **Problem:** without rules, position size is a guess.
- **How:**
  - **Day-trade mode:** it sizes to the smallest of four limits (maximum loss per trade, position cap, maximum order,
    cash after a buffer) and says **which limit decided it**.
  - **Weights mode:** it splits a budget across a list by weight, caps each stock, and redistributes the excess.
- **Reusable for you** (Phase 5 paper portfolio):
  - **Weights mode is close to what you need:** a fixed amount per stock, a maximum % per stock, a cash buffer, and
    whole shares.
  - "Say which limit decided it" is a good habit for your "why it's here" explanations.
  - You'll add a **per-sector cap**, which it doesn't have.
- **Not reusable:** the bracket order format for Alpaca and the stop-based sizing (long-term holdings usually have no
  hard stop).

### 8. trader-risk: "Does this break my rules?"
- **Problem:** in the moment, people break their own rules.
- **How:**
  1. It checks every proposed order against your limits: stop required, maximum loss, reward-to-risk, daily loss,
     trades per day, position and cash limits, blocked tickers.
  2. It prints **PASS or BLOCK with the reason**.
  3. It **never blocks getting out**.
- **Reusable for you:** a **paper-portfolio rule check** before each rebalance:
  - maximum % per stock and per sector;
  - minimum number of holdings;
  - turnover warnings;
  - a block on any stock that failed the screener or has an active red flag.
  "Exits are never blocked" carries over too.
- **Not reusable:** the day-trading checks (entry window, pattern-day-trader rule, daily trade count).

### 9. trader-entry and 10. trader-exit: "When do I get in, and where do I get out?"
- **Problem:** turning a setup into an exact entry time and price, then a stop and target **before** buying.
- **How:**
  - **Entry:** waits bar by bar for the first **completed** 5-minute bar that closes above the opening range.
  - **Exit:** puts the stop at the range midpoint (or an ATR multiple) and the target at 2R; it refuses stops that are
    too tight for the spread.
- **Reusable for you:**
  - Mostly for **Phase 6 (trading lab)** only.
  - Two habits carry over everywhere. **Only completed bars count** (the same no-look-ahead rule as point-in-time
    data). **Decide the exit before the entry**; for a long-term holding that's a written sell rule (thesis broken,
    red flag, valuation), the subject of `when-to-sell.md` in Phase 5.
- **Not reusable** for long-term investing: opening ranges, intraday bars, flat-by-close.

### 11. trader-broker: "Send the order, only after your yes."
- **Problem:** an AI should never place an order on its own.
- **How:**
  - It shows each order as a plain ticket.
  - It records your **typed yes word for word**.
  - It relies on Claude's own "Allow once" permission card.
  - It only accepts orders that trader-risk passed today (matched by a fingerprint).
  - It never trades from a background task.
- **Reusable for you:** **nothing that sends orders**. Your rule 1 forbids it, and your code already has no order
  methods (enforced by a test). Two ideas transfer:
  - **The fingerprint of an exact proposal:** your paper portfolio can fingerprint each rebalance it records.
  - **The paper/live separation** stays a hard wall: paper only.
- **Not reusable:** Alpaca, IBKR and the order setup. Do not port this skill.

---

## Patterns worth copying across the whole pack

1. **Small tools, files in between.** Each step reads the previous step's output and writes its own. In your system
   the "files" are Postgres tables with a `run_id` (you already do this with `ingestion_runs` and `backtest_runs`).
2. **State so nothing repeats** (news, alerts, filings): store a fingerprint of everything already shown.
3. **Honest output rules, written down:** say what was scanned and what failed; say "partial" when it is; never print
   a promise; quote the source with a link; label derived numbers.
4. **Refuse in one plain line** instead of guessing (missing data, a plan that doesn't make sense).
5. **Pinned clock and offline replay:**
   - Every tool accepts `--now` and saved data, so it can be tested on a fixed day.
   - Your point-in-time store needs the same idea: `as_of(date)`.
6. **Fixed random seed** for any simulation.
7. **Respect sources:** a polite pause between requests, identify yourself (SEC User-Agent), and never automate
   accepting terms.

## Mapped onto the upgrade phases

| Phase | Skill(s) to borrow from | What to borrow |
|---|---|---|
| 1 Data | trader-analyst | Filed-numbers-first fundamentals, quarter alignment, trailing twelve months, "derived" labels, lag notes |
| 2 Screener | trader-scanner (+ analyst) | Scan the whole universe, rank, honest counts, "matched a rule" language |
| 3 Backtest | trader-timemachine | Bootstrap of rebalance returns, history next to simulation, seed, honest verdict |
| 4 Discovery | trader-news, trader-pelosi, trader-analyst | New-items-only state, announcement tags, insider/SAST/bulk-deal rows, terms-of-use discipline |
| 5 Alerts + paper | trader-alerts, trader-budget (weights), trader-risk | Once-only alert rules, fixed-amount allocation with caps, rebalance rule check |
| 6 Lab | trader-entry, exit, timemachine, risk | The intraday pipeline on NIFTY data, paper only |
| never | trader-broker | No order placement (rule 1) |

## What the pack does NOT give you (new work)

- **India-specific data:** AMFI market-cap categories, NSE/BSE XBRL results, shareholding patterns and pledges,
  sector classification, and Nifty TRI series.
- **A point-in-time store and a survivorship-free universe.** The US pack never needed history beyond 60 days.
- **Long-term portfolio backtesting** (quarterly rebalance, turnover, costs against TRI).
- **Value, quality and growth scoring, sector-relative valuation and red flags.**
- **A Telegram delivery channel.**
