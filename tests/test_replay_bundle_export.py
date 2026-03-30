import json
from pathlib import Path

import pytest

from api.schema_validation import validate_nexus_payload
from backtest.export_run import export_run_bundle

pytestmark = pytest.mark.slow


def test_export_run_bundle_writes_payload_and_manifest(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runs_dir = tmp_path / ".runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    run_id = "run-test-1"
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

    out_dir = tmp_path / "bundles"
    manifest = export_run_bundle(run_id="latest", out_dir=out_dir, seed=123)
    bundle_dir = out_dir / manifest["run_id"]

    payload_path = bundle_dir / "payload.json"
    manifest_path = bundle_dir / "manifest.json"
    events_path = bundle_dir / "events.jsonl"

    assert payload_path.exists()
    assert manifest_path.exists()
    assert events_path.exists()

    payload = json.loads(payload_path.read_text())
    validate_nexus_payload(payload)
