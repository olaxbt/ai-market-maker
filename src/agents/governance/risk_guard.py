from __future__ import annotations

from typing import Any, Dict

from agents.base_agent import BaseAgent


class RiskGuardAgent(BaseAgent):
    """
    Governance layer: implements veto power (final say).
    """

    def __init__(self):
        super().__init__("Risk Guard", "風控官")

    async def process(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Implements Veto Power.
        Expects a 'proposal' (e.g., orders/portfolio actions) and returns APPROVED/VETOED.
        """
        risk_score = self._calculate_risk(proposal)

        is_vetoed = risk_score > 0.8
        thought = (
            f"Risk score is {risk_score:.2f}. "
            f"{'VETOED due to high risk/volatility' if is_vetoed else 'APPROVED'}"
        )

        return {
            "status": "VETOED" if is_vetoed else "APPROVED",
            "risk_score": risk_score,
            "reasoning": self.log_reasoning(thought, "VETO" if is_vetoed else "PROCEED"),
        }

    def _calculate_risk(self, data: Dict[str, Any]) -> float:
        # Placeholder: later integrate with Nexus Security Guard + Simulator.
        return 0.5
