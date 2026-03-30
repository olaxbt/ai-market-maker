"""Integration: synthetic FlowEvent JSONL → NexusPayload → schema validation."""

import json
from pathlib import Path

import pytest

from api.payload_adapter import build_nexus_payload
from api.schema_validation import validate_nexus_payload

pytestmark = pytest.mark.slow


def test_build_nexus_payload_from_minimal_events_jsonl(tmp_path: Path):
    log_path = tmp_path / "integration-run.events.jsonl"
    lines = [
        {
            "kind": "node_start",
            "ts": "2026-03-28T12:00:00Z",
            "payload": {"node": "market_scan", "ticker": "ETH/USDT"},
        },
        {
            "kind": "reasoning",
            "ts": "2026-03-28T12:00:01Z",
            "payload": {
                "node": "signal_arbitrator",
                "thought": "Synthesize",
                "decision": {"action": "hold", "params": {"size": 0}},
                "extra": {"tool_name": "nexus.fetch_market_depth"},
            },
        },
        {
            "kind": "risk_guard",
            "ts": "2026-03-28T12:00:02Z",
            "payload": {
                "status": "APPROVED",
                "risk_score": 0.1,
                "reasoning": {"thought": "Within limits"},
            },
        },
        {
            "kind": "execution",
            "ts": "2026-03-28T12:00:03Z",
            "payload": {"status": "skipped", "message": "no order"},
        },
    ]
    log_path.write_text("\n".join(json.dumps(row) for row in lines) + "\n")

    payload, events = build_nexus_payload(log_path)
    assert len(events) == 4
    validate_nexus_payload(payload)
    assert payload["metadata"]["ticker"] == "ETH/USDT"
    assert payload["metadata"]["run_id"] == "integration-run"
