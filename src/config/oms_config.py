"""OMS ledger configuration.

AI_MARKET_MAKER_OMS_LEDGER=in_memory   (default) — pure in-memory, no filesystem side-effects
AI_MARKET_MAKER_OMS_LEDGER=sqlite      — SQLite persistence; requires no external services

AI_MARKET_MAKER_OMS_SQLITE_PATH=.runs/oms/orders.sqlite
    Path to the SQLite file. Only read when ledger type is 'sqlite'.
    Defaults to .runs/oms/orders.sqlite if not set.
    The directory is created lazily when SqliteLedger is first constructed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

OMS_LEDGER_ENV = "AI_MARKET_MAKER_OMS_LEDGER"
OMS_SQLITE_PATH_ENV = "AI_MARKET_MAKER_OMS_SQLITE_PATH"
_DEFAULT_SQLITE_PATH = ".runs/oms/orders.sqlite"


@dataclass(frozen=True)
class OmsConfig:
    ledger_type: str = "in_memory"  # "in_memory" | "sqlite"
    sqlite_path: Path | None = None  # only meaningful when ledger_type == "sqlite"


def load_oms_config(*, env: Mapping[str, str] | None = None) -> OmsConfig:
    """Load OMS ledger config from the environment.

    Raises:
        ValueError: if AI_MARKET_MAKER_OMS_LEDGER is set to an unsupported value.
    """
    e = env if env is not None else os.environ
    ledger_type = (e.get(OMS_LEDGER_ENV) or "in_memory").strip().lower()

    if ledger_type not in ("in_memory", "sqlite"):
        raise ValueError(
            f"AI_MARKET_MAKER_OMS_LEDGER={ledger_type!r} is not supported. "
            "Valid values: 'in_memory' (default), 'sqlite'."
        )

    sqlite_path: Path | None = None
    if ledger_type == "sqlite":
        raw = (e.get(OMS_SQLITE_PATH_ENV) or _DEFAULT_SQLITE_PATH).strip()
        sqlite_path = Path(raw)

    return OmsConfig(ledger_type=ledger_type, sqlite_path=sqlite_path)


__all__ = ["OMS_LEDGER_ENV", "OMS_SQLITE_PATH_ENV", "OmsConfig", "load_oms_config"]
