from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Literal, Optional

from config.app_settings import load_app_settings
from config.fund_policy import load_fund_policy
from config.nexus_env import load_nexus_data_base_url
from paper_account import (
    append_trade,
    apply_perp_fill,
    apply_spot_fill,
    load_or_init_account,
    save_account,
)

OrderSide = Literal["buy", "sell"]
OrderType = Literal["market", "limit"]


@dataclass(frozen=True)
class NexusAdapterConfig:
    mode: str = "paper"  # backtest|paper|live
    venue: str = "binance"
    testnet: bool = True
    #: When set, future implementations prefer OLAXBT Nexus data feeds for depth / quant.
    nexus_data_base_url: Optional[str] = None


class NexusAdapter:
    """A minimal Nexus tool surface.

    This starts as a deterministic/mockable adapter so:
    - agents can call `nexus.*` tools without depending on ccxt directly
    - we can swap in real `nexus_trading_engine` / `nexus_wallet_hub` later
    """

    def __init__(self, config: NexusAdapterConfig | None = None):
        self.config = config or NexusAdapterConfig()

    # ---- Tool surface (stable names in openclaw/manifest.json) -------------

    def get_portfolio_health(self, *, account_id: str | None = None) -> Dict[str, Any]:
        # In paper mode, expose our local paper account snapshot.
        start_usdt = float(load_app_settings().paper.start_usdt)
        fp = load_fund_policy()
        max_lev = max(1.0, float(fp.max_leverage))
        aid = account_id or "default"
        runs_dir = Path(".runs")
        try:
            acct = load_or_init_account(runs_dir=runs_dir, account_id=aid, start_usdt=start_usdt)
            s = load_app_settings()
            inst = str(s.paper.instrument or "spot").lower()
            snap = acct.snapshot(instrument=inst)
        except Exception:
            snap = {
                "account_id": aid,
                "instrument": "spot",
                "cash_usdt": start_usdt,
                "realized_pnl_usdt": 0.0,
                "positions": [],
                "updated_ts": int(time.time()),
            }
        return {
            "account_id": account_id or "default",
            "ts": int(time.time()),
            "mode": self.config.mode,
            "balances": {"USDT": float(snap.get("cash_usdt") or start_usdt)},
            "positions": list(snap.get("positions") or []),
            "risk_caps": {
                # Simple policy-based cap: gross notional <= equity * leverage.
                "max_notional_usd": round(float(start_usdt) * max_lev, 2),
                "max_leverage": max_lev,
            },
            "paper_account": snap,
        }

    def fetch_market_depth(self, *, symbol: str, limit: int = 5) -> Dict[str, Any]:
        # Toy book until Nexus HTTP client is wired for `nexus_data_base_url`.
        #
        # Important: downstream LLM nodes consume this tool output. Make the mock nature explicit
        # so the model doesn't treat placeholder depth as real market liquidity.
        mid = 100.0
        bids = [[mid - i * 0.5, 1.0 + i * 0.1] for i in range(1, limit + 1)]
        asks = [[mid + i * 0.5, 1.0 + i * 0.1] for i in range(1, limit + 1)]
        return {
            "symbol": symbol,
            "bids": bids,
            "asks": asks,
            "ts": int(time.time()),
            "source": "mock",
            "is_mock": True,
            "note": "Placeholder depth from NexusAdapter (not a real order book).",
        }

    def place_smart_order(
        self,
        *,
        symbol: str,
        side: OrderSide,
        qty: float,
        order_type: OrderType = "market",
        price: Optional[float] = None,
        post_only: bool = False,
        max_slippage_bps: Optional[float] = None,
        client_order_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        # Mock order: safe in all environments. In paper mode we also book fills locally.
        if qty <= 0:
            return {"status": "rejected", "reason": "qty must be > 0"}
        if order_type == "limit" and price is None:
            return {"status": "rejected", "reason": "limit orders require price"}

        base = {
            "status": "accepted",
            "mode": self.config.mode,
            "venue": self.config.venue,
            "symbol": symbol,
            "side": side,
            "qty": float(qty),
            "type": order_type,
            "price": float(price) if price is not None else None,
            "post_only": bool(post_only),
            "max_slippage_bps": float(max_slippage_bps) if max_slippage_bps is not None else None,
            "client_order_id": client_order_id,
        }

        # Paper booking (spot-only). If no price is provided for market, we cannot book deterministically.
        if self.config.mode == "paper":
            s = load_app_settings()
            if not s.paper.trading_enabled:
                return {**base, "paper": {"booked": False, "reason": "paper.trading_enabled=false"}}
            if price is None:
                return {**base, "paper": {"booked": False, "reason": "missing price"}}
            runs_dir = Path(".runs")
            aid = "default"
            acct = load_or_init_account(
                runs_dir=runs_dir, account_id=aid, start_usdt=float(s.paper.start_usdt)
            )
            inst = str(s.paper.instrument or "spot").lower()
            fp = load_fund_policy()
            lev = min(max(1.0, float(s.paper.leverage)), max(1.0, float(fp.max_leverage)))
            try:
                if inst == "perp":
                    trade = apply_perp_fill(
                        account=acct,
                        symbol=str(symbol),
                        side=str(side),
                        qty=float(qty),
                        price=float(price),
                        fee_bps=float(s.paper.fee_bps),
                        leverage=float(lev),
                    )
                else:
                    trade = apply_spot_fill(
                        account=acct,
                        symbol=str(symbol),
                        side=str(side),
                        qty=float(qty),
                        price=float(price),
                        fee_bps=float(s.paper.fee_bps),
                    )
            except Exception as e:
                return {**base, "paper": {"booked": False, "reason": str(e)}}
            append_trade(runs_dir=runs_dir, account_id=aid, trade={**trade, "order": base})
            save_account(runs_dir=runs_dir, account=acct)
            return {
                **base,
                "paper": {
                    "booked": True,
                    "trade": trade,
                    "account": acct.snapshot(instrument=inst),
                },
            }

        return base


_adapter: NexusAdapter | None = None


def get_nexus_adapter() -> NexusAdapter:
    global _adapter
    if _adapter is None:
        mode = (os.getenv("MODE") or "paper").strip().lower()
        _adapter = NexusAdapter(
            NexusAdapterConfig(
                mode=mode,
                nexus_data_base_url=load_nexus_data_base_url(),
            )
        )
    return _adapter


def set_nexus_adapter(adapter: NexusAdapter | None) -> None:
    global _adapter
    _adapter = adapter


__all__ = [
    "NexusAdapter",
    "NexusAdapterConfig",
    "get_nexus_adapter",
    "set_nexus_adapter",
]
