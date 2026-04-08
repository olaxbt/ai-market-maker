"""Default multi-symbol universe for backtests and demos when the operator omits ``--symbols``.

Single source of truth: `config/app.default.json`.
"""

from __future__ import annotations

DEFAULT_UNIVERSE_SYMBOLS: tuple[str, ...] = (
    "BTC/USDT",
    "ETH/USDT",
    "SOL/USDT",
    "AIO/USDT",
    "BNB/USDT",
    "XRP/USDT",
    "ADA/USDT",
)


def resolve_backtest_symbol_list(
    primary: str,
    *,
    max_symbols: int = 7,
) -> list[str]:
    """Return up to ``max_symbols`` pairs: ``primary`` first, then app defaults."""
    primary = (primary or "BTC/USDT").strip() or "BTC/USDT"
    cap = max(1, int(max_symbols))
    pool = list(DEFAULT_UNIVERSE_SYMBOLS)
    if primary not in pool:
        merged = [primary] + pool
    else:
        merged = [primary] + [x for x in pool if x != primary]

    seen: set[str] = set()
    out: list[str] = []
    for sym in merged:
        if sym not in seen:
            seen.add(sym)
            out.append(sym)
        if len(out) >= cap:
            break
    return out


__all__ = ["DEFAULT_UNIVERSE_SYMBOLS", "resolve_backtest_symbol_list"]
