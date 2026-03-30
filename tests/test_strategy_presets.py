"""Strategy preset defaults and API list shape."""

import pytest

from strategies.presets import (
    DEFAULT_QUANT_STRATEGY_ID,
    get_preset,
    merge_preset_quick_request,
    quant_trace_meta,
)


def test_default_preset_exists():
    p = get_preset(DEFAULT_QUANT_STRATEGY_ID)
    assert p.interval_sec == 300
    assert p.n_bars >= 20


def test_merge_preset_produces_quick_body():
    m = merge_preset_quick_request(DEFAULT_QUANT_STRATEGY_ID, ticker="ETH/USDT")
    assert m["ticker"] == "ETH/USDT"
    assert "n_bars" in m and "interval_sec" in m


def test_quant_trace_meta_shape():
    meta = quant_trace_meta()
    assert meta["preset_id"] == DEFAULT_QUANT_STRATEGY_ID
    assert "signals" in meta


@pytest.mark.slow
def test_http_strategies_list():
    from fastapi.testclient import TestClient

    from api.flow_stream_server import app

    client = TestClient(app)
    r = client.get("/strategies")
    assert r.status_code == 200
    data = r.json()
    assert "strategies" in data
    assert any(s.get("id") == DEFAULT_QUANT_STRATEGY_ID for s in data["strategies"])
