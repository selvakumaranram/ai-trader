from __future__ import annotations

import math
import sys
from typing import List, Tuple


def build_price_series(symbol: str, periods: int = 250) -> List[float]:
    seed = sum(ord(ch) for ch in symbol.lower()) % 97
    prices = [100.0 + seed]
    for index in range(1, periods):
        drift = 0.01 + (index % 7) * 0.002
        noise = math.sin(index / 8.0) * 0.8
        prices.append(prices[-1] * (1 + drift + noise / 100.0))
    return prices


def sma(values: List[float], window: int) -> List[float]:
    result: List[float] = []
    for index in range(len(values)):
        if index < window - 1:
            result.append(float("nan"))
        else:
            window_values = values[index - window + 1:index + 1]
            result.append(sum(window_values) / window)
    return result


def run_backtest(prices: List[float], short_window: int, long_window: int) -> Tuple[float, float, int]:
    short_sma = sma(prices, short_window)
    long_sma = sma(prices, long_window)\n    cash = 10000.0
    shares = 0
    entry_price = prices[0]

    for index in range(1, len(prices)):
        short_value = short_sma[index]
        long_value = long_sma[index]
        if math.isnan(short_value) or math.isnan(long_value):
            continue
        if short_value > long_value and shares == 0:
            shares = cash / prices[index]
            cash = 0.0
        elif short_value < long_value and shares > 0:
            cash = shares * prices[index]
            shares = 0

    if shares > 0:
        cash = shares * prices[-1]

    buy_hold = prices[-1] / prices[0] * 10000.0
    return round(cash, 2), round(buy_hold, 2), len(prices)


def main() -> None:
    symbol = sys.argv[1] if len(sys.argv) > 1 else "RELIANCE.NS"
    short_window = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    long_window = int(sys.argv[3]) if len(sys.argv) > 3 else 50

    prices = build_price_series(symbol, periods=250)
    strategy_value, buy_hold_value, periods = run_backtest(prices, short_window, long_window)

    print(f"Backtest for {symbol} | periods={periods} | short={short_window} | long={long_window}")
    print(f"Strategy final value: Rs {strategy_value:,.2f}")
    print(f"Buy-and-hold value:  Rs {buy_hold_value:,.2f}")
    if strategy_value > buy_hold_value:
        print("Outcome: strategy outperformed buy-and-hold on this synthetic sample.")
    else:
        print("Outcome: strategy underperformed buy-and-hold on this synthetic sample.")


if __name__ == "__main__":
    main()
