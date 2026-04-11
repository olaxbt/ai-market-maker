from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import ccxt

DEFAULT_CORE = ("BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "ADA/USDT", "DOGE/USDT")


def _is_spot_symbol(sym: str) -> bool:
    # Conservative filter for ccxt-style symbols.
    if "/" not in sym:
        return False
    if sym.endswith((":UP/USDT", ":DOWN/USDT")):
        return False
    return True


def _is_usdt_quote(sym: str) -> bool:
    return sym.endswith("/USDT")


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)


@dataclass(frozen=True)
class UniverseSelection:
    universe: list[str]
    pairs: list[tuple[str, str]]
    source: str


def build_pairs(universe: Iterable[str], *, max_pairs: int = 21) -> list[tuple[str, str]]:
    syms = [s for s in universe if isinstance(s, str)]
    out: list[tuple[str, str]] = []
    for i, a in enumerate(syms):
        for b in syms[i + 1 :]:
            out.append((a, b))
            if len(out) >= max_pairs:
                return out
    return out


def select_universe_from_tickers(
    tickers: dict[str, dict[str, Any]] | None,
    *,
    primary: str,
    size: int = 7,
) -> UniverseSelection:
    if size < 1:
        size = 1
    if not tickers:
        universe = [primary] + [s for s in DEFAULT_CORE if s != primary]
        universe = universe[:size]
        return UniverseSelection(
            universe=universe, pairs=build_pairs(universe), source="default_core"
        )

    # Prefer quoteVolume; fall back to baseVolume/last.
    scored: list[tuple[float, str]] = []
    for sym, t in tickers.items():
        if not isinstance(sym, str) or not isinstance(t, dict):
            continue
        if not _is_spot_symbol(sym) or not _is_usdt_quote(sym):
            continue
        vol = _safe_float(t.get("quoteVolume"), 0.0)
        if vol <= 0:
            vol = _safe_float(t.get("baseVolume"), 0.0)
        scored.append((vol, sym))
    scored.sort(reverse=True)
    universe = [primary]
    for _vol, sym in scored:
        if sym != primary:
            universe.append(sym)
        if len(universe) >= size:
            break
    if len(universe) < size:
        for s in DEFAULT_CORE:
            if s not in universe and len(universe) < size:
                universe.append(s)
    return UniverseSelection(
        universe=universe, pairs=build_pairs(universe), source="tickers_volume_rank"
    )


def augment_universe_with_oi(
    oi_candidates_ccxt: list[str],
    *,
    primary: str,
    tickers: dict[str, dict[str, Any]] | None,
    size: int,
    markets: set[str] | None = None,
) -> UniverseSelection:
    """Prefer primary, then Nexus OI-ranked symbols (if listed on exchange), then volume core."""
    if size < 1:
        size = 1
    seen: set[str] = set()
    universe: list[str] = []

    def _take(sym: str) -> None:
        if sym in seen:
            return
        if markets is not None and sym not in markets:
            return
        seen.add(sym)
        universe.append(sym)

    _take(primary)
    for sym in oi_candidates_ccxt:
        if len(universe) >= size:
            break
        if isinstance(sym, str):
            _take(sym)

    if len(universe) < size:
        vol = select_universe_from_tickers(tickers, primary=primary, size=size)
        for sym in vol.universe:
            if len(universe) >= size:
                break
            _take(sym)

    if len(universe) < size:
        for sym in DEFAULT_CORE:
            if len(universe) >= size:
                break
            _take(sym)

    u = universe[:size]
    source = "nexus_oi_plus_volume" if oi_candidates_ccxt else "tickers_volume_rank"
    return UniverseSelection(universe=u, pairs=build_pairs(u), source=source)


def fetch_volume_ranked_universe_ccxt(
    *,
    primary: str,
    size: int,
    exchange_id: str = "binance",
) -> UniverseSelection:
    """Pick ``size`` USDT spot symbols: ``primary`` first, rest by 24h quote volume on the exchange.

    Use for backtests when you do not want a hand-picked ``--symbols`` list: same idea as a fund
    rotating into the most liquid names the venue actually lists.
    """
    if size < 1:
        size = 1
    primary = (primary or "BTC/USDT").strip() or "BTC/USDT"
    ex_class = getattr(ccxt, exchange_id)
    exchange = ex_class({"enableRateLimit": True})
    exchange.load_markets()
    tickers = exchange.fetch_tickers()
    return select_universe_from_tickers(tickers, primary=primary, size=size)
