"""Small durable run ledger for evaluation.

Raw `.runs/<run_id>.events.jsonl` logs are valuable but can be large. This module writes a tiny
append-only index under `.runs/index.jsonl` so you can evaluate outcomes over time even with retention.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from config.app_settings import load_app_settings
from schemas.state import HedgeFundState


def _prune_index_file(idx: Path, *, keep_last: int, max_bytes: int) -> None:
    try:
        if not idx.exists():
            return
        st = idx.stat()
        if st.st_size <= max_bytes and st.st_size <= max(1, max_bytes):
            return
        # Keep only the last N lines. This is fast enough for our intended size caps.
        lines = idx.read_text(encoding="utf-8").splitlines()
        if keep_last > 0 and len(lines) > keep_last:
            lines = lines[-keep_last:]
        out = "\n".join(lines).rstrip() + "\n" if lines else ""
        # If still too big (single huge lines), hard trim by bytes.
        if len(out.encode("utf-8")) > max_bytes:
            b = out.encode("utf-8")[-max_bytes:]
            # ensure valid utf-8 by dropping leading partials
            out = b.decode("utf-8", errors="ignore")
            if out and not out.endswith("\n"):
                out += "\n"
        idx.write_text(out, encoding="utf-8")
    except OSError:
        return


def append_run_index(
    *,
    run_id: str,
    state: HedgeFundState,
    events_path: Path | None = None,
    runs_dir: Path | None = None,
) -> None:
    base = runs_dir or Path(".runs")
    base.mkdir(parents=True, exist_ok=True)
    idx = base / "index.jsonl"
    rec: dict[str, Any] = {
        "ts": int(time.time()),
        "run_id": run_id,
        "ticker": state.get("ticker"),
        "run_mode": state.get("run_mode"),
        "is_vetoed": state.get("is_vetoed"),
        "veto_reason": state.get("veto_reason"),
        "risk_status": (state.get("risk_report") or {}).get("status"),
        "risk_score": (state.get("risk_guard") or {}).get("risk_score"),
        "proposal_status": (state.get("proposal") or {}).get("status"),
        "execution_status": (state.get("execution_result") or {}).get("status"),
        "trade_intent": state.get("trade_intent"),
    }
    if events_path is not None:
        rec["events_path"] = str(events_path)
    idx.write_text("", encoding="utf-8") if not idx.exists() else None
    with idx.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, default=str) + "\n")

    # Prune after append so the latest run is always retained.
    try:
        s = load_app_settings()
        keep_last = int(s.runs.index_keep_last)
        max_mb = int(s.runs.index_max_mb)
        _prune_index_file(idx, keep_last=keep_last, max_bytes=max(1, max_mb) * 1024 * 1024)
    except Exception:
        # Never fail the run due to index housekeeping.
        return


__all__ = ["append_run_index"]
