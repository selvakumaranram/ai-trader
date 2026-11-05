# Point-in-time data

**In one line:** store every number together with **the date the market could first know it**, so a backtest only
uses what an investor could really have seen on each day.

## Why it matters
A company's quarter ends on one date, but its results are published weeks later. If a backtest uses the results on
the day the quarter ended, it is "seeing the future": it buys stocks before anyone could know the numbers were good.
That makes a strategy look better than it could ever be in real life. This mistake is called **look-ahead bias**
(Phase 3 explains it fully in `backtest-biases.md`).

Numbers can also change later. A company can **restate** an old quarter, and data websites often overwrite the old
number with the new one. A backtest must use the number that was published *at that time*, not today's corrected
version.

## Indian example
**Infosys's** July–September quarter ends on 30 September, but the company announces the results around mid-October.
- A backtest running on **1 October** must not see those results yet. It still only knows the April–June quarter.
- From the **day after the announcement**, the new numbers can be used.

So for every number we keep three dates:

| field | example |
|---|---|
| `period_end` | 2025-09-30 (the quarter the number is about) |
| `published_at` | the date the results were announced to the exchange |
| `retrieved_at` | when QuantDesk downloaded it |

A question like "what did we know on 2025-10-01?" only looks at rows whose `published_at` is **before** that date.

## In QuantDesk
Phase 1 builds this store for fundamentals and shareholding data. Phase 3's backtest asks it "what was known as of
each quarterly rebalance date", and nothing else.
