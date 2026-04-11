from __future__ import annotations

from llm.portfolio_llm import sanitize_portfolio_trades


def test_sanitize_portfolio_trades_filters_universe_and_actions() -> None:
    parsed = {
        "trades": {
            "BTC/USDT": {"action": "buy", "weight": 0.5},
            "ETH/USDT": {"action": "HOLD", "weight": 0.5},
            "DOGE/USDT": {"action": "buy", "weight": 0.5},
            "SOL/USDT": {"action": "moon"},
        }
    }
    out = sanitize_portfolio_trades(parsed, universe=["BTC/USDT", "ETH/USDT"])
    assert out["status"] == "success"
    assert set(out["trades"].keys()) == {"BTC/USDT", "ETH/USDT"}
    assert out["trades"]["BTC/USDT"]["action"] == "buy"
    assert out["trades"]["ETH/USDT"]["action"] == "hold"
