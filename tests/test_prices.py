import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from sources import prices


class _FakeSeries:
    def __init__(self, values):
        self._values = values

    def tolist(self):
        return self._values


class _FakeFrame:
    def __init__(self, values):
        self.empty = len(values) == 0
        self._close = _FakeSeries(values)

    def __getitem__(self, key):
        assert key == "Close"
        return self._close


class _FakeFrameNoClose:
    """Frame that raises KeyError when 'Close' column is accessed (schema drift)."""
    def __init__(self):
        self.empty = False

    def __getitem__(self, key):
        raise KeyError(key)


def test_fetch_price_history_returns_close_values(monkeypatch):
    monkeypatch.setattr(prices.yf, "download", lambda *a, **k: _FakeFrame([100.0, 101.5, 99.25]))

    result = prices.fetch_price_history("TEST", period="6mo")

    assert result == [100.0, 101.5, 99.25]


def test_fetch_price_history_raises_on_empty_data(monkeypatch):
    monkeypatch.setattr(prices.yf, "download", lambda *a, **k: _FakeFrame([]))

    with pytest.raises(RuntimeError):
        prices.fetch_price_history("TEST")


def test_fetch_price_history_raises_on_download_exception(monkeypatch):
    def _raise(*a, **k):
        raise ConnectionError("network down")

    monkeypatch.setattr(prices.yf, "download", _raise)

    with pytest.raises(RuntimeError):
        prices.fetch_price_history("TEST")


def test_fetch_price_history_raises_on_missing_close_column(monkeypatch):
    monkeypatch.setattr(prices.yf, "download", lambda *a, **k: _FakeFrameNoClose())

    with pytest.raises(RuntimeError) as exc_info:
        prices.fetch_price_history("TEST")

    assert "Close" in str(exc_info.value)
