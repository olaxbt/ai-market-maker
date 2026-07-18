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


def test_risk_guard_prefers_engine_mark_equity():
    """Backtest shared_memory publishes mark equity; do not rebuild as cash + spot qty."""
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "src"))

    from agents.governance.risk_guard import RiskGuardAgent

    guard = RiskGuardAgent()
    data = {
        "proposal": {},
        "shared_memory": {
            "backtest": {
                "cash": 500.0,  # free collateral only
                "equity": 10_200.0,  # mark NAV from PerpEngine
                "positions": {"BTC/USDT": {"size": 0.1, "entry": 100_000.0}},
            }
        },
        "market_data": {
            "BTC/USDT": {
                "ohlcv": [[0, 100_000, 100_000, 100_000, 100_000, 1]],
            }
        },
    }
    score, extra = guard._calculate_risk(data)
    assert extra["equity"] == pytest.approx(10_200.0)
    assert extra["gross_exposure"] == pytest.approx(10_000.0)
    assert 0.0 <= score <= 1.0
