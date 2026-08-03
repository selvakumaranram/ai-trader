from __future__ import annotations

import math
from typing import List, Tuple

from sources import prices as prices_source


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
    long_sma = sma(prices, long_window)
    cash = 10000.0
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
