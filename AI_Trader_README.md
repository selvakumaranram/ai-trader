# AI Trader (QuantDesk) — Product Vision and Implementation Requirements

**Status:** Product vision and implementation brief  
**Initial market:** Indian index options — NIFTY and BANKNIFTY  
**Initial strategy scope:** Long options only (buy calls or puts)  
**Initial operating mode:** Research, historical backtesting, and paper trading  
**Execution:** Manual trading only; no live order placement in the initial versions  
**Future expansion:** Bitcoin and other cryptocurrency markets

---

## 1. Product vision

AI Trader is an AI-assisted market research, strategy-testing, and trade-monitoring system. Its purpose is to help a user who has limited chart-reading and technical-analysis experience understand potential trading opportunities without having to interpret every chart manually.

The system should analyse historical and current market data, evaluate clearly defined trading strategies, and explain in plain language:

- Whether a valid setup exists now.
- What conditions triggered the setup.
- Which instrument and option contract the strategy is evaluating.
- The potential entry conditions or entry range.
- Where the setup would be invalidated.
- The proposed stop-loss and target levels.
- The risk/reward calculation and assumptions.
- What conditions would trigger an exit.
- Why the system recommends waiting or avoiding a trade.

The application must not assume that a candle pattern or a single large buying/selling candle guarantees a profitable trade. Every strategy must be explicitly defined, tested on historical data, and evaluated after transaction costs and slippage.

**Core principle:** Make trading setups explainable and testable. Do not claim that a strategy works until the backtesting and out-of-sample evidence supports that conclusion.

## 2. Existing project context

The existing repository is called **QuantDesk**, while **AI Trader** is the intended product direction/name. Before renaming or restructuring anything, inspect the actual repository and preserve working features.

The project discovery report describes the current system as:

- A React/Vite dashboard.
- Python serverless API handlers under `vercel-demo/`.
- PostgreSQL storage for holdings, watchlist, and daily momentum rankings.
- A momentum screener for Indian equities using price/volume features and quality filters.
- An older root-level Python CLI and simple SMA-crossover backtest.
- A test suite with 34 passing tests at the time of the discovery report.

The discovery report also states that the current project does **not** yet contain:

- Claude/Anthropic API integration.
- Zerodha Kite Connect integration.
- NIFTY/BANKNIFTY options-chain analytics.
- Option Greeks or implied-volatility analytics.
- Historical options backtesting.
- Paper trading.
- Persistent trade monitoring and alerts.
- Automated order execution.

These are findings from the prior discovery report and must be verified against the current workspace before implementation.

## 3. Initial scope and boundaries

### In scope for the first version

1. NIFTY and BANKNIFTY as the initial underlying indices.
2. Long call and long put strategies only.
3. Historical market-data collection and quality validation.
4. A strategy library containing explicitly specified, reproducible rules.
5. Historical backtesting over approximately one to two years where suitable historical data is available.
6. Evaluation on data not used to design or tune the strategy.
7. Paper trading using current market data.
8. Dashboard-based setup explanations and exit alerts.
9. Trade and signal journaling.
10. Claude AI to explain and critique structured, code-computed results.

### Out of scope for the first version

- Live order placement or autonomous execution.
- Short-option selling and strategies with unlimited or complex margin exposure.
- Claims of guaranteed profit or consistently accurate buy/sell predictions.
- Treating Claude's natural-language response as the source of truth for prices, position sizes, or risk calculations.
- Cryptocurrency implementation before the initial index-options workflow has been validated.

### Future scope

After the initial workflow is reliable, the architecture may be extended to Bitcoin and other cryptocurrencies. Cryptocurrency markets have different market hours, venues, instruments, liquidity patterns, fees, and risk characteristics; they should have their own data adapters and validation rather than reusing NIFTY/BANKNIFTY assumptions.

## 4. Intended user workflow

