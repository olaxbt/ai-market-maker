from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.flow_stream_server import app


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    # Use an isolated prompts file per test run.
    prompts_path = tmp_path / "agent_prompts.json"
    monkeypatch.setenv("AIMM_AGENT_PROMPTS_PATH", str(prompts_path))
    return TestClient(app)


def test_put_creates_row_then_get_roundtrip(client: TestClient, tmp_path: Path) -> None:
    body = {
        "system_prompt": "sys",
        "task_prompt": "task",
        "model": "gpt-4o-mini",
        "temperature": 0.1,
        "max_tokens": 123,
        "tools": [],
        "cot_enabled": True,
    }
    # n13 exists in NODE_REGISTRY (signal_arbitrator)
    r = client.put("/agent-prompts/n13", json=body)
    assert r.status_code == 200
    out = r.json()
    assert out["node_id"] == "n13"
    assert out["system_prompt"] == "sys"

    r2 = client.get("/agent-prompts/n13")
    assert r2.status_code == 200
    out2 = r2.json()
    assert out2["task_prompt"] == "task"

    # File written
    p = Path(tmp_path) / "agent_prompts.json"
    assert p.is_file()
    data = json.loads(p.read_text(encoding="utf-8"))
    assert isinstance(data, list) and len(data) == 1


def test_get_synthetic_prompt_when_node_missing_from_file(client: TestClient) -> None:
    """Topology nodes (e.g. n0) exist in NODE_REGISTRY before a row is written to JSON."""
    r = client.get("/agent-prompts/n0")
    assert r.status_code == 200
    out = r.json()
    assert out["node_id"] == "n0"
    assert out["actor_id"] == "policy_orchestrator"
    assert "system_prompt" in out and "task_prompt" in out
    assert "applies_to_runtime" in out and out["applies_to_runtime"] is False
    assert out.get("mode") == "deterministic"


def test_payload_includes_default_agent_prompts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AIMM_AGENT_PROMPTS_PATH", str(tmp_path / "agent_prompts.json"))
    from api.payload_adapter import NODE_REGISTRY, build_nexus_payload

    payload, _events = build_nexus_payload(tmp_path / "missing.events.jsonl")
    rows = payload.get("agent_prompts") or []
    assert isinstance(rows, list)
    assert len(rows) == len(NODE_REGISTRY)
    # Spot-check required keys
    assert {"node_id", "actor_id", "system_prompt", "task_prompt", "cot_enabled"}.issubset(
        set(rows[0].keys())
    )
