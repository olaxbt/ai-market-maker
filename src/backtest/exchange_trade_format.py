"""Exchange-shaped trade rows for analysis and future CEX/DEX adapters.

Spot user-trades shape follows Binance ``GET /api/v3/myTrades`` field names (see Binance API docs).
Values are JSON-serializable; numeric fields use strings where Binance returns strings.

Simulation-only fields live under ``_sim`` so imports can strip them when posting to a venue.
"""

from __future__ import annotations

import hashlib
from typing import Any


def ccxt_symbol_to_binance(symbol: str) -> str:
    """``BTC/USDT`` → ``BTCUSDT`` (compact, no separator)."""
    return str(symbol).replace("/", "").upper()


def quote_asset_from_ccxt(symbol: str) -> str:
    """Quote asset for commission (e.g. ``BTC/USDT`` → ``USDT``)."""
    s = str(symbol)
    if "/" in s:
        return s.split("/")[-1].upper()
    return "USDT"


def synthetic_trade_and_order_id(run_id: str, step: int, symbol: str, seq: int) -> tuple[int, int]:
    """Deterministic pseudo-ids (not global exchange ids; stable for a given backtest run)."""
    blob = f"{run_id}|{step}|{symbol}|{seq}".encode()
    h = hashlib.sha256(blob).digest()
    trade_id = int.from_bytes(h[:8], "big", signed=False) % (10**15)
    order_id = int.from_bytes(h[8:16], "big", signed=False) % (10**15)
    if trade_id == 0:
        trade_id = 1
    if order_id == 0:
        order_id = 1
    return trade_id, order_id


def build_binance_my_trades_row(
    *,
    symbol_ccxt: str,
    side: str,
    qty: float,
    price: float,
    commission: float,
    commission_asset: str,
    time_ms: int,
    is_maker: bool,
    run_id: str,
    step: int,
    seq: int,
    sim_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One row shaped like Binance spot ``myTrades`` (+ optional ``_sim``)."""

    def _fmt_num(x: float) -> str:
        xf = float(x)
        if xf == 0.0:
            return "0"
        # Avoid serializing tiny-but-nonzero fills as "0" due to fixed decimals.
        if abs(xf) < 1e-8:
            return f"{xf:.12g}"
        return f"{xf:.8f}".rstrip("0").rstrip(".")

    sym = ccxt_symbol_to_binance(symbol_ccxt)
    side_l = str(side).lower()
    is_buyer = side_l == "buy"
    q = float(qty)
    p = float(price)
    quote = q * p
    tid, oid = synthetic_trade_and_order_id(run_id, step, symbol_ccxt, seq)
    row: dict[str, Any] = {
        "symbol": sym,
        "id": tid,
        "orderId": oid,
        "orderListId": -1,
        "price": _fmt_num(p),
        "qty": _fmt_num(q),
        "quoteQty": _fmt_num(quote),
        "commission": _fmt_num(float(commission)),
        "commissionAsset": commission_asset,
        "time": int(time_ms),
        "isBuyer": bool(is_buyer),
        "isMaker": bool(is_maker),
        "isBestMatch": True,
    }
    if sim_meta:
        row["_sim"] = {
            "venue": "sim",
            "run_id": run_id,
            "step": step,
            "ccxt_symbol": symbol_ccxt,
            **sim_meta,
        }
    return row


TRADES_CSV_COLUMNS = [
    "symbol",
    "id",
    "orderId",
    "orderListId",
    "price",
    "qty",
    "quoteQty",
    "commission",
    "commissionAsset",
    "time",
    "isBuyer",
    "isMaker",
    "isBestMatch",
]


def trade_row_to_csv_line(row: dict[str, Any]) -> str:
    """CSV row for core exchange columns (no ``_sim``)."""
    import csv
    import io

    core = {k: row.get(k) for k in TRADES_CSV_COLUMNS}
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=TRADES_CSV_COLUMNS, extrasaction="ignore")
    w.writerow(core)  # type: ignore[arg-type]
    return buf.getvalue().rstrip("\r\n")


def trades_to_csv(trades: list[dict[str, Any]]) -> str:
    """Full CSV text with header."""
    if not trades:
        return ",".join(TRADES_CSV_COLUMNS) + "\n"
    header = ",".join(TRADES_CSV_COLUMNS) + "\n"
    body = "\n".join(trade_row_to_csv_line(r) for r in trades) + "\n"
    return header + body


def normalize_trade_row_for_api(row: dict[str, Any]) -> dict[str, Any]:
    """Map persisted exchange-shaped rows to the HTTP/API contract (superset, non-destructive).

    Ledger lines follow Binance ``myTrades`` (``isBuyer``, ``time``, string numerics, ``_sim``).
    The API also exposes ``side``, ``step``, ``ts_ms``, and ``fee_usd`` so clients and charts
    stay stable. Rows that already include those keys are unchanged.
    """
    out = dict(row)
    sim = row.get("_sim") if isinstance(row.get("_sim"), dict) else {}
    if "side" not in out and "isBuyer" in row:
        out["side"] = "buy" if row.get("isBuyer") else "sell"
    if "step" not in out and sim.get("step") is not None:
        out["step"] = int(sim["step"])
    if "ts_ms" not in out and row.get("time") is not None:
        out["ts_ms"] = int(row["time"])
    if "fee_usd" not in out:
        c = row.get("commission")
        if c is not None:
            try:
                out["fee_usd"] = float(c)
            except (TypeError, ValueError):
                pass
    return out


def trade_row_fee_usd(tr: dict[str, Any]) -> float:
    """Fee in quote terms for analytics (supports Binance ``commission`` or legacy ``fee_usd``)."""
    if tr.get("fee_usd") is not None:
        try:
            return float(tr["fee_usd"])
        except (TypeError, ValueError):
            pass
    c = tr.get("commission")
    if c is None:
        return 0.0
    try:
        return float(c)
    except (TypeError, ValueError):
        return 0.0


def trade_row_side(tr: dict[str, Any]) -> str:
    if tr.get("side"):
        return str(tr["side"])
    if "isBuyer" in tr:
        return "buy" if tr.get("isBuyer") else "sell"
    return ""


def trade_row_symbol_for_analytics(tr: dict[str, Any]) -> str:
    """Prefer CCXT ``BASE/QUOTE`` from ``_sim`` when present (stable-pair detection)."""
    sim = tr.get("_sim") if isinstance(tr.get("_sim"), dict) else {}
    ccxt_sym = sim.get("ccxt_symbol")
    if isinstance(ccxt_sym, str) and ccxt_sym:
        return ccxt_sym
    return str(tr.get("symbol") or "")


__all__ = [
    "TRADES_CSV_COLUMNS",
    "build_binance_my_trades_row",
    "ccxt_symbol_to_binance",
    "normalize_trade_row_for_api",
    "quote_asset_from_ccxt",
    "synthetic_trade_and_order_id",
    "trade_row_fee_usd",
    "trade_row_side",
    "trade_row_symbol_for_analytics",
    "trade_row_to_csv_line",
    "trades_to_csv",
]
