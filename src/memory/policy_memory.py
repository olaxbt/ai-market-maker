from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable


def _runs_dir() -> Path:
    return Path(os.getenv("AIMM_RUNS_DIR") or ".runs")


def _memory_path() -> Path:
    return _runs_dir() / "policy_memory.jsonl"


@dataclass(frozen=True)
class PolicyDecision:
    """Orchestrator output for this run."""

    decided_at_ms: int
    config_path: str | None
    policy_preset: str | None
    desk_strategy_preset: str | None
    notes: str


class PolicyMemoryStore:
    """Tiny persistent memory (JSONL) to support cross-run adaptivity.

    This is intentionally simple and filesystem-based so it works in community setups
    without requiring Neo4j/vector DB. It can be replaced later.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or _memory_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append_event(self, event: Dict[str, Any]) -> None:
        line = json.dumps(event, sort_keys=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def iter_events(self, *, limit: int | None = None) -> Iterable[Dict[str, Any]]:
        if not self.path.exists():
            return []
        # Read from end if limit requested (simple approach: read all, then slice).
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except Exception:
            return []
        if limit is not None:
            lines = lines[-int(limit) :]
        out: list[Dict[str, Any]] = []
        for ln in lines:
            try:
                obj = json.loads(ln)
            except Exception:
                continue
            if isinstance(obj, dict):
                out.append(obj)
        return out


def decide_policy_from_memory(
    *,
    recent: Iterable[Dict[str, Any]],
    default_config_path: str | None,
) -> PolicyDecision:
    """Heuristic orchestrator: choose preset/config for this run from recent outcomes.

    Goal: be conservative in drawdown trouble; otherwise use signoff baseline.
    """
    now_ms = int(time.time() * 1000)
    evs = list(recent)

    # Count recent risk-triggered vetoes.
    veto_dd = 0
    for e in evs[-10:]:
        if e.get("kind") != "run_end":
            continue
        rg = e.get("risk_guard") or {}
        if isinstance(rg, dict):
            extra = (
                (rg.get("reasoning") or {}).get("extra")
                if isinstance(rg.get("reasoning"), dict)
                else None
            ) or {}
            reasons = extra.get("reasons") if isinstance(extra, dict) else None
            if isinstance(reasons, list) and any(
                "drawdown_stop_triggered" in str(x) for x in reasons
            ):
                veto_dd += 1

    # Default: signoff config + all_weather.
    config_path = default_config_path
    policy_preset = None
    desk_preset = os.getenv("AIMM_DESK_STRATEGY_PRESET")  # allow operator override
    if desk_preset:
        desk_preset = desk_preset.strip().lower()
    if not desk_preset:
        desk_preset = "all_weather"

    notes = "baseline"
    if veto_dd >= 2:
        # Risk trouble: temporarily go passive.
        policy_preset = "passive"
        notes = f"recent_drawdown_vetoes={veto_dd} -> passive preset"

    return PolicyDecision(
        decided_at_ms=now_ms,
        config_path=config_path,
        policy_preset=policy_preset,
        desk_strategy_preset=desk_preset,
        notes=notes,
    )


__all__ = ["PolicyDecision", "PolicyMemoryStore", "decide_policy_from_memory"]
