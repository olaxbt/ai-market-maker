"""Tests for OMS ledger implementations, Oms+ledger integration, and OmsConfig.

All SQLite tests use pytest's tmp_path — no external services, no persistent filesystem state.
InMemoryLedger tests need no fixtures.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from adapters.exchange_protocol import ExchangeOrderResult
from adapters.nexus_adapter import OmsNexusAdapter, get_nexus_adapter, set_nexus_adapter
from config.execution_engine import EXECUTION_ENGINE_ENV
from config.oms_config import (
    OMS_LEDGER_ENV,
    OMS_SQLITE_PATH_ENV,
    load_oms_config,
)
from oms.ledger import _OPEN_STATES, InMemoryLedger, OmsLedger, SqliteLedger
from oms.oms import Oms
from oms.order import OmsOrder, OrderState

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_order(
    client_order_id: str = "coid-1",
    idempotency_key: str = "idem-1",
    state: OrderState = OrderState.CREATED,
    venue_order_id: str | None = None,
) -> OmsOrder:
    return OmsOrder(
        client_order_id=client_order_id,
        idempotency_key=idempotency_key,
        symbol="BTC/USDT",
        side="buy",
        order_type="limit",
        quantity=0.1,
        price=50_000.0,
        state=state,
        venue_order_id=venue_order_id,
        created_at=1_000_000,
        updated_at=1_000_000,
    )


class _AcceptingAdapter:
    def __init__(self) -> None:
        self.call_count = 0

    def place_order(self, *, symbol, side, qty, order_type, price, client_order_id):
        self.call_count += 1
        return ExchangeOrderResult(
            status="accepted",
            exchange_order_id=f"eid-{self.call_count}",
            client_order_id=client_order_id,
            symbol=symbol,
            side=side,
            qty=qty,
            price=price,
            filled_qty=0.0,
            ts=1_000_000,
            raw={},
        )

    def cancel_order(self, *, symbol, exchange_order_id):
        return ExchangeOrderResult(
            status="cancelled",
            exchange_order_id=exchange_order_id,
            client_order_id=None,
            symbol=symbol,
            side="",
            qty=0.0,
            price=None,
            filled_qty=0.0,
            ts=1_000_000,
            raw={},
        )

    def get_order_status(self, *, symbol, exchange_order_id):
        return ExchangeOrderResult(
            status="accepted",
            exchange_order_id=exchange_order_id,
            client_order_id=None,
            symbol=symbol,
            side="",
            qty=0.0,
            price=None,
            filled_qty=0.0,
            ts=1_000_000,
            raw={},
        )

    def get_portfolio_health(self, *, account_id=None):
        return {}

    def fetch_market_depth(self, *, symbol, limit):
        return {}


# ---------------------------------------------------------------------------
# InMemoryLedger tests
# ---------------------------------------------------------------------------


def test_in_memory_ledger_upsert_and_load():
    ledger = InMemoryLedger()
    order = _make_order()
    ledger.upsert_order(order)
    loaded = ledger.load_orders()
    assert len(loaded) == 1
    assert loaded[0].client_order_id == "coid-1"


def test_in_memory_ledger_get_by_client_id():
    ledger = InMemoryLedger()
    order = _make_order(client_order_id="abc")
    ledger.upsert_order(order)
    assert ledger.get_order_by_client_id("abc") is order
    assert ledger.get_order_by_client_id("missing") is None


def test_in_memory_ledger_get_by_idempotency_key():
    ledger = InMemoryLedger()
    order = _make_order(idempotency_key="idem-xyz")
    ledger.upsert_order(order)
    assert ledger.get_order_by_idempotency_key("idem-xyz") is order
    assert ledger.get_order_by_idempotency_key("missing") is None


def test_in_memory_ledger_upsert_overwrites():
    ledger = InMemoryLedger()
    order = _make_order(state=OrderState.CREATED)
    ledger.upsert_order(order)
    order.state = OrderState.ACCEPTED  # mutate in place
    ledger.upsert_order(order)
    assert ledger.get_order_by_client_id("coid-1").state == OrderState.ACCEPTED


def test_in_memory_ledger_list_open_orders():
    ledger = InMemoryLedger()
    for state in OrderState:
        ledger.upsert_order(
            _make_order(client_order_id=state.value, idempotency_key=state.value, state=state)
        )
    open_states = {o.state for o in ledger.list_open_orders()}
    assert open_states == set(_OPEN_STATES)


def test_in_memory_ledger_append_and_list_events():
    ledger = InMemoryLedger()
    ledger.append_event("coid-1", "order_created")
    ledger.append_event("coid-1", "order_submitted", {"venue": "test"})
    events = ledger.list_events("coid-1")
    assert len(events) == 2
    assert events[0]["event_type"] == "order_created"
    assert events[1]["event_type"] == "order_submitted"
    assert events[1]["payload"] == {"venue": "test"}


def test_in_memory_ledger_events_isolated_per_order():
    ledger = InMemoryLedger()
    ledger.append_event("coid-1", "order_created")
    ledger.append_event("coid-2", "order_created")
    assert len(ledger.list_events("coid-1")) == 1
    assert len(ledger.list_events("coid-2")) == 1
    assert ledger.list_events("coid-3") == []


def test_in_memory_ledger_satisfies_protocol():
    assert isinstance(InMemoryLedger(), OmsLedger)


# ---------------------------------------------------------------------------
# SqliteLedger tests
# ---------------------------------------------------------------------------


def test_sqlite_creates_schema_on_init(tmp_path: Path):
    db = tmp_path / "oms.db"
    ledger = SqliteLedger(db)
    # Both tables must exist
    tables = {
        r[0]
        for r in ledger._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "oms_orders" in tables
    assert "oms_order_events" in tables
    ledger.close()


def test_sqlite_creates_parent_dirs(tmp_path: Path):
    db = tmp_path / "a" / "b" / "c" / "oms.db"
    ledger = SqliteLedger(db)
    assert db.exists()
    ledger.close()


def test_sqlite_upsert_and_load_roundtrip(tmp_path: Path):
    db = tmp_path / "oms.db"
    ledger = SqliteLedger(db)
    order = _make_order(venue_order_id="v-1")
    order.filled_quantity = 0.05
    order.error = None
    ledger.upsert_order(order)

    loaded = ledger.load_orders()
    assert len(loaded) == 1
    o = loaded[0]
    assert o.client_order_id == order.client_order_id
    assert o.idempotency_key == order.idempotency_key
    assert o.symbol == "BTC/USDT"
    assert o.side == "buy"
    assert o.order_type == "limit"
    assert o.quantity == 0.1
    assert o.price == 50_000.0
    assert o.state == OrderState.CREATED
    assert o.venue_order_id == "v-1"
    assert o.filled_quantity == 0.05
    assert o.created_at == 1_000_000
    assert o.updated_at == 1_000_000
    ledger.close()


def test_sqlite_upsert_overwrites_state(tmp_path: Path):
    db = tmp_path / "oms.db"
    ledger = SqliteLedger(db)
    order = _make_order(state=OrderState.CREATED)
    ledger.upsert_order(order)
    order._transition(OrderState.ACCEPTED)
    ledger.upsert_order(order)
    loaded = ledger.load_orders()
    assert loaded[0].state == OrderState.ACCEPTED
    ledger.close()


def test_sqlite_all_order_states_roundtrip(tmp_path: Path):
    db = tmp_path / "oms.db"
    ledger = SqliteLedger(db)
    for i, state in enumerate(OrderState):
        order = _make_order(
            client_order_id=f"coid-{i}",
            idempotency_key=f"idem-{i}",
            state=state,
        )
        ledger.upsert_order(order)
    loaded = {o.client_order_id: o for o in ledger.load_orders()}
    for i, state in enumerate(OrderState):
        assert loaded[f"coid-{i}"].state == state
    ledger.close()


def test_sqlite_list_open_orders_excludes_terminal(tmp_path: Path):
    db = tmp_path / "oms.db"
    ledger = SqliteLedger(db)
    terminal_states = {
        OrderState.FILLED,
        OrderState.CANCELLED,
        OrderState.REJECTED,
        OrderState.EXPIRED,
        OrderState.FAILED,
    }
    for i, state in enumerate(OrderState):
        ledger.upsert_order(
            _make_order(client_order_id=f"coid-{i}", idempotency_key=f"idem-{i}", state=state)
        )
    open_orders = ledger.list_open_orders()
    open_states = {o.state for o in open_orders}
    assert open_states.isdisjoint(terminal_states)
    assert open_states == set(_OPEN_STATES)
    ledger.close()


def test_sqlite_get_by_client_id(tmp_path: Path):
    db = tmp_path / "oms.db"
    ledger = SqliteLedger(db)
    ledger.upsert_order(_make_order(client_order_id="target"))
    result = ledger.get_order_by_client_id("target")
    assert result is not None
    assert result.client_order_id == "target"
    assert ledger.get_order_by_client_id("missing") is None
    ledger.close()


def test_sqlite_get_by_idempotency_key(tmp_path: Path):
    db = tmp_path / "oms.db"
    ledger = SqliteLedger(db)
    ledger.upsert_order(_make_order(idempotency_key="idem-unique"))
    result = ledger.get_order_by_idempotency_key("idem-unique")
    assert result is not None
    assert result.idempotency_key == "idem-unique"
    assert ledger.get_order_by_idempotency_key("missing") is None
    ledger.close()


def test_sqlite_multiple_orders(tmp_path: Path):
    db = tmp_path / "oms.db"
    ledger = SqliteLedger(db)
    for i in range(5):
        ledger.upsert_order(_make_order(client_order_id=f"c{i}", idempotency_key=f"k{i}"))
    assert len(ledger.load_orders()) == 5
    ledger.close()


def test_sqlite_append_and_list_events(tmp_path: Path):
    db = tmp_path / "oms.db"
    ledger = SqliteLedger(db)
    ledger.append_event("coid-1", "order_created")
    ledger.append_event("coid-1", "order_submitted", {"nonce": "abc"})
    events = ledger.list_events("coid-1")
    assert len(events) == 2
    assert events[0]["event_type"] == "order_created"
    assert events[0]["payload"] == {}
    assert events[1]["event_type"] == "order_submitted"
    assert events[1]["payload"] == {"nonce": "abc"}
    assert events[0]["id"] < events[1]["id"]  # ordered by insertion
    ledger.close()


def test_sqlite_events_isolated_per_order(tmp_path: Path):
    db = tmp_path / "oms.db"
    ledger = SqliteLedger(db)
    ledger.append_event("coid-A", "order_created")
    ledger.append_event("coid-B", "order_created")
    ledger.append_event("coid-A", "order_submitted")
    assert len(ledger.list_events("coid-A")) == 2
    assert len(ledger.list_events("coid-B")) == 1
    assert ledger.list_events("coid-X") == []
    ledger.close()


def test_sqlite_satisfies_protocol(tmp_path: Path):
    db = tmp_path / "oms.db"
    ledger = SqliteLedger(db)
    assert isinstance(ledger, OmsLedger)
    ledger.close()


# ---------------------------------------------------------------------------
# Oms + ledger integration tests
# ---------------------------------------------------------------------------


def test_oms_with_ledger_persists_submitted_order(tmp_path: Path):
    db = tmp_path / "oms.db"
    adapter = _AcceptingAdapter()
    oms = Oms(adapter=adapter, ledger=SqliteLedger(db))
    order = oms.submit_order(
        symbol="BTC/USDT",
        side="buy",
        order_type="limit",
        quantity=0.1,
        price=50_000.0,
        strategy="s",
        run_id="r",
        nonce="n1",
    )
    # Must be in the DB
    ledger = SqliteLedger(db)
    persisted = ledger.get_order_by_client_id(order.client_order_id)
    assert persisted is not None
    assert persisted.state == OrderState.ACCEPTED
    ledger.close()


def test_oms_survives_restart_with_sqlite_ledger(tmp_path: Path):
    db = tmp_path / "oms.db"
    adapter = _AcceptingAdapter()

    oms1 = Oms(adapter=adapter, ledger=SqliteLedger(db))
    order = oms1.submit_order(
        symbol="ETH/USDT",
        side="sell",
        order_type="market",
        quantity=1.0,
        strategy="s",
        run_id="r",
        nonce="n1",
    )
    coid = order.client_order_id

    # Simulate restart: new Oms with same DB
    oms2 = Oms(adapter=_AcceptingAdapter(), ledger=SqliteLedger(db))
    reloaded = oms2.get_order(client_order_id=coid)
    assert reloaded is not None
    assert reloaded.state == OrderState.ACCEPTED
    assert reloaded.client_order_id == coid


def test_oms_idempotency_survives_restart(tmp_path: Path):
    db = tmp_path / "oms.db"
    adapter1 = _AcceptingAdapter()

    oms1 = Oms(adapter=adapter1, ledger=SqliteLedger(db))
    order = oms1.submit_order(
        symbol="BTC/USDT",
        side="buy",
        order_type="limit",
        quantity=0.1,
        price=50_000.0,
        strategy="s",
        run_id="r",
        nonce="n1",
        idempotency_key="idem-restart-test",
    )
    assert adapter1.call_count == 1

    # Restart: second Oms with same DB and same idempotency_key
    adapter2 = _AcceptingAdapter()
    oms2 = Oms(adapter=adapter2, ledger=SqliteLedger(db))
    duplicate = oms2.submit_order(
        symbol="BTC/USDT",
        side="buy",
        order_type="limit",
        quantity=0.1,
        price=50_000.0,
        strategy="s",
        run_id="r",
        nonce="n1",
        idempotency_key="idem-restart-test",
    )
    assert adapter2.call_count == 0  # deduped by reloaded idem index
    assert duplicate.client_order_id == order.client_order_id


def test_oms_open_orders_survive_restart(tmp_path: Path):
    db = tmp_path / "oms.db"
    adapter = _AcceptingAdapter()

    oms1 = Oms(adapter=adapter, ledger=SqliteLedger(db))
    oms1.submit_order(
        symbol="BTC/USDT",
        side="buy",
        order_type="limit",
        quantity=0.1,
        price=50_000.0,
        strategy="s",
        run_id="r",
        nonce="n1",
    )
    oms1.submit_order(
        symbol="ETH/USDT",
        side="sell",
        order_type="market",
        quantity=1.0,
        strategy="s",
        run_id="r",
        nonce="n2",
    )

    ledger2 = SqliteLedger(db)
    open_orders = ledger2.list_open_orders()
    assert len(open_orders) == 2
    ledger2.close()


def test_oms_terminal_orders_not_returned_as_open(tmp_path: Path):
    db = tmp_path / "oms.db"
    adapter = _AcceptingAdapter()
    oms = Oms(adapter=adapter, ledger=SqliteLedger(db))

    order = oms.submit_order(
        symbol="BTC/USDT",
        side="buy",
        order_type="limit",
        quantity=0.1,
        price=50_000.0,
        strategy="s",
        run_id="r",
        nonce="n1",
    )
    # Cancel the accepted order (it has a venue_order_id now)
    oms.cancel_order(client_order_id=order.client_order_id)

    ledger = SqliteLedger(db)
    open_orders = ledger.list_open_orders()
    assert not any(o.client_order_id == order.client_order_id for o in open_orders)
    ledger.close()


def test_oms_events_emitted_on_submit(tmp_path: Path):
    db = tmp_path / "oms.db"
    adapter = _AcceptingAdapter()
    oms = Oms(adapter=adapter, ledger=SqliteLedger(db))

    order = oms.submit_order(
        symbol="BTC/USDT",
        side="buy",
        order_type="limit",
        quantity=0.1,
        price=50_000.0,
        strategy="s",
        run_id="r",
        nonce="n1",
    )
    ledger = SqliteLedger(db)
    events = ledger.list_events(order.client_order_id)
    event_types = [e["event_type"] for e in events]
    assert "order_created" in event_types
    assert "order_submitted" in event_types
    assert "order_accepted" in event_types
    ledger.close()


def test_oms_events_emitted_on_dry_run_submit(tmp_path: Path):
    db = tmp_path / "oms.db"
    adapter = _AcceptingAdapter()
    oms = Oms(adapter=adapter, dry_run=True, ledger=SqliteLedger(db))

    order = oms.submit_order(
        symbol="BTC/USDT",
        side="buy",
        order_type="limit",
        quantity=0.1,
        price=50_000.0,
        strategy="s",
        run_id="r",
        nonce="n1",
    )
    ledger = SqliteLedger(db)
    events = ledger.list_events(order.client_order_id)
    assert len(events) == 1
    assert events[0]["event_type"] == "order_created"
    assert events[0]["payload"].get("dry_run") is True
    ledger.close()


def test_oms_events_emitted_on_cancel(tmp_path: Path):
    db = tmp_path / "oms.db"
    adapter = _AcceptingAdapter()
    oms = Oms(adapter=adapter, ledger=SqliteLedger(db))

    order = oms.submit_order(
        symbol="BTC/USDT",
        side="buy",
        order_type="limit",
        quantity=0.1,
        price=50_000.0,
        strategy="s",
        run_id="r",
        nonce="n1",
    )
    oms.cancel_order(client_order_id=order.client_order_id)

    ledger = SqliteLedger(db)
    event_types = [e["event_type"] for e in ledger.list_events(order.client_order_id)]
    assert "order_cancelled" in event_types
    ledger.close()


def test_oms_without_ledger_behaviour_unchanged():
    """Oms(adapter=...) with no ledger must behave exactly as before this PR."""
    adapter = _AcceptingAdapter()
    oms = Oms(adapter=adapter)
    order = oms.submit_order(
        symbol="BTC/USDT",
        side="buy",
        order_type="limit",
        quantity=0.1,
        price=50_000.0,
        strategy="s",
        run_id="r",
        nonce="n1",
    )
    assert order.state == OrderState.ACCEPTED
    assert adapter.call_count == 1
    assert oms.get_order(client_order_id=order.client_order_id) is order


# ---------------------------------------------------------------------------
# OmsConfig / load_oms_config tests
# ---------------------------------------------------------------------------


def test_load_oms_config_default_is_in_memory(monkeypatch):
    monkeypatch.delenv(OMS_LEDGER_ENV, raising=False)
    cfg = load_oms_config()
    assert cfg.ledger_type == "in_memory"
    assert cfg.sqlite_path is None


def test_load_oms_config_sqlite_uses_default_path(monkeypatch):
    monkeypatch.setenv(OMS_LEDGER_ENV, "sqlite")
    monkeypatch.delenv(OMS_SQLITE_PATH_ENV, raising=False)
    cfg = load_oms_config()
    assert cfg.ledger_type == "sqlite"
    assert cfg.sqlite_path is not None
    assert str(cfg.sqlite_path) == ".runs/oms/orders.sqlite"


def test_load_oms_config_sqlite_custom_path(monkeypatch, tmp_path: Path):
    custom = str(tmp_path / "custom.db")
    monkeypatch.setenv(OMS_LEDGER_ENV, "sqlite")
    monkeypatch.setenv(OMS_SQLITE_PATH_ENV, custom)
    cfg = load_oms_config()
    assert cfg.sqlite_path == Path(custom)


def test_load_oms_config_invalid_raises(monkeypatch):
    monkeypatch.setenv(OMS_LEDGER_ENV, "redis")
    with pytest.raises(ValueError, match="not supported"):
        load_oms_config()


def test_load_oms_config_case_insensitive(monkeypatch):
    monkeypatch.setenv(OMS_LEDGER_ENV, "SQLITE")
    cfg = load_oms_config()
    assert cfg.ledger_type == "sqlite"


def test_no_sqlite_file_created_with_default_config(tmp_path: Path, monkeypatch):
    """Default in_memory config must never create any SQLite file."""
    monkeypatch.delenv(OMS_LEDGER_ENV, raising=False)
    cfg = load_oms_config()
    assert cfg.ledger_type == "in_memory"
    assert cfg.sqlite_path is None
    # No db file should exist anywhere under tmp_path (nothing was created)
    assert list(tmp_path.glob("**/*.sqlite")) == []
    assert list(tmp_path.glob("**/*.db")) == []


# ---------------------------------------------------------------------------
# Factory integration: get_nexus_adapter ledger injection
# ---------------------------------------------------------------------------


def test_get_nexus_adapter_oms_paper_default_no_ledger_file(monkeypatch, tmp_path: Path):
    """OMS + paper + default (in_memory) config must not create any SQLite file."""
    monkeypatch.setenv(EXECUTION_ENGINE_ENV, "oms")
    monkeypatch.delenv("EXCHANGE", raising=False)
    monkeypatch.delenv("AI_MARKET_MAKER_ALLOW_LIVE", raising=False)
    monkeypatch.delenv(OMS_LEDGER_ENV, raising=False)
    set_nexus_adapter(None)
    try:
        adapter = get_nexus_adapter()
        assert isinstance(adapter, OmsNexusAdapter)
        # In-memory by default — no DB files should appear
        assert list(tmp_path.glob("**/*.sqlite")) == []
    finally:
        set_nexus_adapter(None)


def test_get_nexus_adapter_oms_sqlite_injects_ledger(monkeypatch, tmp_path: Path):
    """OMS + paper + sqlite config must create and inject a SqliteLedger."""
    db = tmp_path / "test_oms.sqlite"
    monkeypatch.setenv(EXECUTION_ENGINE_ENV, "oms")
    monkeypatch.delenv("EXCHANGE", raising=False)
    monkeypatch.delenv("AI_MARKET_MAKER_ALLOW_LIVE", raising=False)
    monkeypatch.setenv(OMS_LEDGER_ENV, "sqlite")
    monkeypatch.setenv(OMS_SQLITE_PATH_ENV, str(db))
    set_nexus_adapter(None)
    try:
        adapter = get_nexus_adapter()
        assert isinstance(adapter, OmsNexusAdapter)
        # Place an order — should be written to the SQLite file
        result = adapter.place_smart_order(
            symbol="BTC/USDT", side="buy", qty=0.01, order_type="limit", price=50_000.0
        )
        assert result["status"] in ("accepted", "created")
        # DB file should now exist
        assert db.exists()
    finally:
        set_nexus_adapter(None)


def test_get_nexus_adapter_legacy_path_unchanged(monkeypatch):
    """Legacy path must never construct a ledger regardless of OMS_LEDGER env."""
    from adapters.nexus_adapter import NexusAdapter  # noqa: PLC0415

    monkeypatch.delenv(EXECUTION_ENGINE_ENV, raising=False)
    monkeypatch.setenv(OMS_LEDGER_ENV, "sqlite")  # should be ignored on legacy path
    monkeypatch.delenv("AI_MARKET_MAKER_ALLOW_LIVE", raising=False)
    set_nexus_adapter(None)
    try:
        adapter = get_nexus_adapter()
        assert isinstance(adapter, NexusAdapter)  # legacy, not OmsNexusAdapter
    finally:
        set_nexus_adapter(None)
