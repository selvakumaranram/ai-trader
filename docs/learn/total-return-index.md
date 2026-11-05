# Price index vs total return index (TRI)

**In one line:** a price index only follows share prices; a total return index also adds back the dividends the
companies paid, as if you reinvested them.

## Why it matters
When you buy a stock or an index fund, you earn two things:
1. **Price change:** the share is worth more (or less) later.
2. **Dividends:** cash the company pays you along the way.

The NIFTY 50 you see quoted on TV is a **price index**. It ignores dividends. The **NIFTY 50 TRI** is the same 50
stocks, but every dividend is reinvested back into the index on the day it is paid.

An index fund that tracks the NIFTY 50 receives those dividends, so its real return is close to the TRI, not the
price index. If you compare your strategy against the price index, you make the index look worse than what you could
have earned by simply buying an index fund.

## A rough example
Large Indian companies have together paid dividends of very roughly 1–1.5% of their price per year. Over 10 years,
reinvesting that adds roughly 13–16% on top of the price-index return (1.013¹⁰ ≈ 1.14, 1.015¹⁰ ≈ 1.16). The exact
figures come from NSE's published TRI series, which Phase 1 will load.

## Indian example
**ITC** has long paid a large dividend. Judged on its share price alone, ITC can look like a weak performer in some
years. Its total return (price plus dividends reinvested) tells a better story. The same is true for the NIFTY 50
index as a whole, only smaller.

## In QuantDesk
The current backtests compare against the NIFTY 50 **price** index. From Phase 3 on, every result is compared
against the **Nifty 50 TRI** (and the **Nifty Midcap 150 TRI** for mid-cap strategies), after costs. That is the fair
bar: what you would have earned by doing nothing clever at all.
