from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from api.payload_adapter import build_nexus_payload
from api.schema_validation import validate_nexus_payload

RUNS_DIR = Path(".runs")
LATEST_RUN_FILE = RUNS_DIR / "latest_run.txt"


def _resolve_run_log(run_id: str) -> Path:
    if run_id == "latest" and LATEST_RUN_FILE.exists():
        latest = LATEST_RUN_FILE.read_text().strip()
        if latest:
            return RUNS_DIR / f"{latest}.events.jsonl"
    return RUNS_DIR / f"{run_id}.events.jsonl"


def export_run_bundle(*, run_id: str, out_dir: Path, seed: int | None = None) -> dict[str, Any]:
    """Export an immutable replay bundle for the web UI.

    Bundle contains:
    - events.jsonl (raw FlowEvent log)
    - payload.json (adapter output; schema validated)
    - manifest.json (metadata)
    """
    if seed is not None:
        random.seed(seed)

    log_path = _resolve_run_log(run_id)
    if not log_path.exists():
        raise FileNotFoundError(f"Run log not found: {log_path}")

    payload, events = build_nexus_payload(log_path)
    validate_nexus_payload(payload)

    resolved_run_id = log_path.stem.replace(".events", "")
    bundle_dir = out_dir / resolved_run_id
    bundle_dir.mkdir(parents=True, exist_ok=True)

    (bundle_dir / "events.jsonl").write_text(log_path.read_text())
    (bundle_dir / "payload.json").write_text(json.dumps(payload, indent=2, sort_keys=True))

    manifest = {
        "kind": "nexus-replay-bundle",
        "version": 1,
        "run_id": resolved_run_id,
        "source_log": str(log_path),
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "seed": seed,
        "counts": {
            "events": len(events),
            "topology_nodes": len((payload.get("topology") or {}).get("nodes") or []),
            "traces": len(payload.get("traces") or []),
            "message_log": len(payload.get("message_log") or []),
        },
    }
    (bundle_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a replay bundle for a run.")
    parser.add_argument("--run-id", type=str, default="latest", help="Run id or 'latest'")
    parser.add_argument(
        "--out",
        type=str,
        default=str(RUNS_DIR / "bundles"),
        help="Output directory for bundles (each run gets its own subfolder).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional deterministic seed (used by future backtest drivers).",
    )
    args = parser.parse_args()

    out_dir = Path(args.out)
    manifest = export_run_bundle(run_id=args.run_id, out_dir=out_dir, seed=args.seed)
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
