from __future__ import annotations

import os
from typing import Dict, List

from sources import news as news_source
from sources import prices as prices_source

UNIVERSE = [
    {"symbol": "BTC", "yf_symbol": "BTC-USD", "type": "crypto", "keywords": ["bitcoin", "etf", "halving", "institutional"]},
    {"symbol": "ETH", "yf_symbol": "ETH-USD", "type": "crypto", "keywords": ["ethereum", "layer2", "staking", "smart contract"]},
    {"symbol": "NVDA", "yf_symbol": "NVDA", "type": "equity_us", "keywords": ["ai", "chip", "data center", "semiconductor"]},
    {"symbol": "MSFT", "yf_symbol": "MSFT", "type": "equity_us", "keywords": ["cloud", "enterprise", "ai", "software"]},
    {"symbol": "RELIANCE", "yf_symbol": "RELIANCE.NS", "type": "equity_in", "keywords": ["retail", "energy", "telecom", "consumer"]},
    {"symbol": "INFY", "yf_symbol": "INFY.NS", "type": "equity_in", "keywords": ["it", "software", "outsourcing", "digital"]},
    {"symbol": "TCS", "yf_symbol": "TCS.NS", "type": "equity_in", "keywords": ["it", "services", "cloud", "enterprise"]},
    {"symbol": "HDFC", "yf_symbol": "HDFCBANK.NS", "type": "equity_in", "keywords": ["bank", "finance", "credit", "lending"]},
]

RSS_FEEDS = [
    "https://feeds.feedburner.com/cointelegraph",
    "https://feeds.feedburner.com/techcrunch/startups",
    "https://www.moneycontrol.com/rss/marketnews.xml",
]

STYLE = "short_term"
CAPITAL = 25000
MAX_DEPLOY_PCT = 0.60
MAX_ALLOC_PER_IDEA = 0.20
MIN_TICKET = 500
SCORE_THRESHOLD = 0.15

STYLE_WEIGHTS = {
    "intraday": {"momentum": 0.8, "sentiment": 0.2},
    "short_term": {"momentum": 0.7, "sentiment": 0.3},
    "swing": {"momentum": 0.55, "sentiment": 0.45},
}


def _compute_momentum(closes: List[float], symbol: str) -> float:
    if len(closes) < 51:
        raise ValueError(f"Need at least 51 closes to compute momentum for {symbol!r}, got {len(closes)}")
    return_10d = (closes[-1] - closes[-11]) / closes[-11]
    sma_50 = sum(closes[-50:]) / 50
    trend = (closes[-1] / sma_50) - 1
    momentum = 0.5 * return_10d + 0.5 * trend
    return max(-1.0, min(1.0, momentum))


def _score_asset(
    asset: Dict[str, object],
    style: str,
    closes: List[float],
    matched_headlines: List[Dict[str, str]],
) -> Dict[str, object]:
    momentum = _compute_momentum(closes, asset["symbol"])
    sentiment = news_source.score_sentiment(matched_headlines)
    style_mix = STYLE_WEIGHTS[style]
    score = round(momentum * style_mix["momentum"] + sentiment * style_mix["sentiment"], 3)

    action = "Research LONG" if score >= SCORE_THRESHOLD else "Watchlist"
    return {
        "symbol": asset["symbol"],
        "type": asset["type"],
        "momentum": round(momentum, 3),
        "sentiment": round(sentiment, 3),
        "score": score,
        "action": action,
    }


def _position_sizing(scores: List[Dict[str, object]]) -> List[Dict[str, object]]:
    positive_scores = [entry["score"] for entry in scores if entry["score"] > 0]
    total_positive = sum(positive_scores) if positive_scores else 1.0
    deployable_capital = CAPITAL * MAX_DEPLOY_PCT
    max_per_idea = CAPITAL * MAX_ALLOC_PER_IDEA

    sized: List[Dict[str, object]] = []
    for entry in scores:
        if entry["score"] <= 0:
            allocation = 0
        else:
            normalized_weight = entry["score"] / total_positive
            raw_allocation = deployable_capital * normalized_weight
            allocation = min(max_per_idea, raw_allocation)
            if allocation < MIN_TICKET:
                allocation = 0
        entry["suggested"] = round(allocation, 0)
        sized.append(entry)
    return sized


def build_rankings() -> List[Dict[str, object]]:
    headlines = news_source.fetch_headlines(RSS_FEEDS)
    scored = []
    for asset in UNIVERSE:
        closes = prices_source.fetch_price_history(asset["yf_symbol"])
        matched = news_source.match_headlines(headlines, asset["keywords"])
        scored.append(_score_asset(asset, STYLE, closes, matched))
    ranked = sorted(scored, key=lambda item: item["score"], reverse=True)
    return _position_sizing(ranked)


def format_table(rows: List[Dict[str, object]]) -> str:
    headers = ["RANK", "ASSET", "TYPE", "SCORE", "SUGGEST", "ACTION"]
    body = [
        f"{headers[0]:<4} {headers[1]:<10} {headers[2]:<12} {headers[3]:<6} {headers[4]:<8} {headers[5]}"
    ]
    for index, row in enumerate(rows, start=1):
        body.append(
            f"{index:<4} {str(row['symbol']):<10} {str(row['type']):<12} {row['score']:<6.3f} Rs {row['suggested']:>7,.0f} {row['action']}"
        )
    return "\n".join(body)


def main() -> None:
    rows = build_rankings()
    print("QuantDesk — Research & Recommendation")
    print(f"Style: {STYLE} | Capital: Rs {CAPITAL:,.0f} | Max deploy: {MAX_DEPLOY_PCT * 100:.0f}%")
    print(format_table(rows))
    deployed = sum(row["suggested"] for row in rows if row["suggested"] > 0)
    print(f"\nSuggested deployed: Rs {deployed:,.0f} | Cash buffer: Rs {CAPITAL - deployed:,.0f}")


if __name__ == "__main__":
    main()
