"""OMS persistent ledger abstractions.

Two implementations:
  InMemoryLedger — default, no I/O, zero side-effects (same behaviour as no ledger)
  SqliteLedger   — opt-in, stdlib sqlite3 only, WAL journal mode

No exchange SDK imports. No secrets stored beyond what OmsOrder already holds.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from oms.order import OmsOrder, OrderState

# Non-terminal states (orders that may still transition)
_OPEN_STATES: frozenset[str] = frozenset(
    {
        OrderState.CREATED,
        OrderState.SUBMITTED,
        OrderState.ACCEPTED,
        OrderState.PARTIALLY_FILLED,
        OrderState.UNKNOWN,
    }
)

_DDL = """
CREATE TABLE IF NOT EXISTS oms_orders (
    client_order_id    TEXT PRIMARY KEY,
    idempotency_key    TEXT NOT NULL,
    symbol             TEXT NOT NULL,
    side               TEXT NOT NULL,
    order_type         TEXT NOT NULL,
    quantity           REAL NOT NULL,
    price              REAL,
    state              TEXT NOT NULL,
    venue_order_id     TEXT,
    filled_quantity    REAL NOT NULL DEFAULT 0.0,
    average_fill_price REAL,
    error              TEXT,
    created_at         INTEGER NOT NULL,
    updated_at         INTEGER NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_oms_orders_idem
    ON oms_orders(idempotency_key);

CREATE TABLE IF NOT EXISTS oms_order_events (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    client_order_id  TEXT NOT NULL,
    event_type       TEXT NOT NULL,
    payload_json     TEXT,
    created_at       INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_oms_events_coid
    ON oms_order_events(client_order_id);
"""


def _row_to_order(row: sqlite3.Row) -> OmsOrder:
    return OmsOrder(
        client_order_id=row["client_order_id"],
        idempotency_key=row["idempotency_key"],
        symbol=row["symbol"],
        side=row["side"],
        order_type=row["order_type"],
        quantity=row["quantity"],
        price=row["price"],
        state=OrderState(row["state"]),
        venue_order_id=row["venue_order_id"],
        filled_quantity=row["filled_quantity"],
        average_fill_price=row["average_fill_price"],
        error=row["error"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@runtime_checkable
class OmsLedger(Protocol):
    """Minimal persistence contract for OMS order state and events."""

    def upsert_order(self, order: OmsOrder) -> None: ...

    def load_orders(self) -> list[OmsOrder]: ...

    def get_order_by_client_id(self, client_order_id: str) -> OmsOrder | None: ...

    def get_order_by_idempotency_key(self, idempotency_key: str) -> OmsOrder | None: ...

    def list_open_orders(self) -> list[OmsOrder]: ...

    def append_event(
        self,
        client_order_id: str,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> None: ...

    def list_events(self, client_order_id: str) -> list[dict[str, Any]]: ...


class InMemoryLedger:
    """In-memory ledger — no I/O, protocol-compatible. Default when no ledger is configured."""

    def __init__(self) -> None:
        self._orders: dict[str, OmsOrder] = {}
        self._idem_index: dict[str, str] = {}
        self._events: dict[str, list[dict[str, Any]]] = {}

    def upsert_order(self, order: OmsOrder) -> None:
        self._orders[order.client_order_id] = order
        self._idem_index[order.idempotency_key] = order.client_order_id

    def load_orders(self) -> list[OmsOrder]:
        return list(self._orders.values())

    def get_order_by_client_id(self, client_order_id: str) -> OmsOrder | None:
        return self._orders.get(client_order_id)

    def get_order_by_idempotency_key(self, idempotency_key: str) -> OmsOrder | None:
        coid = self._idem_index.get(idempotency_key)
        return self._orders.get(coid) if coid else None

    def list_open_orders(self) -> list[OmsOrder]:
        return [o for o in self._orders.values() if o.state in _OPEN_STATES]

    def append_event(
        self,
        client_order_id: str,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self._events.setdefault(client_order_id, []).append(
            {
                "client_order_id": client_order_id,
                "event_type": event_type,
                "payload": payload or {},
                "created_at": int(time.time()),
            }
        )

    def list_events(self, client_order_id: str) -> list[dict[str, Any]]:
        return list(self._events.get(client_order_id, []))


class SqliteLedger:
    """SQLite-backed OMS ledger using stdlib sqlite3 only.

    Creates parent directories and initialises the schema on construction.
    WAL journal mode is enabled for crash safety and concurrent reads.
    """

    def __init__(self, db_path: Path | str) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_DDL)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    def upsert_order(self, order: OmsOrder) -> None:
        self._conn.execute(
            """
            INSERT OR REPLACE INTO oms_orders (
                client_order_id, idempotency_key, symbol, side, order_type,
                quantity, price, state, venue_order_id, filled_quantity,
                average_fill_price, error, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order.client_order_id,
                order.idempotency_key,
                order.symbol,
                order.side,
                order.order_type,
                order.quantity,
                order.price,
                order.state.value,
                order.venue_order_id,
                order.filled_quantity,
                order.average_fill_price,
                order.error,
                order.created_at,
                order.updated_at,
            ),
        )
        self._conn.commit()

    def load_orders(self) -> list[OmsOrder]:
        rows = self._conn.execute("SELECT * FROM oms_orders").fetchall()
        return [_row_to_order(r) for r in rows]

    def get_order_by_client_id(self, client_order_id: str) -> OmsOrder | None:
        row = self._conn.execute(
            "SELECT * FROM oms_orders WHERE client_order_id = ?",
            (client_order_id,),
        ).fetchone()
        return _row_to_order(row) if row else None

    def get_order_by_idempotency_key(self, idempotency_key: str) -> OmsOrder | None:
        row = self._conn.execute(
            "SELECT * FROM oms_orders WHERE idempotency_key = ?",
            (idempotency_key,),
        ).fetchone()
        return _row_to_order(row) if row else None

    def list_open_orders(self) -> list[OmsOrder]:
        placeholders = ",".join("?" * len(_OPEN_STATES))
        rows = self._conn.execute(
            f"SELECT * FROM oms_orders WHERE state IN ({placeholders})",
            tuple(_OPEN_STATES),
        ).fetchall()
        return [_row_to_order(r) for r in rows]

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def append_event(
        self,
        client_order_id: str,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO oms_order_events (client_order_id, event_type, payload_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                client_order_id,
                event_type,
                json.dumps(payload) if payload else None,
                int(time.time()),
            ),
        )
        self._conn.commit()

    def list_events(self, client_order_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM oms_order_events WHERE client_order_id = ? ORDER BY id",
            (client_order_id,),
        ).fetchall()
        return [
            {
                "id": r["id"],
                "client_order_id": r["client_order_id"],
                "event_type": r["event_type"],
                "payload": json.loads(r["payload_json"]) if r["payload_json"] else {},
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def close(self) -> None:
        self._conn.close()


__all__ = ["InMemoryLedger", "OmsLedger", "SqliteLedger"]
