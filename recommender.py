from __future__ import annotations

import math
import os
import textwrap
from typing import Dict, List

UNIVERSE = [
    {"symbol": "BTC", "type": "crypto", "keywords": ["bitcoin", "etf", "halving", "institutional"]},
    {"symbol": "ETH", "type": "crypto", "keywords": ["ethereum", "layer2", "staking", "smart contract"]},
    {"symbol": "NVDA", "type": "equity_us", "keywords": ["ai", "chip", "data center", "semiconductor"]},
    {"symbol": "MSFT", "type": "equity_us", "keywords": ["cloud", "enterprise", "ai", "software"]},
    {"symbol": "RELIANCE", "type": "equity_in", "keywords": ["retail", "energy", "telecom", "consumer"]},
    {"symbol": "INFY", "type": "equity_in", "keywords": ["it", "software", "outsourcing", "digital"]},
    {"symbol": "TCS", "type": "equity_in", "keywords": ["it", "services", "cloud", "enterprise"]},
    {"symbol": "HDFC", "type": "equity_in", "keywords": ["bank", "finance", "credit", "lending"]},
]

RSS_FEEDS = [
    "https://feeds.feedburner.com/cointelegraph",
    "https://feeds.feedburner.com/techcrunch/startups",
    "https://www.moneycontrol.com/rss/marketnews.xml",
]

WEIGHTS = {
    "momentum": 0.65,
    "sentiment": 0.35,
}

STYLE = "short_term"
CAPITAL = 25000
MAX_DEPLOY_PCT = 0.60
MAX_ALLOC_PER_IDEA = 0.20
MIN_TICKET = 500

STYLE_WEIGHTS = {
    "intraday": {"momentum": 0.8, "sentiment": 0.2},
    "short_term": {"momentum": 0.7, "sentiment": 0.3},
    "swing": {"momentum": 0.55, "sentiment": 0.45},
}


def _stable_score(text: str) -> float:
    total = sum(ord(ch) for ch in text.lower())
    return (total % 97) / 96.0


def _estimate_momentum(asset: Dict[str, object], style: str) -> float:
    symbol = str(asset["symbol"]).lower()
    style_mix = STYLE_WEIGHTS[style]
    base = 0.45 + _stable_score(symbol) * 0.35
    keyword_bonus = min(0.15, 0.02 * len(asset["keywords"]))
    style_bonus = style_mix["momentum"] * 0.1
    return min(0.99, max(0.05, base + keyword_bonus + style_bonus))


def _estimate_sentiment(asset: Dict[str, object]) -> float:
    keywords = [word.lower() for word in asset["keywords"]]
    combined = " ".join(keywords)
    score = 0.5 + _stable_score(combined) * 0.25
    if "ai" in combined:
        score += 0.05
    if "bitcoin" in combined or "crypto" in combined:
        score += 0.03
    return min(0.99, max(0.05, score))


def _score_asset(asset: Dict[str, object], style: str) -> Dict[str, object]:
    momentum = _estimate_momentum(asset, style)
    sentiment = _estimate_sentiment(asset)
    score = round((momentum * WEIGHTS["momentum"] + sentiment * WEIGHTS["sentiment"]), 3)
    if style in STYLE_WEIGHTS:
        score = round((momentum * STYLE_WEIGHTS[style]["momentum"] + sentiment * STYLE_WEIGHTS[style]["sentiment"]), 3)

    action = "Research LONG" if score >= 0.55 else "Watchlist"
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
    scored = [_score_asset(asset, STYLE) for asset in UNIVERSE]
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


def write_dashboard(rows: List[Dict[str, object]], path: str = "dashboard.html") -> None:
    items = []
    for row in rows:
        items.append(
            f"<li><strong>{row['symbol']}</strong> — {row['type']} — score {row['score']:.3f} — suggested Rs {int(row['suggested']):,} — {row['action']}</li>"
        )

    html = f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>QuantDesk Research Dashboard</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem; background: #07111f; color: #e7eefc; }}
    .card {{ background: #10233c; border: 1px solid #2f4b72; border-radius: 12px; padding: 1.5rem; max-width: 840px; }}
    ul {{ line-height: 1.7; }}
    .meta {{ color: #89a6c9; margin-bottom: 1rem; }}
  </style>
</head>
<body>
  <div class=\"card\">
    <h1>QuantDesk Research Dashboard</h1>
    <p class=\"meta\">Capital: Rs {CAPITAL:,.0f} • Style: {STYLE} • Feeds: {len(RSS_FEEDS)}</p>
    <ul>
      {''.join(items)}
    </ul>
  </div>
</body>
</html>
"""
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(html)


def main() -> None:
    rows = build_rankings()
    print("QuantDesk — Research & Recommendation")
    print(f"Style: {STYLE} | Capital: Rs {CAPITAL:,.0f} | Max deploy: {MAX_DEPLOY_PCT * 100:.0f}%")
    print(format_table(rows))
    deployed = sum(row["suggested"] for row in rows if row["suggested"] > 0)
    print(f"\nSuggested deployed: Rs {deployed:,.0f} | Cash buffer: Rs {CAPITAL - deployed:,.0f}")

    output_path = os.path.join(os.path.dirname(__file__) or ".", "dashboard.html")
    write_dashboard(rows, output_path)
    print(f"\nDashboard written to {output_path}")


if __name__ == "__main__":
    main()