1. The application ingests historical/current market data for NIFTY and BANKNIFTY and their relevant option contracts.
2. It validates timestamps, missing values, duplicate records, stale quotes, contract identifiers, expiry dates, and data completeness.
3. A strategy engine computes indicators and evaluates predefined entry/exit rules.
4. A risk engine checks whether a candidate setup satisfies configured risk constraints.
5. Claude receives a compact, structured representation of the candidate setup and explains the rationale, risks, assumptions, and invalidation conditions.
6. The application validates the AI output and displays the result on the dashboard.
7. During paper trading, a monitoring process checks the defined conditions and records simulated entries and exits.
8. The journal stores the strategy version, data references, signal, risk decision, simulated fills, costs, and outcome.
9. Evaluation reports compare strategies using consistent metrics and realistic assumptions.

Claude must not invent market prices or override values computed by deterministic application code. If data is stale, missing, inconsistent, or insufficient, the system should say that no valid setup can be generated.

## 5. Historical backtesting requirements

The goal is to examine approximately one to two years of historical data and determine how a precisely specified strategy would have behaved. Historical coverage depends on the chosen data source, contract availability, and data licence; do not assume all required historical option data is freely available.

A backtest must:

- Use timestamped historical data with known provenance.
- Use the data actually available at each simulated decision time.
- Avoid look-ahead bias and survivorship/selection bias where relevant.
- Define the exact time when a signal is generated and the earliest permissible simulated fill.
- Model brokerage, exchange charges, taxes, slippage, bid/ask spread, and other applicable costs as accurately as possible.
- Handle expiry, contract selection, lot-size changes, market holidays, missing candles, and trading-session boundaries.
- Define stop-loss, target, time-based exit, and strategy-invalidation rules before evaluation.
- Document assumptions for stop-loss gaps, limit-order fills, and candles that touch both stop and target within the same bar.
- Separate development/tuning data from validation data, preferably with walk-forward evaluation.
- Include a baseline comparison and report results by strategy, instrument, expiry type, and market regime when the data supports it.
- Preserve failed and rejected setups, not just successful trades.

At minimum, reports should include:

- Number of trades.
- Win rate.
- Gross and net profit/loss.
- Average win and average loss.
- Expectancy per trade.
- Profit factor.
- Maximum drawdown.
- Average and distribution of risk/reward outcomes.
- Costs and slippage.
- Exposure and time in market.
- Results by month and market regime.
- A clear description of data coverage and limitations.

Do not tune a strategy repeatedly on the final validation period. A profitable historical result does not guarantee future performance.

### Historical-data limitation

Underlying index candles alone are not enough to accurately backtest buying options. Option premiums are affected by time to expiry, implied volatility, volatility changes, liquidity, bid/ask spread, and Greeks. For credible option-buying backtests, use historical option-contract prices or an appropriate licensed dataset. Record live option-chain snapshots going forward if permitted by the data provider. If suitable historical options data is unavailable, clearly label any underlying-only study as a proxy, not an options profitability backtest.

## 6. Strategy library

The user has limited technical-analysis knowledge. Strategies must therefore be explicit, visualised where useful, and explained in accessible language.

Potential candidates to investigate—not assumed to be profitable—include:

- Trend-following rules using moving averages.
- Breakout rules based on prior highs/lows and volume confirmation.
- Candlestick-pattern rules with a precise mathematical definition and confirmation conditions.
- VWAP-based intraday rules, if reliable intraday data is available.
- Volatility- or ATR-based filters and exits.
- Rules combining a market-regime filter with a specific entry trigger.

Do not implement a large catalogue at once. Begin with two or three simple, falsifiable candidate strategies and evaluate them consistently.

Every strategy specification must define:

- Strategy name and version.
- Instruments and trading timeframe.
- Required input data and indicators.
- Market conditions in which it is allowed to trade.
- Exact entry trigger.
- Option-contract selection rule (expiry, strike, delta or other rule, liquidity/spread limits).
- Stop-loss and target rules.
- Time-based exit and end-of-session handling.
- Position-sizing and maximum-risk rules.
- Conditions that invalidate the setup.
- Assumptions, known failure modes, and test cases.

A single large bullish candle must not automatically trigger a buy. The strategy should define what qualifies as a meaningful candle, how it is confirmed, where the entry occurs, and where the setup becomes invalid.

