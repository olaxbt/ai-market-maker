"""Schema contract tests for nexus payload shape."""

import json
from pathlib import Path

import pytest

from api.schema_validation import validate_nexus_payload


def test_schema_rejects_invalid_message_log_kind():
    bad_payload = {
        "metadata": {"run_id": "r1", "ticker": "BTC/USDT", "status": "RUNNING", "kpis": {}},
        "topology": {
            "nodes": [
                {"id": "n1", "actor": "market_scan", "label": "Market Scan", "status": "ACTIVE"}
            ],
            "edges": [],
        },
        "traces": [],
        "message_log": [
            {
                "seq": 1,
                "ts": "2026-03-24T00:00:00Z",
                "node_id": "n1",
                "actor_id": "market_scan",
                "kind": "invalid_kind",
                "message": "x",
            }
        ],
    }
    with pytest.raises(ValueError, match="schema validation failed"):
        validate_nexus_payload(bad_payload)


def test_checked_in_mock_payload_matches_schema():
    repo_root = Path(__file__).resolve().parents[1]
    fixture_path = repo_root / "web" / "src" / "data" / "mock-traces.json"
    payload = json.loads(fixture_path.read_text())
    validate_nexus_payload(payload)
