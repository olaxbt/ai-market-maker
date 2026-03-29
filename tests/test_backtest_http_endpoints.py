"""HTTP helpers for backtest equity/trades series."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.backtest_routes import _downsample_rows
from api.flow_stream_server import app


def test_downsample_rows_inclusive_ends():
    rows = [{"step": i} for i in range(100)]
    out = _downsample_rows(rows, 10)
    assert len(out) == 10
    assert out[0]["step"] == 0
    assert out[-1]["step"] == 99


def test_downsample_small_noop():
    rows = [{"step": i} for i in range(5)]
    assert _downsample_rows(rows, 10) == rows


@pytest.fixture
def client():
    return TestClient(app)


def test_get_equity_and_trades(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, client: TestClient):
    monkeypatch.setattr("api.backtest_routes.BACKTESTS_DIR", tmp_path)
    rid = "bt-fixture-1"
    job = tmp_path / rid
    job.mkdir(parents=True)
    equity_rows = [
        {
            "step": i,
            "ts_ms": 1000 * i,
            "close": 100.0 + i,
            "equity": 10_000.0 + i * 10,
            "vetoed": False,
        }
        for i in range(20)
    ]
    (job / "equity.jsonl").write_text(
        "\n".join(json.dumps(r) for r in equity_rows), encoding="utf-8"
    )
    trade_rows = [{"step": 1, "side": "buy", "qty": 0.01}]
    (job / "trades.jsonl").write_text(json.dumps(trade_rows[0]) + "\n", encoding="utf-8")

    r = client.get(f"/backtests/{rid}/equity?max_points=500")
    assert r.status_code == 200
    body = r.json()
    assert body["run_id"] == rid
    assert body["count"] == 20
    assert len(body["points"]) == 20

    r2 = client.get(f"/backtests/{rid}/trades?limit=100")
    assert r2.status_code == 200
    t = r2.json()
    assert t["total"] == 1
    assert t["trades"][0]["side"] == "buy"


def test_get_equity_404(client: TestClient):
    r = client.get("/backtests/does-not-exist-zzz/equity")
    assert r.status_code == 404
