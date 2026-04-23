from __future__ import annotations

from adapters.nexus_adapter import NexusAdapter


def test_mock_depth_is_explicitly_labeled() -> None:
    out = NexusAdapter().fetch_market_depth(symbol="BTC/USDT", limit=3)
    assert out.get("is_mock") is True
    assert out.get("source") == "mock"
    assert isinstance(out.get("note"), str) and out["note"]
