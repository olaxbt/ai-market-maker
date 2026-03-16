import asyncio
import sys
from pathlib import Path


def test_risk_guard_returns_reasoning():
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "src"))

    from agents.governance.risk_guard import RiskGuardAgent

    guard = RiskGuardAgent()
    result = asyncio.run(guard.process({"proposal": {"trades": {"BTC/USDT": {"action": "buy"}}}}))

    assert result["status"] in {"APPROVED", "VETOED"}
    assert isinstance(result.get("risk_score"), float)
    reasoning = result.get("reasoning")
    assert isinstance(reasoning, dict)
    assert reasoning.get("agent") == "Risk Guard"
    assert "decision" in reasoning
