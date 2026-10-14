import pytest

from api_harness import call, load_api_module

cron = load_api_module("cron/momentum_screen.py", "api_cron_momentum_screen")


@pytest.fixture
def ran(monkeypatch):
    calls = []
    monkeypatch.setattr(cron, "run_screen", lambda: calls.append(1) or {"symbols_scored": 1})
    return calls


def test_refuses_when_secret_not_configured(monkeypatch, ran):
    monkeypatch.delenv("CRON_SECRET", raising=False)
    response = call(cron.handler, "GET", "/api/cron/momentum_screen")
    assert response.status == 503
    assert ran == []


def test_rejects_missing_token(monkeypatch, ran):
    monkeypatch.setenv("CRON_SECRET", "s3cret")
    assert call(cron.handler, "GET", "/api/cron/momentum_screen").status == 401
    assert ran == []


def test_rejects_wrong_token(monkeypatch, ran):
    monkeypatch.setenv("CRON_SECRET", "s3cret")
    response = call(cron.handler, "GET", "/api/cron/momentum_screen", {"Authorization": "Bearer nope"})
    assert response.status == 401
    assert ran == []


def test_runs_with_correct_token(monkeypatch, ran):
    monkeypatch.setenv("CRON_SECRET", "s3cret")
    response = call(cron.handler, "GET", "/api/cron/momentum_screen", {"Authorization": "Bearer s3cret"})
    assert response.status == 200
    assert response.json() == {"symbols_scored": 1}
    assert ran == [1]


def test_screen_failure_reports_message_without_traceback(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "s3cret")

    def _fail():
        raise RuntimeError("Cannot screen without the Nifty 200 universe: blocked")

    monkeypatch.setattr(cron, "run_screen", _fail)
    response = call(cron.handler, "GET", "/api/cron/momentum_screen", {"Authorization": "Bearer s3cret"})
    assert response.status == 500
    assert "Nifty 200" in response.json()["error"]
    assert b"Traceback" not in response.body
