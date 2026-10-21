import os

import pytest

import dev_server
from api_harness import call


def test_resolve_handler_maps_api_path_to_module_handler():
    handler_cls = dev_server.resolve_handler("/api/search?symbol=INFY.NS")
    assert handler_cls is not None
    assert hasattr(handler_cls, "do_GET")


def test_resolve_handler_supports_nested_cron_route():
    assert dev_server.resolve_handler("/api/cron/momentum_screen") is not None


@pytest.mark.parametrize("path", ["/api/nope", "/api/../db", "/api/", "/index.html", "/api/search/../../db"])
def test_resolve_handler_rejects_unknown_or_unsafe_paths(path):
    assert dev_server.resolve_handler(path) is None


def test_router_returns_404_for_unknown_api():
    response = call(dev_server.DevRouter, "GET", "/api/nope")
    assert response.status == 404
    assert response.json() == {"error": "Not found"}


def test_router_dispatches_to_real_handler():
    # /api/search without a symbol is answered by the real handler (400), no network.
    response = call(dev_server.DevRouter, "GET", "/api/search")
    assert response.status == 400
    assert "symbol" in response.json()["error"]


def test_router_returns_405_for_unsupported_method():
    response = call(dev_server.DevRouter, "DELETE", "/api/search")
    assert response.status == 405


def test_load_env_file_sets_missing_keys_without_overriding(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('# comment\n\nNEW_KEY="quoted value"\nEXISTING=from-file\nNO_EQUALS_LINE\n', encoding="utf-8")
    monkeypatch.delenv("NEW_KEY", raising=False)
    monkeypatch.setenv("EXISTING", "from-shell")

    loaded = dev_server.load_env_file(str(env))

    assert os.environ["NEW_KEY"] == "quoted value"
    assert os.environ["EXISTING"] == "from-shell"
    assert loaded == ["NEW_KEY"]


def test_load_env_file_missing_file_is_noop(tmp_path):
    assert dev_server.load_env_file(str(tmp_path / "absent.env")) == []
