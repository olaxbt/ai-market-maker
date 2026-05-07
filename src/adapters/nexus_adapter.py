from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Literal, Optional

from adapters.exchange_protocol import ExchangeOrderResult
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

    # ------------------------------------------------------------------
    # ExchangeAdapter Protocol compatibility methods
    # ------------------------------------------------------------------

    def place_order(
        self,
        *,
        symbol: str,
        side: str,
        qty: float,
        order_type: str,
        price: float | None,
        client_order_id: str | None,
    ) -> ExchangeOrderResult:
        """Bridge over place_smart_order() to satisfy ExchangeAdapter Protocol."""
        now = int(time.time())
        raw = self.place_smart_order(
            symbol=symbol,
            side=side,
            qty=qty,
            order_type=order_type,
            price=price,
            client_order_id=client_order_id,
        )
        status = raw.get("status", "unknown")
        if status == "accepted":
            mapped = "accepted"
        elif status == "rejected":
            mapped = "rejected"
        else:
            mapped = "unknown"
        kwargs: dict[str, Any] = {
            "status": mapped,
            "exchange_order_id": None,
            "client_order_id": client_order_id,
            "symbol": symbol,
            "side": side,
            "qty": float(qty),
            "price": float(price) if price is not None else None,
            "filled_qty": 0.0,
            "ts": now,
            "raw": raw,
        }
        if mapped == "rejected":
            kwargs["error"] = str(raw.get("reason", "rejected"))
        return ExchangeOrderResult(**kwargs)

    def cancel_order(
        self,
        *,
        symbol: str,
        exchange_order_id: str,
    ) -> ExchangeOrderResult:
        """Paper adapter: acknowledge cancel locally, no exchange call."""
        return ExchangeOrderResult(
            status="cancelled",
            exchange_order_id=exchange_order_id,
            client_order_id=None,
            symbol=symbol,
            side="",
            qty=0.0,
            price=None,
            filled_qty=0.0,
            ts=int(time.time()),
            raw={},
        )

    def get_order_status(
        self,
        *,
        symbol: str,
        exchange_order_id: str,
    ) -> ExchangeOrderResult:
        """Paper adapter: all tracked orders are considered accepted."""
        return ExchangeOrderResult(
            status="accepted",
            exchange_order_id=exchange_order_id,
            client_order_id=None,
            symbol=symbol,
            side="",
            qty=0.0,
            price=None,
            filled_qty=0.0,
            ts=int(time.time()),
            raw={},
        )


class OmsNexusAdapter:
    """Routes place_smart_order() through Oms lifecycle. Drop-in replacement for NexusAdapter.

    Used when AI_MARKET_MAKER_EXECUTION_ENGINE=oms. main.py requires no changes.
    get_portfolio_health() and fetch_market_depth() delegate to the wrapped exchange adapter.
    """

    def __init__(self, *, oms: Any, exchange_adapter: Any) -> None:
        self._oms = oms
        self._exchange = exchange_adapter

    def place_smart_order(
        self,
        *,
        symbol: str,
        side: str,
        qty: float,
        order_type: str = "market",
        price: Optional[float] = None,
        post_only: bool = False,
        max_slippage_bps: Optional[float] = None,
        client_order_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        nonce = str(int(time.time() * 1_000_000))
        order = self._oms.submit_order(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=qty,
            price=price,
            strategy="oms",
            run_id="default",
            nonce=nonce,
            client_order_id=client_order_id,
        )
        return {
            "status": order.state.value,
            "symbol": symbol,
            "side": side,
            "qty": float(qty),
            "price": float(price) if price is not None else None,
            "type": order_type,
            "mode": "oms",
            "venue": "oms",
            "client_order_id": order.client_order_id,
            "exchange_order_id": order.venue_order_id,
            "oms_state": order.state.value,
        }

    def get_portfolio_health(self, *, account_id: Optional[str] = None) -> Dict[str, Any]:
        return self._exchange.get_portfolio_health(account_id=account_id)

    def fetch_market_depth(self, *, symbol: str, limit: int = 5) -> Dict[str, Any]:
        return self._exchange.fetch_market_depth(symbol=symbol, limit=limit)


_adapter: Any = None


def get_nexus_adapter() -> Any:
    """Return the singleton execution adapter.

    Default (AI_MARKET_MAKER_EXECUTION_ENGINE=legacy): NexusAdapter paper path, unchanged.
    Opt-in (AI_MARKET_MAKER_EXECUTION_ENGINE=oms): OmsNexusAdapter routes through OMS.
    """
    global _adapter
    if _adapter is not None:
        return _adapter

    from config.execution_engine import ExecutionEngine, load_execution_engine

    engine = load_execution_engine()

    if engine == ExecutionEngine.LEGACY:
        mode = (os.getenv("MODE") or "paper").strip().lower()
        _adapter = NexusAdapter(
            NexusAdapterConfig(mode=mode, nexus_data_base_url=load_nexus_data_base_url())
        )
        return _adapter

    # OMS path — requires explicit AI_MARKET_MAKER_EXECUTION_ENGINE=oms
    from config.exchange_env import load_exchange_config
    from oms.oms import Oms

    cfg = load_exchange_config()

    if cfg.exchange_name == "paper":
        mode = (os.getenv("MODE") or "paper").strip().lower()
        inner = NexusAdapter(
            NexusAdapterConfig(mode=mode, nexus_data_base_url=load_nexus_data_base_url())
        )
        oms = Oms(adapter=inner, dry_run=cfg.dry_run)
        _adapter = OmsNexusAdapter(oms=oms, exchange_adapter=inner)

    elif cfg.exchange_name == "hyperliquid":
        # Raise before touching SDK import so the error is clear regardless of SDK presence
        if not cfg.dry_run:
            raise RuntimeError(
                "Hyperliquid live SDK execution is not implemented in this PR. "
                "Set HYPERLIQUID_DRY_RUN=1 to use dry-run mode, or use exchange=paper."
            )
        from adapters.hyperliquid_adapter import HyperliquidAdapter

        hl_adapter = HyperliquidAdapter(config=cfg)
        oms = Oms(adapter=hl_adapter)
        _adapter = OmsNexusAdapter(oms=oms, exchange_adapter=hl_adapter)

    else:
        raise RuntimeError(
            f"Unsupported exchange {cfg.exchange_name!r} for OMS engine. "
            "Supported: 'paper', 'hyperliquid' (with HYPERLIQUID_DRY_RUN=1)."
        )

    return _adapter


def set_nexus_adapter(adapter: Any) -> None:
    global _adapter
    _adapter = adapter


__all__ = [
    "NexusAdapter",
    "NexusAdapterConfig",
    "OmsNexusAdapter",
    "get_nexus_adapter",
    "set_nexus_adapter",
]