## 7. Risk-management requirements

Risk controls are deterministic application logic, not suggestions that Claude can override.

Before a setup is shown as eligible, calculate and validate:

- Maximum planned loss per trade.
- Maximum cumulative loss per day.
- Maximum concurrent paper positions.
- Maximum quantity/lots allowed.
- Minimum risk/reward threshold.
- Contract liquidity and bid/ask spread limits.
- Stop-loss and target validity.
- Available capital and option-premium exposure.
- Data freshness and market-session status.

Reject a setup if a required value is missing or a hard limit is breached. Record the rejection reason.

Option buyers can lose the full premium paid. Stops can also fill worse than expected during fast markets or gaps; do not present stop-loss levels as guaranteed maximum realised losses.

Initial risk limits should be configurable and must be agreed before paper trading. Do not invent the user's capital or acceptable loss limits.

## 8. Claude AI integration

Claude is an explanation and analysis layer, not the market-data source, backtesting engine, or risk authority.

The application should provide Claude with structured, validated features and a candidate setup. Claude should return a constrained response such as:

- Setup summary.
- Bullish/bearish/neutral context.
- Trigger conditions that were met.
- Evidence and indicators supporting the setup.
- Main risks and contradictory evidence.
- Entry, stop, and targets copied from validated application results.
- Invalidation and exit conditions.
- Missing data or uncertainty.
- A plain-language explanation suitable for a beginner.

Use schema-constrained outputs and validate them again in application code. Log the model identifier, prompt version, relevant inputs, output, timestamp, and usage/cost metadata, while protecting secrets and sensitive account data.

Claude must not have a direct tool for placing orders in the initial versions. A malformed, refused, inconsistent, or incomplete response must fail closed; the underlying validated setup can be shown without an AI explanation or be withheld according to the application's safety policy.

## 9. Dashboard and monitoring

Extend the existing React dashboard rather than replacing it without evidence that replacement is necessary.

Provide a setup card containing:

- Underlying: NIFTY or BANKNIFTY.
- Current market timestamp and data freshness.
- Strategy name/version and timeframe.
- Selected option contract, expiry, strike, and call/put.
- Current premium and spread, when available.
- Setup status: waiting, candidate, rejected, paper position open, target reached, stop reached, invalidated, or exited.
- Entry condition and simulated entry.
- Stop-loss, target levels, planned risk and reward.
- Explanation of why the setup exists.
- Reasons to avoid the trade.
- Clear warnings about missing/stale data.

During paper trading, monitor the same predeclared exit conditions used by the strategy and record each transition. Do not depend on Claude repeatedly generating messages to detect stop-loss or target events.

## 10. Proposed technical architecture

Retain the existing React/Vite and Python/PostgreSQL foundations where practical. Before adding modules, inspect the actual repository and choose one canonical location for each responsibility.

Suggested logical components:

- **Market-data adapter:** authorised data ingestion and instrument metadata.
- **Historical data store:** candles, option-contract prices and timestamped option-chain snapshots.
- **Feature engine:** indicators, candle features, volatility, liquidity and options metrics.
- **Strategy engine:** deterministic, versioned rules.
- **Backtesting engine:** simulated event timeline, fills, fees and performance metrics.
- **Risk engine:** hard constraints and rejection reasons.
- **Claude service:** structured explanation and critique.
- **Paper-trading/monitoring worker:** simulated positions and exit conditions.
- **Journal and reporting:** immutable signals, decisions, simulated fills and outcomes.
- **React dashboard:** understandable strategy results, charts, paper positions and alerts.

The initial environment is the user's local computer. Make it possible to run tests and historical backtests offline using stored sample datasets. Document how to start the API, frontend, database and monitoring worker. The system must detect disconnections and stale data; it must not claim to monitor trades while its worker is stopped.

## 11. Implementation phases and gates

### Phase 0 — Stabilise the existing repository

Inspect Git state and user changes, establish a test/build baseline, consolidate duplicate code paths carefully, improve API error handling, require cron authentication, configure safe CORS, pin dependencies, and add CI.

