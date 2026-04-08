from __future__ import annotations


def split_ccxt_symbol(sym: str) -> tuple[str, str] | None:
    if "/" not in sym:
        return None
    base, quote = sym.split("/", 1)
    b, q = base.strip(), quote.strip()
    if not b or not q:
        return None
    return b, q


def ccxt_to_nexus_pair_id(sym: str) -> str:
    """Map ``BTC/USDT`` → ``BTCUSDT`` for Nexus coin/OI-style IDs."""
    parts = split_ccxt_symbol(sym)
    if not parts:
        return sym.replace("/", "").upper()
    return f"{parts[0]}{parts[1]}".upper()


def nexus_pair_id_to_ccxt(nid: str) -> str | None:
    """Best-effort map ``CTSIUSDT`` → ``CTSI/USDT``."""
    u = nid.upper()
    for quote in ("USDT", "USDC", "BUSD"):
        if u.endswith(quote) and len(u) > len(quote):
            return f"{u[: -len(quote)]}/{quote}"
    return None


def base_asset(sym: str) -> str:
    parts = split_ccxt_symbol(sym)
    return parts[0].upper() if parts else sym.upper()
