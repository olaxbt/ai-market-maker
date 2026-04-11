import asyncio
import sys
from pathlib import Path

import pytest


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


def test_risk_guard_kill_switch_vetoes(monkeypatch: pytest.MonkeyPatch):
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "src"))
    monkeypatch.setenv("AIMM_KILL_SWITCH", "1")
    from agents.governance.risk_guard import RiskGuardAgent

    guard = RiskGuardAgent()
    result = asyncio.run(guard.process({"proposal": {}}))
    assert result["status"] == "VETOED"
    assert result.get("kill_switch") is True
    monkeypatch.delenv("AIMM_KILL_SWITCH", raising=False)
