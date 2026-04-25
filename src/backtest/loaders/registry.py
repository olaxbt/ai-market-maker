"""Loader registry with direct module-level registration.

Loaders self-register via the ``@register`` decorator when their module is
imported.
"""

from __future__ import annotations

from typing import Any, Type

from .base import NoAvailableSourceError

LOADER_REGISTRY: dict[str, Type[Any]] = {}


def register(cls: Type[Any]) -> Type[Any]:
    """Class decorator: register a loader into the global registry."""
    LOADER_REGISTRY[cls.name] = cls
    return cls


FALLBACK_CHAINS: dict[str, list[str]] = {
    "crypto": ["ccxt"],
    "hk_equity": ["futu", "yfinance", "ccxt"],
    "a_share": ["futu", "yfinance", "ccxt"],
    "us_equity": ["yfinance", "futu", "ccxt"],
    "futures": ["yfinance"],
    "forex": ["yfinance"],
}


def resolve_loader(market: str) -> Any:
    """Return the first loader instance for *market* following the fallback chain."""
    chain = FALLBACK_CHAINS.get(market, [])
    tried: list[str] = []
    for name in chain:
        if name not in LOADER_REGISTRY:
            continue
        loader = LOADER_REGISTRY[name]()
        tried.append(name)
        return loader
    raise NoAvailableSourceError(
        f"No available data source for market '{market}'. Tried: {tried or chain}."
    )


# Import loaders at module bottom so @register fires after LOADER_REGISTRY exists.
import backtest.loaders.ccxt_loader  # noqa: F401 E402
import backtest.loaders.futu_loader  # noqa: F401 E402
import backtest.loaders.yfinance_loader  # noqa: F401 E402
