"""Loader registry with market-level fallback chains.

Loaders are registered explicitly — no decorators, no automatic imports.
"""

from __future__ import annotations

from typing import Any, Type

from .base import NoAvailableSourceError
from .ccxt_loader import CCXTLoader
from .futu_loader import FutuLoader
from .yfinance_loader import YFinanceLoader

LOADER_REGISTRY: dict[str, Type[Any]] = {}
FALLBACK_CHAINS: dict[str, list[str]] = {
    "crypto": ["ccxt"],
    "hk_equity": ["futu", "yfinance", "ccxt"],
    "a_share": ["futu", "yfinance", "ccxt"],
    "us_equity": ["yfinance", "futu", "ccxt"],
    "futures": ["yfinance"],
    "forex": ["yfinance"],
}


def register_loader(cls: Type[Any]) -> Type[Any]:
    LOADER_REGISTRY[cls.name] = cls
    return cls


register_loader(CCXTLoader)
register_loader(FutuLoader)
register_loader(YFinanceLoader)


def resolve_loader(market: str) -> Any:
    """Return the first loader instance for *market* following the fallback chain."""
    chain = FALLBACK_CHAINS.get(market, [])
    tried: list[str] = []
    for name in chain:
        if name not in LOADER_REGISTRY:
            continue
        tried.append(name)
        return LOADER_REGISTRY[name]()
    raise NoAvailableSourceError(
        f"No available data source for market '{market}'. Tried: {tried or chain}."
    )
