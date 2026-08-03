from __future__ import annotations

from typing import Dict, List

import feedparser
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_analyzer = SentimentIntensityAnalyzer()


def fetch_headlines(feed_urls: List[str]) -> List[Dict[str, str]]:
    headlines: List[Dict[str, str]] = []
    for url in feed_urls:
        try:
            parsed = feedparser.parse(url)
        except Exception:
            continue
        if parsed.bozo and not parsed.entries:
            continue
        for entry in parsed.entries:
            headlines.append({
                "title": entry.get("title", ""),
                "summary": entry.get("summary", ""),
            })

    if not headlines:
        raise RuntimeError(
            f"Failed to fetch any headlines from {len(feed_urls)} feed(s): {feed_urls}"
        )
    return headlines


def match_headlines(headlines: List[Dict[str, str]], keywords: List[str]) -> List[Dict[str, str]]:
    lowered_keywords = [kw.lower() for kw in keywords]
    matched = []
    for headline in headlines:
        text = f"{headline.get('title', '')} {headline.get('summary', '')}".lower()
        if any(kw in text for kw in lowered_keywords):
            matched.append(headline)
    return matched


def score_sentiment(headlines: List[Dict[str, str]]) -> float:
    if not headlines:
        return 0.0
    scores = []
    for headline in headlines:
        text = f"{headline.get('title', '')} {headline.get('summary', '')}"
        scores.append(_analyzer.polarity_scores(text)["compound"])
    return sum(scores) / len(scores)
