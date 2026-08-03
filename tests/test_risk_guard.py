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


def _dd_trip_base(*, positions: dict, action: str = "sell") -> dict:
    return {
        "run_mode": "backtest",
        "proposal": {"trades": {"BTC/USDT": {"action": action}}},
        "shared_memory": {
            "backtest": {
                "cash": 8100.0,
                "equity": 8100.0,
                "equity_peak": 10100.0,
                "dd_frac": 0.20,  # > default 0.12 stop
                "positions": positions,
            }
        },
        "market_data": {},
    }


def test_risk_guard_dd_kill_clears_when_flat():
    """Flat book after DD trip clears kill and allows re-entry."""
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "src"))

    from agents.governance.risk_guard import RiskGuardAgent

    guard = RiskGuardAgent()
    data = _dd_trip_base(positions={}, action="sell")
    result = asyncio.run(guard.process(data))
    assert result["status"] == "APPROVED"
    score, extra = guard._calculate_risk(data)
    assert score < 0.8
    assert any("drawdown_stop_cleared_flat_book" in str(r) for r in (extra.get("reasons") or []))
    assert not any("drawdown_stop_triggered" in str(r) for r in (extra.get("reasons") or []))


def test_risk_guard_dd_kill_allows_risk_reducing():
    """DD trip still allows risk-reducing sells."""
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "src"))

    from agents.governance.risk_guard import RiskGuardAgent

    guard = RiskGuardAgent()
    data = _dd_trip_base(
        positions={"BTC/USDT": {"qty_signed": 0.05, "size": 0.05, "direction": 1}},
        action="sell",
    )
    result = asyncio.run(guard.process(data))
    assert result["status"] == "APPROVED"
    score, extra = guard._calculate_risk(data)
    assert score < 0.8
    assert any(
        "drawdown_stop_armed_risk_reducing_allowed" in str(r) for r in (extra.get("reasons") or [])
    )


def test_risk_guard_dd_kill_vetoes_risk_increasing():
    """DD trip vetoes risk-increasing buys."""
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "src"))

    from agents.governance.risk_guard import RiskGuardAgent

    guard = RiskGuardAgent()
    data = _dd_trip_base(
        positions={"BTC/USDT": {"qty_signed": 0.05, "size": 0.05, "direction": 1}},
        action="buy",
    )
    data["run_mode"] = "paper"
    result = asyncio.run(guard.process(data))
    assert result["status"] == "VETOED"
    assert result["risk_score"] >= 0.8
    score, extra = guard._calculate_risk(data)
    assert any("drawdown_stop_triggered" in str(r) for r in (extra.get("reasons") or []))
    assert any("risk_increasing" in str(r) for r in (extra.get("reasons") or []))


def test_risk_guard_dd_kill_vetoes_risk_increasing_backtest():
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "src"))

    from agents.governance.risk_guard import RiskGuardAgent

    guard = RiskGuardAgent()
    data = _dd_trip_base(
        positions={"BTC/USDT": {"qty_signed": 0.05, "size": 0.05, "direction": 1}},
        action="buy",
    )
    result = asyncio.run(guard.process(data))
    assert result["status"] == "VETOED"
    assert result["risk_score"] >= 0.8


def test_risk_guard_dd_kill_flat_live_allows_reentry():
    """Live/paper flat book after DD trip clears kill."""
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "src"))

    from agents.governance.risk_guard import RiskGuardAgent

    guard = RiskGuardAgent()
    data = _dd_trip_base(positions={}, action="buy")
    data["run_mode"] = "paper"
    result = asyncio.run(guard.process(data))
    assert result["status"] == "APPROVED"
    assert result["risk_score"] < 0.8