**Gate:** Existing features still work; tests and frontend build pass; sensitive data is protected; no regression is knowingly hidden.

### Phase 1 — Market-data foundation

Implement authorised Kite authentication, secure server-side token handling, instrument synchronisation, historical candle ingestion, timestamps, data-quality checks, rate limits and local storage.

**Gate:** Repeated ingestion produces consistent data; stale/missing data is detected; credentials never appear in browser code or logs.

### Phase 2 — Journal and domain models

Create typed models and database migrations for strategy versions, data snapshots, signals, candidate setups, risk decisions, paper trades, fills, alerts and outcomes.

**Gate:** Every decision can be traced to its strategy version and input data.

### Phase 3 — Options analytics and history

Support NIFTY and BANKNIFTY option contract selection, expiry handling, chain snapshots, liquidity checks, implied volatility and Greeks. Research data licensing and historical option-price availability before selecting the backtest dataset.

**Gate:** Contract selection and calculations are tested against reference cases; snapshot coverage and missing periods are visible.

### Phase 4 — Backtesting

Implement event-driven or otherwise carefully validated simulation with realistic execution assumptions, Indian trading costs, slippage and out-of-sample evaluation.

**Gate:** No-look-ahead tests pass; reports are reproducible; all metrics disclose their assumptions and data coverage.

### Phase 5 — Candidate strategies and risk engine

Start with two or three precisely defined strategies. Generate and validate candidate option-buying setups. Keep strategy parameters and risk limits versioned.

**Gate:** Each setup is reproducible; invalid setups are rejected with explicit reasons; risk rules are thoroughly tested.

### Phase 6 — Claude explanations

Integrate Claude using constrained inputs and outputs. Require code-level validation of every numeric trading value and record AI provenance.

**Gate:** Claude cannot override deterministic values; malformed output fails closed; results are auditable.

### Phase 7 — Paper trading and dashboard alerts

Monitor current data, simulate positions, update the dashboard when entry/exit conditions occur, and recover safely after process restarts.

**Gate:** Run a defined paper-trading evaluation period, including at least one full trading week, with no unresolved critical data, risk or reconciliation failures. Review performance rather than assuming it is profitable.

### Phase 8 — Separate live-trading review

Do not activate live order placement automatically at the end of Phase 7. Require an explicit decision, validated paper results, a security review, current broker/exchange compliance checks, appropriate infrastructure, kill-switch tests and an order-reconciliation plan.

**Gate:** Written approval of all requirements before any live execution implementation is enabled.

### Phase 9 — Cryptocurrency expansion

Only after the index-options workflow has been evaluated, introduce a separate cryptocurrency market-data adapter, instrument model, trading calendar, fees and strategy-validation suite.

**Gate:** Cryptocurrency strategies are independently backtested and validated; index-options results are not treated as evidence of crypto performance.

## 12. Open decisions that must not be guessed

Before the relevant phase, ask the user to decide or explicitly document:

- Whether historical options data will come from a licensed vendor or be collected prospectively.
- The historical coverage actually available for each strategy.
- The initial trading timeframe and expiry/contract-selection rules.
- Maximum planned loss per paper trade and per day.
- Maximum paper positions and minimum risk/reward threshold.
- The evaluation period and criteria for accepting or rejecting a strategy.
- The exact local runtime and database setup.

Do not ask for API secrets in chat. Do not invent these values.

## 13. Instructions for the coding agent

Work incrementally in the existing repository.

1. Read the existing project-discovery report and verify its findings against the current workspace.
2. Start with Phase 0 only.
3. Produce a plan before making risky or broad changes.
4. Make small, reviewable changes with tests.
5. Run the relevant tests and build after each phase.
6. Update documentation and report exact files changed, tests run, outcomes, assumptions, and remaining risks.
7. Never claim a strategy is profitable without appropriate evidence.
8. Never place live trades or enable live order execution during these phases without a separate explicit approval and completed compliance gate.

**Product principle:** Data and deterministic code establish what happened and what rules permit. Claude explains the candidate setup. Backtesting and paper trading provide evidence. The user remains in control.