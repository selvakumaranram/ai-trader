import io
import json
from email.message import Message
from types import SimpleNamespace

import pytest

import http_utils


def _headers(**values):
    message = Message()
    for name, value in values.items():
        message[name.replace("_", "-")] = value
    return message


def _request(body: bytes, content_length=None):
    headers = _headers(**({"Content_Length": content_length} if content_length is not None else {}))
    return SimpleNamespace(headers=headers, rfile=io.BytesIO(body))


def test_device_id_valid():
    assert http_utils.device_id_from_headers(_headers(X_Device_Id="abc-123")) == "abc-123"


@pytest.mark.parametrize("value", ["", "has space", "x" * 65, "semi;colon"])
def test_device_id_rejected(value):
    with pytest.raises(http_utils.HttpError) as info:
        http_utils.device_id_from_headers(_headers(X_Device_Id=value))
    assert info.value.status == 400


def test_device_id_missing():
    with pytest.raises(http_utils.HttpError) as info:
        http_utils.device_id_from_headers(_headers())
    assert info.value.status == 400


def test_read_json_object_valid():
    body = json.dumps({"symbol": "INFY.NS"}).encode()
    assert http_utils.read_json_object(_request(body, str(len(body)))) == {"symbol": "INFY.NS"}


def test_read_json_object_empty_body_is_empty_object():
    assert http_utils.read_json_object(_request(b"", None)) == {}


@pytest.mark.parametrize("body", [b"[1, 2]", b"not json", b'"text"'])
def test_read_json_object_rejects_non_objects(body):
    with pytest.raises(http_utils.HttpError) as info:
        http_utils.read_json_object(_request(body, str(len(body))))
    assert info.value.status == 400


@pytest.mark.parametrize("length", ["abc", "-5"])
def test_read_json_object_rejects_bad_content_length(length):
    with pytest.raises(http_utils.HttpError) as info:
        http_utils.read_json_object(_request(b"{}", length))
    assert info.value.status == 400


def test_read_json_object_rejects_oversized_without_reading():
    request = _request(b"{}", str(http_utils.MAX_BODY_BYTES + 1))
    with pytest.raises(http_utils.HttpError) as info:
        http_utils.read_json_object(request)
    assert info.value.status == 413
    assert request.rfile.tell() == 0


def test_allowed_origin_none_when_unconfigured(monkeypatch):
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    assert http_utils.allowed_origin("https://evil.example") is None


def test_allowed_origin_echoes_only_listed_origins(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://a.example, https://b.example")
    assert http_utils.allowed_origin("https://b.example") == "https://b.example"
    assert http_utils.allowed_origin("https://evil.example") is None
    assert http_utils.allowed_origin(None) is None


def test_internal_error_hides_details_but_logs_them(capsys):
    try:
        raise RuntimeError("password=hunter2 in connection string")
    except RuntimeError as exc:
        payload = http_utils.internal_error(exc)

    assert payload == {"error": "Internal server error"}
    assert "hunter2" in capsys.readouterr().err


def test_bearer_token_matches():
    assert http_utils.bearer_token_matches(_headers(Authorization="Bearer s3cret"), "s3cret")
    assert not http_utils.bearer_token_matches(_headers(Authorization="Bearer wrong"), "s3cret")
    assert not http_utils.bearer_token_matches(_headers(), "s3cret")


def test_read_json_object_rejects_deeply_nested_json():
    body = b"[" * 32000 + b"]" * 32000  # under MAX_BODY_BYTES; overflows the decoder on 3.12 and 3.14
    with pytest.raises(http_utils.HttpError) as info:
        http_utils.read_json_object(_request(body, str(len(body))))
    assert info.value.status == 400
