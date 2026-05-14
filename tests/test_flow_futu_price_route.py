from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import adapters.futu as futu_mod
from adapters.futu import _time_key_to_epoch_ms


def test_time_key_parses_futu_date_string() -> None:
    ms = _time_key_to_epoch_ms("2024-06-15 00:00:00")
    assert ms > 1_000_000_000_000


def test_futu_price_endpoint_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    class StubAdapter:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def get_history_kline(self, **kwargs):
            return [[1704067200000.0, 100.0, 101.0, 99.0, 100.5, 1_000_000.0]]

        def close(self) -> None:
            pass

    monkeypatch.setattr(futu_mod, "FutuAdapter", StubAdapter)

    from api.flow_stream_server import app

    client = TestClient(app)
    r = client.get("/futu/price?symbol=HK.09999&interval=1d&limit=200")
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "flow"
    assert body["symbol"] == "HK.09999"
    assert isinstance(body["bars"], list)
    assert len(body["bars"]) == 1


def test_futu_status_endpoint_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    class StubAdapter:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def healthcheck(self) -> dict[str, object]:
            return {"status": "ok", "opend_connected": True}

        def close(self) -> None:
            pass

    monkeypatch.setattr(futu_mod, "FutuAdapter", StubAdapter)

    from api.flow_stream_server import app

    client = TestClient(app)
    r = client.get("/futu/status")
    assert r.status_code == 200
    body = r.json()
    assert body.get("source") == "flow"
    assert body.get("opend_connected") is True


def test_futu_status_endpoint_returns_body_when_adapter_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BadAdapter:
        def __init__(self, *args, **kwargs) -> None:
            raise RuntimeError("no futu-api")

    monkeypatch.setattr(futu_mod, "FutuAdapter", BadAdapter)

    from api.flow_stream_server import app

    client = TestClient(app)
    r = client.get("/futu/status")
    assert r.status_code == 200
    body = r.json()
    assert body.get("opend_connected") is False
    assert "no futu-api" in str(body.get("detail", ""))


def test_futu_price_endpoint_502_when_adapter_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    class BadAdapter:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def get_history_kline(self, **kwargs):
            raise RuntimeError("OpenD down")

        def close(self) -> None:
            pass

    monkeypatch.setattr(futu_mod, "FutuAdapter", BadAdapter)

    from api.flow_stream_server import app

    client = TestClient(app)
    r = client.get("/futu/price")
    assert r.status_code == 502
    assert "OpenD" in r.json().get("detail", "")
