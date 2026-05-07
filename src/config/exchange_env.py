"""Environment config for the exchange adapter layer.

Use:
    EXCHANGE=paper           (default) — NexusAdapter, no real keys needed
    EXCHANGE=hyperliquid     — HyperliquidAdapter; also requires AI_MARKET_MAKER_ALLOW_LIVE=1

Hyperliquid-specific:
    HYPERLIQUID_API_KEY      — wallet address or API key
    HYPERLIQUID_SECRET       — private key / secret
    HYPERLIQUID_TESTNET=1    — use testnet API base (default: 1 for safety)
    HYPERLIQUID_DRY_RUN=1    — parse + validate but do not send orders (default: 0)
    HYPERLIQUID_API_BASE     — override API base URL (optional)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

from config.run_mode import LIVE_CONFIRM_ENV

EXCHANGE_ENV = "EXCHANGE"
HL_API_KEY_ENV = "HYPERLIQUID_API_KEY"
HL_SECRET_ENV = "HYPERLIQUID_SECRET"
HL_TESTNET_ENV = "HYPERLIQUID_TESTNET"
HL_DRY_RUN_ENV = "HYPERLIQUID_DRY_RUN"
HL_API_BASE_ENV = "HYPERLIQUID_API_BASE"


@dataclass(frozen=True)
class ExchangeConfig:
    exchange_name: str = "paper"
    testnet: bool = True
    dry_run: bool = False
    hyperliquid_api_key: str | None = None
    hyperliquid_secret: str | None = None
    hyperliquid_api_base: str | None = None

    def __repr__(self) -> str:
        secret_display = "[REDACTED]" if self.hyperliquid_secret else None
        return (
            f"ExchangeConfig("
            f"exchange_name={self.exchange_name!r}, "
            f"testnet={self.testnet!r}, "
            f"dry_run={self.dry_run!r}, "
            f"hyperliquid_api_key={self.hyperliquid_api_key!r}, "
            f"hyperliquid_secret={secret_display!r}, "
            f"hyperliquid_api_base={self.hyperliquid_api_base!r}"
            f")"
        )


def _truthy(val: str | None) -> bool:
    return str(val or "").strip().lower() in ("1", "true", "yes")


def load_exchange_config(*, env: Mapping[str, str] | None = None) -> ExchangeConfig:
    e = env if env is not None else os.environ
    name = (e.get(EXCHANGE_ENV) or "paper").strip().lower()

    if name != "paper":
        if not _truthy(e.get(LIVE_CONFIRM_ENV)):
            raise ValueError(
                f"EXCHANGE={name!r} requires {LIVE_CONFIRM_ENV}=1. "
                "Set it explicitly to confirm real trading intent."
            )

    testnet = _truthy(e.get(HL_TESTNET_ENV, "1"))
    dry_run = _truthy(e.get(HL_DRY_RUN_ENV))
    api_key = (e.get(HL_API_KEY_ENV) or "").strip() or None
    secret = (e.get(HL_SECRET_ENV) or "").strip() or None
    api_base = (e.get(HL_API_BASE_ENV) or "").strip() or None

    return ExchangeConfig(
        exchange_name=name,
        testnet=testnet,
        dry_run=dry_run,
        hyperliquid_api_key=api_key,
        hyperliquid_secret=secret,
        hyperliquid_api_base=api_base,
    )


__all__ = [
    "EXCHANGE_ENV",
    "ExchangeConfig",
    "HL_API_KEY_ENV",
    "HL_DRY_RUN_ENV",
    "HL_SECRET_ENV",
    "HL_TESTNET_ENV",
    "load_exchange_config",
]
