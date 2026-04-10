from __future__ import annotations

import os
from typing import Any, Dict

from agents.base_agent import BaseAgent
from memory.policy_memory import PolicyMemoryStore, decide_policy_from_memory


def _env_truthy(name: str) -> bool:
    v = (os.getenv(name) or "").strip().lower()
    return v in ("1", "true", "yes", "on")


class PolicyOrchestratorAgent(BaseAgent):
    """Lightweight orchestrator that chooses policy config/preset across runs.

    This is the minimal "agentic control" layer:
    - reads persistent memory (JSONL)
    - selects config/preset for this run
    - records the decision
    """

    def __init__(self):
        super().__init__("Policy Orchestrator", "Supervisor")
        self.store = PolicyMemoryStore()

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        if _env_truthy("AIMM_ORCHESTRATOR_DISABLE"):
            return {
                "status": "SKIPPED",
                "reasoning": self.log_reasoning(
                    "Orchestrator disabled by AIMM_ORCHESTRATOR_DISABLE.", "SKIP"
                ),
            }

        # Default to a shipped policy file if operator didn't set one.
        default_cfg = os.getenv("AIMM_CONFIG_PATH") or os.getenv("AIMM_POLICY_CONFIG_PATH")
        if not default_cfg:
            default_cfg = "config/policy.default.json"

        recent = list(self.store.iter_events(limit=200))
        decision = decide_policy_from_memory(recent=recent, default_config_path=default_cfg)

        # Apply decision to env for the rest of this graph tick.
        if decision.config_path:
            os.environ["AIMM_CONFIG_PATH"] = str(decision.config_path)
        if decision.policy_preset:
            os.environ["AIMM_POLICY_PRESET"] = str(decision.policy_preset)
        if decision.desk_strategy_preset:
            os.environ["AIMM_DESK_STRATEGY_PRESET"] = str(decision.desk_strategy_preset)

        event = {
            "kind": "policy_decision",
            "decided_at_ms": decision.decided_at_ms,
            "config_path": decision.config_path,
            "policy_preset": decision.policy_preset,
            "desk_strategy_preset": decision.desk_strategy_preset,
            "notes": decision.notes,
        }
        self.store.append_event(event)
        return {
            "status": "success",
            "policy_decision": event,
            "reasoning": self.log_reasoning(
                f"Policy selected: config={decision.config_path} preset={decision.policy_preset} desk={decision.desk_strategy_preset}.",
                "PROCEED",
            ),
        }


__all__ = ["PolicyOrchestratorAgent"]
