from __future__ import annotations

import os
from typing import Dict, List

from sources import news as news_source
from sources import prices as prices_source

UNIVERSE = [
    {"symbol": "BTC", "yf_symbol": "BTC-USD", "type": "crypto", "keywords": ["bitcoin", "bitcoin etf", "halving", "institutional"]},
    {"symbol": "ETH", "yf_symbol": "ETH-USD", "type": "crypto", "keywords": ["ethereum", "layer 2", "staking", "smart contracts"]},
    {"symbol": "SOL", "yf_symbol": "SOL-USD", "type": "crypto", "keywords": ["solana", "defi", "layer 1", "validators"]},
    {"symbol": "BNB", "yf_symbol": "BNB-USD", "type": "crypto", "keywords": ["binance", "bnb chain", "exchange token"]},
    {"symbol": "XRP", "yf_symbol": "XRP-USD", "type": "crypto", "keywords": ["ripple", "xrp", "cross-border payments"]},
    {"symbol": "NVDA", "yf_symbol": "NVDA", "type": "equity_us", "keywords": ["ai", "chip", "chips", "data center", "semiconductor"]},
    {"symbol": "MSFT", "yf_symbol": "MSFT", "type": "equity_us", "keywords": ["cloud", "enterprise", "ai", "software"]},
    {"symbol": "AAPL", "yf_symbol": "AAPL", "type": "equity_us", "keywords": ["iphone", "apple", "consumer electronics", "macbook"]},
    {"symbol": "GOOGL", "yf_symbol": "GOOGL", "type": "equity_us", "keywords": ["google", "google search", "cloud", "advertising"]},
    {"symbol": "TSLA", "yf_symbol": "TSLA", "type": "equity_us", "keywords": ["tesla", "electric vehicle", "ev", "autonomous driving"]},
    {"symbol": "AMZN", "yf_symbol": "AMZN", "type": "equity_us", "keywords": ["amazon", "ecommerce", "cloud", "logistics"]},
    {"symbol": "META", "yf_symbol": "META", "type": "equity_us", "keywords": ["facebook", "instagram", "social media", "advertising"]},
    {"symbol": "AMD", "yf_symbol": "AMD", "type": "equity_us", "keywords": ["chip", "chips", "semiconductor", "gpu", "processor"]},
    {"symbol": "NFLX", "yf_symbol": "NFLX", "type": "equity_us", "keywords": ["netflix", "streaming", "subscribers", "original series"]},
    {"symbol": "JPM", "yf_symbol": "JPM", "type": "equity_us", "keywords": ["jpmorgan", "bank", "finance", "lending", "wall street"]},
    {"symbol": "V", "yf_symbol": "V", "type": "equity_us", "keywords": ["visa inc", "payments", "credit card", "payment network"]},
    {"symbol": "DIS", "yf_symbol": "DIS", "type": "equity_us", "keywords": ["disney", "streaming", "entertainment", "theme park"]},
    {"symbol": "RELIANCE", "yf_symbol": "RELIANCE.NS", "type": "equity_in", "keywords": ["retail", "energy", "telecom", "consumer"]},
    {"symbol": "INFY", "yf_symbol": "INFY.NS", "type": "equity_in", "keywords": ["infosys", "software", "outsourcing", "digital"]},
    {"symbol": "TCS", "yf_symbol": "TCS.NS", "type": "equity_in", "keywords": ["tata consultancy", "tcs", "cloud", "enterprise"]},
    {"symbol": "HDFC", "yf_symbol": "HDFCBANK.NS", "type": "equity_in", "keywords": ["hdfc", "bank", "finance", "credit", "lending"]},
    {"symbol": "ICICIBANK", "yf_symbol": "ICICIBANK.NS", "type": "equity_in", "keywords": ["icici", "bank", "finance", "credit", "lending"]},
    {"symbol": "WIPRO", "yf_symbol": "WIPRO.NS", "type": "equity_in", "keywords": ["wipro", "software", "outsourcing", "digital"]},
    {"symbol": "ITC", "yf_symbol": "ITC.NS", "type": "equity_in", "keywords": ["fmcg", "consumer goods", "cigarette", "hotel"]},
    {"symbol": "SBIN", "yf_symbol": "SBIN.NS", "type": "equity_in", "keywords": ["sbi", "bank", "psu", "lending"]},
    {"symbol": "BHARTIARTL", "yf_symbol": "BHARTIARTL.NS", "type": "equity_in", "keywords": ["telecom", "airtel", "bharti airtel", "broadband"]},
    {"symbol": "LT", "yf_symbol": "LT.NS", "type": "equity_in", "keywords": ["infrastructure", "construction", "engineering", "capital goods"]},
    {"symbol": "KOTAKBANK", "yf_symbol": "KOTAKBANK.NS", "type": "equity_in", "keywords": ["kotak", "bank", "finance", "credit", "lending"]},
    {"symbol": "AXISBANK", "yf_symbol": "AXISBANK.NS", "type": "equity_in", "keywords": ["axis bank", "bank", "finance", "credit", "lending"]},
    {"symbol": "MARUTI", "yf_symbol": "MARUTI.NS", "type": "equity_in", "keywords": ["automobile", "car", "suzuki", "vehicle"]},
    {"symbol": "SUNPHARMA", "yf_symbol": "SUNPHARMA.NS", "type": "equity_in", "keywords": ["pharma", "healthcare", "drug", "medicine"]},
    {"symbol": "TITAN", "yf_symbol": "TITAN.NS", "type": "equity_in", "keywords": ["jewellery", "watches", "retail", "consumer"]},
    {"symbol": "ASIANPAINT", "yf_symbol": "ASIANPAINT.NS", "type": "equity_in", "keywords": ["paint", "consumer goods", "coatings", "retail"]},
    {"symbol": "BAJFINANCE", "yf_symbol": "BAJFINANCE.NS", "type": "equity_in", "keywords": ["nbfc", "finance", "lending", "consumer credit"]},
    {"symbol": "HCLTECH", "yf_symbol": "HCLTECH.NS", "type": "equity_in", "keywords": ["hcltech", "hcl technologies", "software", "outsourcing"]},
    {"symbol": "ULTRACEMCO", "yf_symbol": "ULTRACEMCO.NS", "type": "equity_in", "keywords": ["cement", "infrastructure", "construction", "building materials"]},
    {"symbol": "NESTLEIND", "yf_symbol": "NESTLEIND.NS", "type": "equity_in", "keywords": ["fmcg", "food", "consumer goods", "nutrition"]},
    {"symbol": "ADANIENT", "yf_symbol": "ADANIENT.NS", "type": "equity_in", "keywords": ["infrastructure", "energy", "ports", "conglomerate"]},
    {"symbol": "ONGC", "yf_symbol": "ONGC.NS", "type": "equity_in", "keywords": ["ongc", "oil", "gas", "energy", "psu"]},
    {"symbol": "NTPC", "yf_symbol": "NTPC.NS", "type": "equity_in", "keywords": ["ntpc", "power", "energy", "psu", "electricity"]},
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


def _momentum_detail(closes: List[float]) -> Dict[str, float]:
    return_10d = (closes[-1] - closes[-11]) / closes[-11]
    sma_50 = sum(closes[-50:]) / 50
    trend_vs_sma50 = (closes[-1] / sma_50) - 1
    return {"return_10d": round(return_10d, 4), "trend_vs_sma50": round(trend_vs_sma50, 4)}


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


def build_asset_payload(asset: Dict[str, object], closes: List[float], headlines: List[Dict[str, str]]) -> Dict[str, object]:
    matched = news_source.match_headlines(headlines, asset["keywords"])
    day_change_pct = round((closes[-1] - closes[-2]) / closes[-2] * 100, 2)

    scores = {}
    momentum_value = None
    sentiment_value = None
    for style in STYLE_WEIGHTS:
        scored = _score_asset(asset, style, closes, matched)
        momentum_value = scored["momentum"]
        sentiment_value = scored["sentiment"]
        scores[style] = {"score": scored["score"], "action": scored["action"]}

    return {
        "symbol": asset["symbol"],
        "type": asset["type"],
        "momentum": momentum_value,
        "momentum_detail": _momentum_detail(closes),
        "sentiment": sentiment_value,
        "day_change_pct": day_change_pct,
        "matched_headlines": matched,
        "scores": scores,
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
