import datetime
import json

import pytest

from api_harness import FakeConnection, call, load_api_module

dashboard = load_api_module("dashboard.py", "api_dashboard")
search = load_api_module("search.py", "api_search")
holdings = load_api_module("holdings.py", "api_holdings")
watchlist = load_api_module("watchlist.py", "api_watchlist")
momentum = load_api_module("momentum.py", "api_momentum")
backtest_api = load_api_module("backtest.py", "api_backtest")

DEVICE = {"X-Device-Id": "device-1"}


def _rising(n=60):
    return [100.0 + i * 0.5 for i in range(n)]


@pytest.fixture(autouse=True)
def _no_cors_config(monkeypatch):
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)


def _boom(*args, **kwargs):
    raise Exception("connection to secret-host.internal failed")


def _assert_generic_500(response):
    assert response.status == 500
    assert response.json() == {"error": "Internal server error"}
    assert b"Traceback" not in response.body
    assert b"secret-host" not in response.body


# --- error hygiene -----------------------------------------------------------

def test_dashboard_unexpected_error_is_generic_and_logged(monkeypatch, capsys):
    monkeypatch.setattr(dashboard, "build_dashboard", _boom)
    _assert_generic_500(call(dashboard.handler, "GET", "/api/dashboard"))
    assert "secret-host" in capsys.readouterr().err


def test_holdings_get_db_failure_is_generic(monkeypatch):
    monkeypatch.setattr(holdings.db, "get_connection", _boom)
    _assert_generic_500(call(holdings.handler, "GET", "/api/holdings", DEVICE))


def test_watchlist_get_db_failure_is_generic(monkeypatch):
    monkeypatch.setattr(watchlist.db, "get_connection", _boom)
    _assert_generic_500(call(watchlist.handler, "GET", "/api/watchlist", DEVICE))


def test_momentum_db_failure_is_generic(monkeypatch):
    monkeypatch.setattr(momentum.db, "get_connection", _boom)
    _assert_generic_500(call(momentum.handler, "GET", "/api/momentum?tab=screener"))


def test_search_unexpected_error_is_generic(monkeypatch):
    monkeypatch.setattr(search, "search_symbol", _boom)
    _assert_generic_500(call(search.handler, "GET", "/api/search?symbol=INFY.NS"))


# --- CORS --------------------------------------------------------------------

def test_no_cors_header_by_default(monkeypatch):
    monkeypatch.setattr(search, "search_symbol", lambda s: {"symbol": s})
    response = call(search.handler, "GET", "/api/search?symbol=X", {"Origin": "https://evil.example"})
    assert response.status == 200
    assert "access-control-allow-origin" not in response.headers


def test_listed_origin_is_echoed(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://app.example")
    monkeypatch.setattr(search, "search_symbol", lambda s: {"symbol": s})
    response = call(search.handler, "GET", "/api/search?symbol=X", {"Origin": "https://app.example"})
    assert response.headers["access-control-allow-origin"] == "https://app.example"


# --- input validation ----------------------------------------------------------

def test_search_requires_symbol():
    assert call(search.handler, "GET", "/api/search").status == 400


def test_momentum_rejects_unknown_tab():
    assert call(momentum.handler, "GET", "/api/momentum?tab=bogus").status == 400


def test_holdings_requires_device_id():
    assert call(holdings.handler, "GET", "/api/holdings").status == 400


def test_holdings_post_oversized_body_is_413():
    huge = b"{" + b" " * (70 * 1024) + b"}"
    assert call(holdings.handler, "POST", "/api/holdings", DEVICE, huge).status == 413


def test_holdings_post_invalid_json_is_400():
    assert call(holdings.handler, "POST", "/api/holdings", DEVICE, b"not json").status == 400


def test_holdings_post_bad_price_is_400():
    body = json.dumps({"symbol": "INFY.NS", "buy_price": "abc", "quantity": 1, "buy_date": "2026-01-02"}).encode()
    response = call(holdings.handler, "POST", "/api/holdings", DEVICE, body)
    assert response.status == 400
    assert "buy_price" in response.json()["error"]


def test_holdings_post_success(monkeypatch):
    monkeypatch.setattr(holdings.prices_source, "fetch_price_history", lambda s, period="6mo": _rising())
    row = {"id": 7, "symbol": "INFY.NS", "buy_price": 1500, "quantity": 2, "buy_date": datetime.date(2026, 1, 2)}
    conn = FakeConnection(on_execute=lambda sql, params: [row])
    monkeypatch.setattr(holdings.db, "get_connection", lambda: conn)

    body = json.dumps({"symbol": "infy.ns", "buy_price": 1500, "quantity": 2, "buy_date": "2026-01-02"}).encode()
    response = call(holdings.handler, "POST", "/api/holdings", DEVICE, body)

    assert response.status == 201
    assert response.json()["id"] == 7
    assert conn.committed and conn.closed


def test_holdings_delete_returns_204_without_body(monkeypatch):
    conn = FakeConnection(on_execute=lambda sql, params: [{"id": 5}])
    monkeypatch.setattr(holdings.db, "get_connection", lambda: conn)
    response = call(holdings.handler, "DELETE", "/api/holdings?id=5", DEVICE)
    assert response.status == 204
    assert response.body == b""


def test_holdings_delete_missing_is_404(monkeypatch):
    monkeypatch.setattr(holdings.db, "get_connection", lambda: FakeConnection(on_execute=lambda s, p: []))
    assert call(holdings.handler, "DELETE", "/api/holdings?id=5", DEVICE).status == 404


# --- backtest ------------------------------------------------------------------

@pytest.mark.parametrize("query", ["short=abc", "short=50&long=20", "short=0&long=5", "long=999"])
def test_backtest_rejects_bad_windows(query):
    response = call(backtest_api.handler, "GET", f"/api/backtest?{query}")
    assert response.status == 400
    assert "Traceback" not in response.text


def test_backtest_rejects_window_longer_than_history(monkeypatch):
    monkeypatch.setattr(backtest_api.prices_source, "fetch_price_history", lambda s, period="1y": _rising(30))
    response = call(backtest_api.handler, "GET", "/api/backtest?symbol=X&short=5&long=50")
    assert response.status == 400


def test_backtest_success(monkeypatch):
    monkeypatch.setattr(backtest_api.prices_source, "fetch_price_history", lambda s, period="1y": _rising(120))
    response = call(backtest_api.handler, "GET", "/api/backtest?symbol=TEST&short=5&long=20")
    assert response.status == 200
    assert "Backtest for TEST" in response.text


import psycopg2.errors


def test_watchlist_duplicate_insert_is_409(monkeypatch):
    monkeypatch.setattr(watchlist.prices_source, "fetch_price_history", lambda s, period="6mo": _rising())

    def on_execute(sql, params):
        if sql.lstrip().upper().startswith("INSERT"):
            raise psycopg2.errors.UniqueViolation("duplicate key value violates unique constraint")
        return []

    conn = FakeConnection(on_execute=on_execute)
    monkeypatch.setattr(watchlist.db, "get_connection", lambda: conn)

    response = call(watchlist.handler, "POST", "/api/watchlist", DEVICE, b'{"symbol": "INFY.NS"}')

    assert response.status == 409
    assert response.json() == {"error": "already in your watchlist"}
    assert conn.rolled_back and conn.closed
