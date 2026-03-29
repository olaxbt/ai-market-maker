import pytest

from adapters.nexus_adapter import (
    NexusAdapter,
    NexusAdapterConfig,
    get_nexus_adapter,
    set_nexus_adapter,
)


def test_get_portfolio_health_smoke():
    a = NexusAdapter(NexusAdapterConfig(mode="paper"))
    h = a.get_portfolio_health()
    assert h["mode"] == "paper"
    assert "balances" in h


def test_fetch_market_depth_deterministic_shapes():
    a = NexusAdapter(NexusAdapterConfig(mode="paper"))
    book = a.fetch_market_depth(symbol="BTC/USDT", limit=3)
    assert book["symbol"] == "BTC/USDT"
    assert len(book["bids"]) == 3
    assert len(book["asks"]) == 3


def test_place_smart_order_rejects_bad_qty():
    a = NexusAdapter(NexusAdapterConfig(mode="paper"))
    res = a.place_smart_order(symbol="BTC/USDT", side="buy", qty=0)
    assert res["status"] == "rejected"


def test_place_smart_order_limit_requires_price():
    a = NexusAdapter(NexusAdapterConfig(mode="paper"))
    res = a.place_smart_order(symbol="BTC/USDT", side="buy", qty=1, order_type="limit")
    assert res["status"] == "rejected"


def test_place_smart_order_accepts_market():
    a = NexusAdapter(NexusAdapterConfig(mode="paper"))
    res = a.place_smart_order(symbol="BTC/USDT", side="buy", qty=1, order_type="market")
    assert res["status"] == "accepted"


def test_get_nexus_adapter_loads_olaxbt_nexus_data_url(monkeypatch: pytest.MonkeyPatch):
    set_nexus_adapter(None)
    monkeypatch.setenv("OLAXBT_NEXUS_DATA_BASE_URL", "https://nexus.test.invalid/api")
    adapter = get_nexus_adapter()
    assert adapter.config.nexus_data_base_url == "https://nexus.test.invalid/api"
    set_nexus_adapter(None)
