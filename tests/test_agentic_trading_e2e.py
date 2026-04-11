"""End-to-end workflow: full LangGraph with Tier-0 fixtures + execution path (stubs, no network)."""

from __future__ import annotations

from typing import Any, Dict, List

import pytest
from nexus_agentic_fixtures import (
    nexus_bundle_bullish_btc,
    nexus_bundle_risk_off_btc,
    ohlcv_window_btc,
)

import main as main_mod
from config.run_mode import RunMode
from schemas.state import initial_hedge_fund_state
from schemas.tier0_contract import TIER0_NODE_TO_AGENT_ID, tier0_consensus_for_arbitrator


class _StubMarketScanAgent:
    def __init__(self, *args, **kwargs):
        pass

    def fetch_data(self, ticker: str, timeframe: str = "1h") -> Dict[str, Any]:
        return {
            "ticker": ticker,
            "ohlcv": [[0, 0, 0, 0, 100.0, 1.0]],
            "bids": [[99.5, 1.0]],
            "asks": [[100.5, 1.0]],
            "status": "success",
        }

    def scan_meme_coins(self) -> List[Dict[str, Any]]:
        return []


class _StubPortfolioManagementAgent:
    def __init__(self, *args, **kwargs):
        pass

    def analyze(self, ticker: str, *args, execute: bool = True, **kwargs) -> Dict[str, Any]:
        return {
            "status": "success",
            "allocations": {ticker: {"weight": 1.0, "amount": 10.0, "stop_price": 0}},
            "trades": {
                ticker: {
                    "status": "proposed",
                    "action": "buy",
                    "quantity": 0.01,
                    "reason": {"note": "stub"},
                }
            },
        }


class _StubRiskManagementAgent:
    def __init__(self, *args, **kwargs):
        pass

    def analyze(self, market_data: Dict[str, Any], valuation: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "success", "analysis": {"BTC/USDT": {"volatility": 0.001}}}


class _StubRiskGuardAgent:
    role = "agent"

    def __init__(self, *args, **kwargs):
        pass

    async def process(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "APPROVED", "risk_score": 0.1, "reasoning": {"thought": "stub approve"}}


class _StubNexusAdapter:
    def fetch_market_depth(self, *, symbol: str, limit: int = 5) -> Dict[str, Any]:
        return {"status": "success", "bids": [[100.0, 1.0]], "asks": [[100.5, 1.0]]}

    def place_smart_order(self, *, symbol: str, side: str, qty: float, **kwargs) -> Dict[str, Any]:
        return {"status": "accepted", "symbol": symbol, "side": side, "qty": qty}


@pytest.fixture
def agentic_stubs(monkeypatch):
    # Deterministic arbitrator + execution intent (not LLM), regardless of developer .env.
    monkeypatch.setenv("AI_MARKET_MAKER_USE_LLM", "0")
    monkeypatch.setattr(main_mod, "MarketScanAgent", _StubMarketScanAgent)
    monkeypatch.setattr(main_mod, "PortfolioManagementAgent", _StubPortfolioManagementAgent)
    monkeypatch.setattr(main_mod, "RiskManagementAgent", _StubRiskManagementAgent)
    monkeypatch.setattr(main_mod, "RiskGuardAgent", _StubRiskGuardAgent)
    monkeypatch.setattr(main_mod, "get_nexus_adapter", lambda: _StubNexusAdapter())


def _base_state(*, nexus_bundle: dict[str, Any]) -> dict[str, Any]:
    state = initial_hedge_fund_state(run_mode=RunMode.BACKTEST.value, ticker="BTC/USDT")
    state["market_data"] = {
        "BTC/USDT": {
            "status": "success",
            "ohlcv": ohlcv_window_btc(bars=100),
            "nexus_depth": {"status": "success", "bids": [], "asks": []},
        }
    }
    state["shared_memory"] = {
        "nexus": nexus_bundle,
        "backtest": {"cash": 10_000.0, "qty": 0.0},
    }
    return state


def test_agentic_graph_emits_all_tier0_contracts(agentic_stubs, monkeypatch):
    monkeypatch.setattr(main_mod, "nexus_feeds_enabled", lambda: False)

    app = main_mod.build_workflow().compile()
    out = app.invoke(_base_state(nexus_bundle=nexus_bundle_bullish_btc()))

    contracts = out.get("tier0_contracts") or []
    assert len(contracts) == len(TIER0_NODE_TO_AGENT_ID)
    agents = {str(c.get("agent")) for c in contracts if isinstance(c, dict)}
    assert agents == set(TIER0_NODE_TO_AGENT_ID.values())


def test_agentic_bullish_nexus_drives_buy_intent(agentic_stubs, monkeypatch):
    monkeypatch.setattr(main_mod, "nexus_feeds_enabled", lambda: False)

    app = main_mod.build_workflow().compile()
    out = app.invoke(_base_state(nexus_bundle=nexus_bundle_bullish_btc()))

    tc = tier0_consensus_for_arbitrator(out)
    assert tc["bull_tilt"] >= 1

    intent = out.get("trade_intent") or {}
    assert intent.get("action") == "BUY"

    ex = out.get("execution_result") or {}
    smart = ex.get("smart_order")
    assert isinstance(smart, dict)
    assert smart.get("status") == "accepted"


def test_agentic_risk_off_nexus_suppresses_buy(agentic_stubs, monkeypatch):
    monkeypatch.setattr(main_mod, "nexus_feeds_enabled", lambda: False)

    app = main_mod.build_workflow().compile()
    out = app.invoke(_base_state(nexus_bundle=nexus_bundle_risk_off_btc()))

    tc = tier0_consensus_for_arbitrator(out)
    assert tc["bear_tilt"] >= tc["bull_tilt"]
    assert tc.get("block_aggressive_long") is True

    intent = out.get("trade_intent") or {}
    assert intent.get("action") in ("HOLD", "SELL")
