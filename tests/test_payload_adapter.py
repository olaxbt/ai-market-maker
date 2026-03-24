"""Tests for FlowEvent -> NexusPayload adapter."""

import json

from api.payload_adapter import build_nexus_payload
from api.schema_validation import validate_nexus_payload


def test_build_nexus_payload_from_event_log(tmp_path):
    log_path = tmp_path / "run-demo.events.jsonl"
    rows = [
        {
            "kind": "node_start",
            "ts": "2026-03-23T00:00:00Z",
            "run_id": "run-demo",
            "payload": {"node": "market_scan", "ticker": "BTC/USDT", "extra": {}},
        },
        {
            "kind": "reasoning",
            "ts": "2026-03-23T00:00:01Z",
            "run_id": "run-demo",
            "payload": {
                "agent": "market_scan",
                "role": "agent",
                "thought": "scan complete",
                "decision": {"symbols": 3},
                "extra": {},
            },
        },
        {
            "kind": "execution",
            "ts": "2026-03-23T00:00:02Z",
            "run_id": "run-demo",
            "payload": {"status": "executed", "message": "done", "orders": [], "extra": {}},
        },
    ]
    log_path.write_text("".join(json.dumps(r) + "\n" for r in rows))

    payload, events = build_nexus_payload(log_path)
    assert len(events) == 3
    assert payload["metadata"]["run_id"] == "run-demo"
    assert payload["metadata"]["ticker"] == "BTC/USDT"
    assert payload["metadata"]["status"] == "COMPLETED"
    assert payload["traces"]
    validate_nexus_payload(payload)
