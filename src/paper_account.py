"""Paper trading account: **spot** (full-cash) and **USDT-margined perp** (initial margin).

Perp model (mock, common in agentic demos):
- Opening a position posts **initial margin = notional / leverage** (+ fees), not full notional.
- ``qty_signed``: positive = long, negative = short.
- Closing releases margin + realized PnL (linear: PnL = qty * (exit - entry) for long, opposite for short).

This aligns paper mode with a simplified perpetual contract book; not exchange-identical (no funding,
liquidation engine, or cross/isolated margin), but comparable across runs for evaluation.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SpotPosition:
    symbol: str
    qty: float = 0.0
    avg_entry: float = 0.0


@dataclass
class PerpPosition:
    symbol: str
    #: Positive = long, negative = short (base asset qty).
    qty_signed: float = 0.0
    avg_entry: float = 0.0
    leverage: float = 1.0
    margin_locked_usdt: float = 0.0


@dataclass
class PaperAccount:
    account_id: str = "default"
    cash_usdt: float = 0.0
    spot_positions: dict[str, SpotPosition] = field(default_factory=dict)
    perp_positions: dict[str, PerpPosition] = field(default_factory=dict)
    realized_pnl_usdt: float = 0.0
    updated_ts: int = 0

    def snapshot(self, *, instrument: str = "spot") -> dict[str, Any]:
        inst = str(instrument or "spot").lower()
        out: dict[str, Any] = {
            "account_id": self.account_id,
            "instrument": inst,
            "cash_usdt": round(float(self.cash_usdt), 8),
            "realized_pnl_usdt": round(float(self.realized_pnl_usdt), 8),
            "spot_positions": [
                {
                    "symbol": p.symbol,
                    "qty": round(float(p.qty), 12),
                    "avg_entry": round(float(p.avg_entry), 8),
                }
                for p in sorted(self.spot_positions.values(), key=lambda x: x.symbol)
                if abs(float(p.qty)) > 1e-12
            ],
            "perp_positions": [
                {
                    "symbol": p.symbol,
                    "qty_signed": round(float(p.qty_signed), 12),
                    "avg_entry": round(float(p.avg_entry), 8),
                    "leverage": round(float(p.leverage), 4),
                    "margin_locked_usdt": round(float(p.margin_locked_usdt), 8),
                }
                for p in sorted(self.perp_positions.values(), key=lambda x: x.symbol)
                if abs(float(p.qty_signed)) > 1e-12
            ],
            # Legacy single list: primary book view for the active instrument mode.
            "positions": (
                [
                    {
                        "symbol": p.symbol,
                        "qty": round(float(p.qty), 12),
                        "avg_entry": round(float(p.avg_entry), 8),
                    }
                    for p in sorted(self.spot_positions.values(), key=lambda x: x.symbol)
                    if abs(float(p.qty)) > 1e-12
                ]
                if inst == "spot"
                else [
                    {
                        "symbol": p.symbol,
                        "qty_signed": round(float(p.qty_signed), 12),
                        "avg_entry": round(float(p.avg_entry), 8),
                        "leverage": round(float(p.leverage), 4),
                        "margin_locked_usdt": round(float(p.margin_locked_usdt), 8),
                    }
                    for p in sorted(self.perp_positions.values(), key=lambda x: x.symbol)
                    if abs(float(p.qty_signed)) > 1e-12
                ]
            ),
            "updated_ts": int(self.updated_ts),
        }
        return out


def _account_paths(*, runs_dir: Path, account_id: str) -> tuple[Path, Path]:
    base = runs_dir / "paper"
    acct = base / f"{account_id}.account.json"
    trades = base / f"{account_id}.trades.jsonl"
    return acct, trades


def _parse_spot_row(row: dict[str, Any]) -> SpotPosition | None:
    sym = str(row.get("symbol") or "")
    if not sym:
        return None
    return SpotPosition(
        symbol=sym, qty=float(row.get("qty") or 0.0), avg_entry=float(row.get("avg_entry") or 0.0)
    )


def _parse_perp_row(row: dict[str, Any]) -> PerpPosition | None:
    sym = str(row.get("symbol") or "")
    if not sym:
        return None
    return PerpPosition(
        symbol=sym,
        qty_signed=float(row.get("qty_signed") or row.get("qty") or 0.0),
        avg_entry=float(row.get("avg_entry") or 0.0),
        leverage=max(1.0, float(row.get("leverage") or 1.0)),
        margin_locked_usdt=float(row.get("margin_locked_usdt") or 0.0),
    )


def load_or_init_account(
    *,
    runs_dir: Path,
    account_id: str = "default",
    start_usdt: float,
) -> PaperAccount:
    acct_path, _trades_path = _account_paths(runs_dir=runs_dir, account_id=account_id)
    try:
        if acct_path.exists():
            data = json.loads(acct_path.read_text(encoding="utf-8"))
            pa = PaperAccount(
                account_id=str(data.get("account_id") or account_id),
                cash_usdt=float(data.get("cash_usdt") or 0.0),
                realized_pnl_usdt=float(data.get("realized_pnl_usdt") or 0.0),
                updated_ts=int(data.get("updated_ts") or 0),
            )
            if isinstance(data.get("spot_positions"), list):
                for row in data["spot_positions"]:
                    if isinstance(row, dict):
                        p = _parse_spot_row(row)
                        if p and abs(p.qty) > 1e-12:
                            pa.spot_positions[p.symbol] = p
            if isinstance(data.get("perp_positions"), list):
                for row in data["perp_positions"]:
                    if isinstance(row, dict):
                        p = _parse_perp_row(row)
                        if p and abs(p.qty_signed) > 1e-12:
                            pa.perp_positions[p.symbol] = p
            # Legacy: only ``positions`` (spot book).
            if (
                not pa.spot_positions
                and not pa.perp_positions
                and isinstance(data.get("positions"), list)
            ):
                for row in data["positions"]:
                    if isinstance(row, dict):
                        p = _parse_spot_row(row)
                        if p and abs(p.qty) > 1e-12:
                            pa.spot_positions[p.symbol] = p
            return pa
    except Exception:
        pass

    pa = PaperAccount(
        account_id=account_id, cash_usdt=float(start_usdt), updated_ts=int(time.time())
    )
    save_account(runs_dir=runs_dir, account=pa)
    return pa


def save_account(*, runs_dir: Path, account: PaperAccount) -> None:
    acct_path, _trades_path = _account_paths(runs_dir=runs_dir, account_id=account.account_id)
    acct_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "account_id": account.account_id,
        "cash_usdt": float(account.cash_usdt),
        "realized_pnl_usdt": float(account.realized_pnl_usdt),
        "spot_positions": [asdict(p) for p in account.spot_positions.values()],
        "perp_positions": [asdict(p) for p in account.perp_positions.values()],
        "updated_ts": int(account.updated_ts),
    }
    acct_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def append_trade(
    *,
    runs_dir: Path,
    account_id: str,
    trade: dict[str, Any],
) -> None:
    _acct_path, trades_path = _account_paths(runs_dir=runs_dir, account_id=account_id)
    trades_path.parent.mkdir(parents=True, exist_ok=True)
    with trades_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(trade, default=str) + "\n")


def apply_spot_fill(
    *,
    account: PaperAccount,
    symbol: str,
    side: str,
    qty: float,
    price: float,
    fee_bps: float,
    ts: int | None = None,
) -> dict[str, Any]:
    """Apply a spot fill and return a trade record."""
    ts_i = int(ts or time.time())
    sym = str(symbol)
    s = str(side).lower()
    q = float(qty)
    px = float(price)
    if q <= 0 or px <= 0 or s not in ("buy", "sell"):
        raise ValueError("invalid fill")

    fee_rate = max(0.0, float(fee_bps)) / 10_000.0
    notional = q * px
    fee = notional * fee_rate

    pos = account.spot_positions.get(sym) or SpotPosition(symbol=sym)
    prev_qty = float(pos.qty)
    prev_avg = float(pos.avg_entry)

    realized_pnl = 0.0
    if s == "buy":
        total_cost = notional + fee
        if account.cash_usdt + 1e-9 < total_cost:
            raise ValueError("insufficient cash")
        account.cash_usdt -= total_cost
        new_qty = prev_qty + q
        if new_qty > 1e-12:
            pos.avg_entry = (prev_qty * prev_avg + q * px) / new_qty if prev_qty > 1e-12 else px
        pos.qty = new_qty
    else:
        if prev_qty + 1e-12 < q:
            raise ValueError("insufficient position qty")
        proceeds = notional - fee
        account.cash_usdt += proceeds
        realized_pnl = (px - prev_avg) * q
        account.realized_pnl_usdt += realized_pnl
        pos.qty = prev_qty - q
        if pos.qty <= 1e-12:
            pos.qty = 0.0
            pos.avg_entry = 0.0

    if abs(pos.qty) > 1e-12:
        account.spot_positions[sym] = pos
    elif sym in account.spot_positions:
        account.spot_positions.pop(sym, None)

    account.updated_ts = ts_i

    return {
        "instrument": "spot",
        "ts": ts_i,
        "account_id": account.account_id,
        "symbol": sym,
        "side": s,
        "qty": round(q, 12),
        "price": round(px, 8),
        "notional_usdt": round(notional, 8),
        "fee_usdt": round(fee, 8),
        "realized_pnl_usdt": round(realized_pnl, 8),
        "cash_usdt_after": round(float(account.cash_usdt), 8),
        "position_qty_after": round(
            float(account.spot_positions.get(sym).qty if sym in account.spot_positions else 0.0), 12
        ),
        "position_avg_entry_after": round(
            float(
                account.spot_positions.get(sym).avg_entry if sym in account.spot_positions else 0.0
            ),
            8,
        ),
    }


def apply_perp_fill(
    *,
    account: PaperAccount,
    symbol: str,
    side: str,
    qty: float,
    price: float,
    fee_bps: float,
    leverage: float,
    ts: int | None = None,
) -> dict[str, Any]:
    """USDT-linear perp: post initial margin = notional/leverage (+ fees)."""
    ts_i = int(ts or time.time())
    sym = str(symbol)
    s = str(side).lower()
    q = float(qty)
    px = float(price)
    lev = max(1.0, float(leverage))
    if q <= 0 or px <= 0 or s not in ("buy", "sell"):
        raise ValueError("invalid fill")

    fee_rate = max(0.0, float(fee_bps)) / 10_000.0
    notional = q * px
    fee = notional * fee_rate

    pos = account.perp_positions.get(sym) or PerpPosition(symbol=sym, leverage=lev)
    pos.leverage = lev
    q_before = float(pos.qty_signed)
    avg = float(pos.avg_entry)
    margin = float(pos.margin_locked_usdt)

    realized = 0.0

    def _release_margin(frac: float) -> float:
        nonlocal margin
        if frac <= 1e-18:
            return 0.0
        rel = margin * min(1.0, frac)
        margin -= rel
        return rel

    if s == "buy":
        if q_before >= -1e-12:
            # Add to long or open long from flat.
            im = notional / lev
            if account.cash_usdt + 1e-9 < im + fee:
                raise ValueError("insufficient cash for initial margin")
            account.cash_usdt -= im + fee
            new_q = q_before + q
            if abs(q_before) <= 1e-12:
                avg = px
            else:
                avg = (avg * q_before + q * px) / new_q
            pos.qty_signed = new_q
            pos.avg_entry = avg
            pos.margin_locked_usdt = margin + im
        else:
            # Cover short: q_before < 0
            cover = min(q, abs(q_before))
            short_avg = avg
            not_c = cover * px
            fee_c = not_c * fee_rate
            rel = _release_margin(cover / abs(q_before)) if q_before != 0 else 0.0
            pnl = (short_avg - px) * cover
            realized = pnl
            account.realized_pnl_usdt += pnl
            account.cash_usdt += rel + pnl - fee_c
            pos.qty_signed = q_before + cover
            pos.margin_locked_usdt = margin
            if abs(pos.qty_signed) <= 1e-12:
                pos.qty_signed = 0.0
                pos.avg_entry = 0.0
                pos.margin_locked_usdt = 0.0
            rem = q - cover
            if rem > 1e-12:
                # Open / add long with remainder
                im2 = (rem * px) / lev
                fee2 = (rem * px) * fee_rate
                if account.cash_usdt + 1e-9 < im2 + fee2:
                    raise ValueError("insufficient cash for flip remainder")
                account.cash_usdt -= im2 + fee2
                new_q = float(pos.qty_signed) + rem
                if float(pos.qty_signed) <= 1e-12:
                    pos.avg_entry = px
                else:
                    pos.avg_entry = (pos.avg_entry * float(pos.qty_signed) + rem * px) / new_q
                pos.qty_signed = new_q
                pos.margin_locked_usdt = float(pos.margin_locked_usdt) + im2
    else:
        # sell
        if q_before <= 1e-12:
            # Open short from flat
            im = notional / lev
            if account.cash_usdt + 1e-9 < im + fee:
                raise ValueError("insufficient cash for initial margin")
            account.cash_usdt -= im + fee
            new_q = q_before - q
            pos.qty_signed = new_q
            pos.avg_entry = px
            pos.margin_locked_usdt = margin + im
        elif q_before > 0:
            # Reduce long
            sell_q = min(q, q_before)
            rel = _release_margin(sell_q / q_before) if q_before > 0 else 0.0
            fee_s = sell_q * px * fee_rate
            pnl = (px - avg) * sell_q
            realized = pnl
            account.realized_pnl_usdt += pnl
            account.cash_usdt += rel + pnl - fee_s
            pos.qty_signed = q_before - sell_q
            pos.margin_locked_usdt = margin
            if abs(pos.qty_signed) <= 1e-12:
                pos.qty_signed = 0.0
                pos.avg_entry = 0.0
                pos.margin_locked_usdt = 0.0
            rem = q - sell_q
            if rem > 1e-12 and pos.qty_signed <= 1e-12:
                im2 = (rem * px) / lev
                fee2 = (rem * px) * fee_rate
                if account.cash_usdt + 1e-9 < im2 + fee2:
                    raise ValueError("insufficient cash for short leg")
                account.cash_usdt -= im2 + fee2
                pos.qty_signed = -rem
                pos.avg_entry = px
                pos.margin_locked_usdt = im2
        else:
            # Add to short
            im = notional / lev
            if account.cash_usdt + 1e-9 < im + fee:
                raise ValueError("insufficient cash for initial margin")
            account.cash_usdt -= im + fee
            ab = abs(q_before)
            new_ab = ab + q
            pos.avg_entry = (avg * ab + q * px) / new_ab
            pos.qty_signed = q_before - q
            pos.margin_locked_usdt = margin + im

    if abs(pos.qty_signed) > 1e-12:
        account.perp_positions[sym] = pos
    elif sym in account.perp_positions:
        account.perp_positions.pop(sym, None)

    account.updated_ts = ts_i

    return {
        "instrument": "perp",
        "leverage": lev,
        "ts": ts_i,
        "account_id": account.account_id,
        "symbol": sym,
        "side": s,
        "qty": round(q, 12),
        "price": round(px, 8),
        "notional_usdt": round(notional, 8),
        "fee_usdt": round(fee, 8),
        "realized_pnl_usdt": round(realized, 8),
        "cash_usdt_after": round(float(account.cash_usdt), 8),
        "perp_qty_signed_after": round(
            float(
                account.perp_positions.get(sym).qty_signed if sym in account.perp_positions else 0.0
            ),
            12,
        ),
        "perp_avg_entry_after": round(
            float(
                account.perp_positions.get(sym).avg_entry if sym in account.perp_positions else 0.0
            ),
            8,
        ),
        "margin_locked_usdt_after": round(
            float(
                account.perp_positions.get(sym).margin_locked_usdt
                if sym in account.perp_positions
                else 0.0
            ),
            8,
        ),
    }


# Back-compat alias
Position = SpotPosition

__all__ = [
    "PaperAccount",
    "PerpPosition",
    "Position",
    "SpotPosition",
    "append_trade",
    "apply_perp_fill",
    "apply_spot_fill",
    "load_or_init_account",
    "save_account",
]
