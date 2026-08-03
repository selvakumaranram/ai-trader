import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from sources import news


class _FakeParsed:
    def __init__(self, entries, bozo=False):
        self.entries = entries
        self.bozo = bozo


def test_fetch_headlines_collects_entries_across_feeds(monkeypatch):
    def fake_parse(url):
        if url == "feed-a":
            return _FakeParsed([{"title": "A rises", "summary": "up"}])
        return _FakeParsed([{"title": "B falls", "summary": "down"}])

    monkeypatch.setattr(news.feedparser, "parse", fake_parse)

    result = news.fetch_headlines(["feed-a", "feed-b"])

    assert len(result) == 2
    assert result[0]["title"] == "A rises"
    assert result[1]["title"] == "B falls"


def test_fetch_headlines_tolerates_partial_feed_failure(monkeypatch):
    def fake_parse(url):
        if url == "feed-a":
            raise ConnectionError("feed-a down")
        return _FakeParsed([{"title": "B falls", "summary": "down"}])

    monkeypatch.setattr(news.feedparser, "parse", fake_parse)

    result = news.fetch_headlines(["feed-a", "feed-b"])

    assert len(result) == 1
    assert result[0]["title"] == "B falls"


def test_fetch_headlines_raises_when_all_feeds_fail(monkeypatch):
    monkeypatch.setattr(news.feedparser, "parse", lambda url: _FakeParsed([], bozo=True))

    with pytest.raises(RuntimeError):
        news.fetch_headlines(["feed-a"])


def test_match_headlines_filters_by_keyword():
    headlines = [
        {"title": "Bitcoin rallies", "summary": "ETF inflows"},
        {"title": "Coffee prices dip", "summary": "harvest season"},
    ]

    matched = news.match_headlines(headlines, ["bitcoin", "etf"])

    assert matched == [headlines[0]]


def test_score_sentiment_returns_zero_for_no_headlines():
    assert news.score_sentiment([]) == 0.0


def test_score_sentiment_is_positive_for_positive_text():
    headlines = [{"title": "Great news, huge rally, best day ever", "summary": ""}]

    assert news.score_sentiment(headlines) > 0


def test_score_sentiment_is_negative_for_negative_text():
    headlines = [{"title": "Terrible crash, massive losses, worst day ever", "summary": ""}]

    assert news.score_sentiment(headlines) < 0
