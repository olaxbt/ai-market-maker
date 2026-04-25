"""Loader registry with market-level fallback chains.

Loaders self-register via the ``@register`` decorator when their module is
first imported.  ``_ensure_registered()`` lazily imports every known loader
module so the registry is always populated.
"""

from __future__ import annotations

import logging
from typing import Any, Type

from .base import NoAvailableSourceError

logger = logging.getLogger(__name__)

LOADER_REGISTRY: dict[str, Type[Any]] = {}
_registered = False


def register(cls: Type[Any]) -> Type[Any]:
    """Class decorator: register a loader into the global registry."""
    LOADER_REGISTRY[cls.name] = cls
    return cls


def _ensure_registered() -> None:
    global _registered
    if _registered:
        return
    _registered = True

    _loader_modules = [
        "backtest.loaders.ccxt_loader",
        "backtest.loaders.futu_loader",
        "backtest.loaders.yfinance_loader",
    ]
    import importlib

    for mod in _loader_modules:
        try:
            importlib.import_module(mod)
        except Exception:
            pass


FALLBACK_CHAINS: dict[str, list[str]] = {
    "crypto": ["ccxt"],
    "hk_equity": ["futu", "yfinance", "ccxt"],
    "a_share": ["futu", "yfinance", "ccxt"],
    "us_equity": ["yfinance", "futu", "ccxt"],
    "futures": ["yfinance"],
    "forex": ["yfinance"],
}


def resolve_loader(market: str) -> Any:
    """Return the first *available* loader instance for *market*.

    Walks the fallback chain and returns the first loader whose
    ``is_available()`` returns ``True``.
    """
    _ensure_registered()
    chain = FALLBACK_CHAINS.get(market, [])
    tried: list[str] = []
    for name in chain:
        if name not in LOADER_REGISTRY:
            continue
        loader = LOADER_REGISTRY[name]()
        tried.append(name)
        if loader.is_available():
            return loader
    raise NoAvailableSourceError(
        f"No available data source for market '{market}'. "
        f"Tried: {tried or chain}. Check network and API token config."
    )


def get_loader_cls_with_fallback(source: str) -> Type[Any]:
    """Return a loader *class* for *source*, falling back if unavailable."""
    _ensure_registered()
    if source not in LOADER_REGISTRY:
        raise NoAvailableSourceError(f"Unknown data source: {source}")

    loader_cls = LOADER_REGISTRY[source]
    instance = loader_cls()
    if instance.is_available():
        return loader_cls

    for market in loader_cls.markets:
        try:
            fallback = resolve_loader(market)
            logger.warning(
                "%s is unavailable, falling back to %s for market %s",
                source,
                fallback.name,
                market,
            )
            return type(fallback)
        except NoAvailableSourceError:
            continue

    raise NoAvailableSourceError(f"Data source '{source}' is unavailable and no fallback found.")
