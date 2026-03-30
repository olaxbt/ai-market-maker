import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.flow_stream_server import app

pytestmark = pytest.mark.slow


def _write_minimal_run(tmp_path: Path, run_id: str = "run-it-1") -> None:
    runs_dir = tmp_path / ".runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    (runs_dir / "latest_run.txt").write_text(run_id)
    log_path = runs_dir / f"{run_id}.events.jsonl"
    log_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "ts": "2026-03-25T00:00:00Z",
                        "kind": "node_start",
                        "payload": {"node": "market_scan", "ticker": "BTC/USDT"},
                    }
                ),
                json.dumps(
                    {
                        "ts": "2026-03-25T00:00:01Z",
                        "kind": "reasoning",
                        "payload": {
                            "agent": "market_scan",
                            "thought": "boot",
                            "decision": {"action": "NOOP", "params": {}},
                        },
                    }
                ),
                json.dumps(
                    {
                        "ts": "2026-03-25T00:00:02Z",
                        "kind": "node_end",
                        "payload": {"node": "market_scan", "summary": "ok"},
                    }
                ),
            ]
        )
        + "\n"
    )


def test_flow_stream_http_payload(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_minimal_run(tmp_path)

    client = TestClient(app)
    res = client.get("/runs/latest/payload")
    assert res.status_code == 200
    payload = res.json()
    assert payload["metadata"]["ticker"] == "BTC/USDT"
    assert "topology" in payload
    assert "traces" in payload
    assert "message_log" in payload


def test_flow_stream_ws_payload_message(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_minimal_run(tmp_path)

    client = TestClient(app)
    with client.websocket_connect("/ws/runs/latest") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "payload"
        assert "payload" in msg
        assert msg["payload"]["metadata"]["ticker"] == "BTC/USDT"
