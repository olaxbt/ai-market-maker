"""Futu OpenD exchange adapter.

Implements the ExchangeAdapter protocol for Hong Kong and US stock data
via the Futu OpenD gateway (futu-api Python SDK).

Three classes:
  - FakeFutuClient  — pure-Python test double; no OpenD required
  - _SdkFutuClient  — lazy-imports real futu-api SDK; only used in production
  - FutuAdapter     — satisfies ExchangeAdapter Protocol; injectable client

OpenD is a local TCP gateway (default 127.0.0.1:11111 for quote, 11112 for trade).
Production use requires OpenD running locally or on a reachable host.

Environment variables (optional, sensible defaults):
  FUTU_OPEND_HOST       — OpenD host (default: 127.0.0.1)
  FUTU_OPEND_QUOTE_PORT — OpenD quote port (default: 11111)
  FUTU_OPEND_TRADE_PORT — OpenD trade port (default: 11112)
  FUTU_UNLOCK_PWD       — Trade unlock password (optional, for live trading)
  FUTU_PWD_MD5          — Whether unlock password is MD5-hashed (default: false)
  FUTU_DRY_RUN          — If set to 1, never send real orders (default: 0)
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any

from adapters.exchange_protocol import ExchangeOrderResult
from config.exchange_env import ExchangeConfig

# ---------------------------------------------------------------------------
# Default OpenD ports
# ---------------------------------------------------------------------------
_DEFAULT_QUOTE_PORT = 11111
_DEFAULT_TRADE_PORT = 11112

# ---------------------------------------------------------------------------
# Helper: normalize HK stock symbols
# ---------------------------------------------------------------------------


def normalize_futu_symbol(symbol: str) -> str:
    """Normalize a symbol to Futu convention.

    - HK stocks: '0700.HK' or '700.HK' → 'HK.00700'
    - US stocks: 'AAPL.US' or 'AAPL' → 'US.AAPL'
    - Crypto: 'BTC/USDT' → keep as-is for futu crypto
    """
    s = symbol.strip().upper()

    # Already prefixed
    if s.startswith("HK.") or s.startswith("US."):
        return s

    # Explicit suffix: 0700.HK, 700.HK → HK.00700
    if s.endswith(".HK"):
        raw = s[:-3].strip()
        padded = raw.zfill(5)
        return f"HK.{padded}"

    if s.endswith(".US"):
        raw = s[:-3].strip()
        return f"US.{raw}"

    # Numeric → assume HK stock
    raw_num = s.replace("0", "")
    if raw_num.isdigit():
        padded = s.zfill(5)
        return f"HK.{padded}"

    # Alphanumeric without dot → assume US stock
    return f"US.{s}"


def _detect_market(symbol: str) -> str:
    """Return 'hk', 'us', or 'crypto' for a symbol."""
    s = symbol.strip().upper()
    if s.startswith("HK."):
        return "hk"
    if s.startswith("US."):
        return "us"
    return "crypto"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class FutuEnvConfig:
    """Futu OpenD connection configuration."""

    host: str = "127.0.0.1"
    quote_port: int = _DEFAULT_QUOTE_PORT
    trade_port: int = _DEFAULT_TRADE_PORT
    unlock_pwd: str | None = None
    pwd_md5: bool = False
    dry_run: bool = False

    @classmethod
    def from_env(cls) -> FutuEnvConfig:
        return cls(
            host=os.getenv("FUTU_OPEND_HOST", "127.0.0.1"),
            quote_port=int(os.getenv("FUTU_OPEND_QUOTE_PORT", str(_DEFAULT_QUOTE_PORT))),
            trade_port=int(os.getenv("FUTU_OPEND_TRADE_PORT", str(_DEFAULT_TRADE_PORT))),
            unlock_pwd=os.getenv("FUTU_UNLOCK_PWD") or None,
            pwd_md5=str(os.getenv("FUTU_PWD_MD5", "0")).strip().lower() in ("1", "true", "yes"),
            dry_run=str(os.getenv("FUTU_DRY_RUN", "0")).strip().lower() in ("1", "true", "yes"),
        )


# ---------------------------------------------------------------------------
# Fake client (test double)
# ---------------------------------------------------------------------------


class FakeFutuClient:
    """Pure-Python test double for Futu OpenD. Zero SDK imports."""

    def __init__(self, *, default_response: str = "accepted") -> None:
        self.default_response = default_response
        self.submitted_orders: list[dict[str, Any]] = []
        self.cancelled_orders: list[dict[str, Any]] = []

    # -- Quotes / Data -------------------------------------------------------

    def get_history_kline(
        self,
        *,
        symbol: str,
        interval: str = "1d",
        limit: int = 100,
    ) -> list[list[float]]:
        """Return synthetic OHLCV bars."""
        now = int(time.time() * 1000)
        base_price = 100.0
        bars: list[list[float]] = []
        for i in range(limit):
            ts = now - (limit - i) * 86_400_000
            o = base_price + i * 0.5
            h = o + 1.0
            l = o - 0.5
            c = o + 0.3
            v = 1_000_000 + i * 10_000
            bars.append([float(ts), o, h, l, c, v])
        return bars

    def get_rt_data(self, *, symbol: str) -> dict[str, Any]:
        """Return synthetic real-time snapshot."""
        return {
            "symbol": symbol,
            "price": 100.0,
            "high": 101.0,
            "low": 99.0,
            "open": 99.5,
            "volume": 1_000_000,
            "turnover": 100_000_000,
            "bid_price": 99.95,
            "ask_price": 100.05,
            "bid_size": 500,
            "ask_size": 300,
            "ts": int(time.time() * 1000),
            "market": _detect_market(symbol),
        }

    def get_market_snapshot(self, *, symbols: list[str]) -> list[dict[str, Any]]:
        return [self.get_rt_data(symbol=s) for s in symbols]

    def get_trade_days(self, *, market: str, start: str, end: str) -> list[str]:
        return ["2026-01-02", "2026-01-03", "2026-01-06"]

    def get_order_book(self, *, symbol: str, limit: int = 5) -> dict[str, Any]:
        mid = 100.0
        bids = [[mid - i * 0.5, 1.0 + i * 0.1] for i in range(1, limit + 1)]
        asks = [[mid + i * 0.5, 1.0 + i * 0.1] for i in range(1, limit + 1)]
        return {"symbol": symbol, "bids": bids, "asks": asks}

    # -- Trading --------------------------------------------------------------

    def place_order(
        self,
        *,
        symbol: str,
        side: str,
        qty: int,
        price: float | None,
        order_type: str = "limit",
        trd_env: str = "SIMULATE",
    ) -> dict[str, Any]:
        record: dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "price": price,
            "order_type": order_type,
            "trd_env": trd_env,
            "ts": int(time.time()),
        }
        self.submitted_orders.append(record)
        oid = f"fake-futu-oid-{len(self.submitted_orders)}"
        if self.default_response == "accepted":
            return {"status": "submitted", "order_id": oid, "symbol": symbol}
        elif self.default_response == "rejected":
            return {
                "status": "rejected",
                "order_id": None,
                "symbol": symbol,
                "error": "insufficient funds",
            }
        elif self.default_response == "filled":
            return {"status": "filled", "order_id": oid, "symbol": symbol}
        elif self.default_response == "timeout":
            return {"status": "unknown", "order_id": None, "symbol": symbol}
        else:
            return {"status": "unknown", "order_id": None, "symbol": symbol}

    def cancel_order(self, *, symbol: str, order_id: str) -> dict[str, Any]:
        self.cancelled_orders.append({"symbol": symbol, "order_id": order_id, "ts": int(time.time())})
        return {"status": "cancelled", "order_id": order_id}

    def get_order_status(self, *, order_id: str) -> dict[str, Any]:
        r = self.default_response
        if r == "accepted":
            return {"status": "submitted", "order_id": order_id, "filled_qty": 0, "qty": 100, "price": 100.0}
        elif r == "filled":
            return {"status": "filled", "order_id": order_id, "filled_qty": 100, "qty": 100, "price": 100.0}
        elif r == "rejected":
            return {"status": "rejected", "order_id": order_id, "filled_qty": 0, "qty": 0, "price": 0}
        elif r == "cancelled":
            return {"status": "cancelled", "order_id": order_id, "filled_qty": 0, "qty": 100, "price": 100.0}
        elif r == "partial":
            return {"status": "partial", "order_id": order_id, "filled_qty": 50, "qty": 100, "price": 100.0}
        else:
            return {"status": r, "order_id": order_id, "filled_qty": 0, "qty": 0, "price": 0}

    def get_account_balance(self, *, trd_env: str = "SIMULATE") -> list[dict[str, Any]]:
        return [
            {"currency": "HKD", "cash": 500_000.0, "market_value": 200_000.0, "power": 700_000.0},
            {"currency": "USD", "cash": 50_000.0, "market_value": 100_000.0, "power": 150_000.0},
        ]

    def get_positions(self, *, trd_env: str = "SIMULATE") -> list[dict[str, Any]]:
        return [
            {"symbol": "HK.00700", "qty": 100, "cost_price": 380.0, "market_price": 400.0},
            {"symbol": "HK.09988", "qty": 200, "cost_price": 85.0, "market_price": 90.0},
        ]

    def healthcheck(self) -> dict[str, Any]:
        return {"status": "ok", "opend_connected": True}


# ---------------------------------------------------------------------------
# Real SDK client (lazy import)
# ---------------------------------------------------------------------------


class _SdkFutuClient:
    """Wraps the real futu-api SDK.

    SDK is imported lazily — RuntimeError raised only on construction if the
    package is absent or OpenD is unreachable.
    """

    def __init__(self, config: FutuEnvConfig) -> None:
        try:
            import futu as ft  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "futu-api package is required to use FutuAdapter with a real client. "
                "Install it with: pip install 'ai-market-maker[futu]' or pip install futu-api"
            ) from exc

        self._config = config
        self._ft = ft
        self._quote_ctx: Any = None
        self._trade_ctx: Any = None

    def _ensure_quote_ctx(self) -> Any:
        if self._quote_ctx is None:
            self._quote_ctx = self._ft.OpenQuoteContext(
                host=self._config.host,
                port=self._config.quote_port,
            )
        return self._quote_ctx

    def _ensure_trade_ctx(self) -> Any:
        if self._trade_ctx is None:
            self._trade_ctx = self._ft.OpenSecTradeContext(
                host=self._config.host,
                port=self._config.trade_port,
                security_firm=self._ft.SecurityFirm.FUTUSECURITIES,
            )
            # Unlock if password provided
            if self._config.unlock_pwd:
                unlock_pwd = self._config.unlock_pwd
                is_md5 = self._config.pwd_md5
                ret, msg = self._trade_ctx.unlock_trade(unlock_pwd, is_md5)
                if ret != self._ft.RET_OK:
                    raise RuntimeError(f"Failed to unlock trade: {msg}")
        return self._trade_ctx

    def __repr__(self) -> str:
        return (
            f"_SdkFutuClient("
            f"host={self._config.host!r}, "
            f"quote_port={self._config.quote_port!r}, "
            f"trade_port={self._config.trade_port!r})"
        )

    # -- Quotes / Data -------------------------------------------------------

    def get_history_kline(
        self,
        *,
        symbol: str,
        interval: str = "1d",
        limit: int = 100,
    ) -> list[list[float]]:
        ctx = self._ensure_quote_ctx()
        ktype = self._ft.KLType.K_DAY if interval in ("1d", "D") else (
            self._ft.KLType.K_60M if interval in ("60m", "1h") else (
                self._ft.KLType.K_30M if interval == "30m" else (
                    self._ft.KLType.K_15M if interval == "15m" else (
                        self._ft.KLType.K_5M if interval == "5m" else (
                            self._ft.KLType.K_WEEK if interval in ("1w", "W") else self._ft.KLType.K_DAY
                        )
                    )
                )
            )
        )
        nsymbol = normalize_futu_symbol(symbol)
        ret, data = ctx.get_history_kline(nsymbol, ktype, limit)
        if ret != self._ft.RET_OK:
            raise RuntimeError(f"Failed to get history kline for {nsymbol}: {data}")
        # Convert DataFrame to list of [ts, open, high, low, close, volume]
        bars: list[list[float]] = []
        for _, row in data.iterrows():
            ts = int(row.get("time_key", 0))
            o = float(row.get("open", 0))
            h = float(row.get("high", 0))
            l = float(row.get("low", 0))
            c = float(row.get("close", 0))
            v = float(row.get("volume", 0))
            bars.append([ts, o, h, l, c, v])
        return bars

    def get_rt_data(self, *, symbol: str) -> dict[str, Any]:
        ctx = self._ensure_quote_ctx()
        nsymbol = normalize_futu_symbol(symbol)
        ret, data = ctx.get_stock_quote(nsymbol)
        if ret != self._ft.RET_OK or data is None or data.empty:
            raise RuntimeError(f"Failed to get RT data for {nsymbol}: {data}")
        row = data.iloc[0]
        return {
            "symbol": symbol,
            "price": float(row.get("last_price", 0)),
            "high": float(row.get("high_price", 0)),
            "low": float(row.get("low_price", 0)),
            "open": float(row.get("open_price", 0)),
            "volume": float(row.get("volume", 0)),
            "turnover": float(row.get("turnover", 0)),
            "bid_price": float(row.get("bid_price", 0)),
            "ask_price": float(row.get("ask_price", 0)),
            "bid_size": int(row.get("bid_size", 0)),
            "ask_size": int(row.get("ask_size", 0)),
            "ts": int(time.time() * 1000),
        }

    def get_order_book(self, *, symbol: str, limit: int = 5) -> dict[str, Any]:
        ctx = self._ensure_quote_ctx()
        nsymbol = normalize_futu_symbol(symbol)
        ret, data = ctx.get_order_book(nsymbol, num=limit)
        if ret != self._ft.RET_OK:
            return {"symbol": symbol, "bids": [], "asks": []}
        bids = []
        asks = []
        if data is not None:
            for _, row in data.iterrows():
                entry = [float(row.get("price", 0)), int(row.get("stock_volume", 0))]
                if row.get("side") == "bid":
                    bids.append(entry)
                else:
                    asks.append(entry)
        return {"symbol": symbol, "bids": bids, "asks": asks}

    # -- Trading --------------------------------------------------------------

    def place_order(
        self,
        *,
        symbol: str,
        side: str,
        qty: int,
        price: float | None,
        order_type: str = "limit",
        trd_env: str = "SIMULATE",
    ) -> dict[str, Any]:
        ctx = self._ensure_trade_ctx()
        nsymbol = normalize_futu_symbol(symbol)
        trd_side = self._ft.TrdSide.BUY if side.lower() == "buy" else self._ft.TrdSide.SELL
        trd_env_e = self._ft.TrdEnv.SIMULATE if trd_env.upper() == "SIMULATE" else self._ft.TrdEnv.REAL
        order_type_e = (
            self._ft.OrderType.NORMAL if order_type == "limit" else self._ft.OrderType.MARKET
        )

        ret, data = ctx.place_order(
            price=price or 0.0,
            qty=qty,
            code=nsymbol,
            trd_side=trd_side,
            order_type=order_type_e,
            trd_env=trd_env_e,
        )
        if ret != self._ft.RET_OK:
            return {"status": "rejected", "order_id": None, "symbol": symbol, "error": str(data)}
        order_id = data.get("order_id", "") if isinstance(data, dict) else ""
        return {"status": "submitted", "order_id": order_id, "symbol": symbol}

    def cancel_order(self, *, symbol: str, order_id: str) -> dict[str, Any]:
        ctx = self._ensure_trade_ctx()
        nsymbol = normalize_futu_symbol(symbol)
        ret, data = ctx.cancel_order(order_id=order_id, code=nsymbol)
        if ret != self._ft.RET_OK:
            return {"status": "error", "order_id": order_id, "error": str(data)}
        return {"status": "cancelled", "order_id": order_id}

    def get_order_status(self, *, order_id: str) -> dict[str, Any]:
        ctx = self._ensure_trade_ctx()
        # Query all orders and filter by id
        ret, data = ctx.get_order_list()
        if ret != self._ft.RET_OK or data is None:
            return {"status": "unknown", "order_id": order_id, "filled_qty": 0, "qty": 0, "price": 0}
        for _, row in data.iterrows():
            if str(row.get("order_id", "")) == order_id:
                return {
                    "status": str(row.get("order_status", "unknown")).lower(),
                    "order_id": order_id,
                    "filled_qty": int(row.get("fill_qty", 0)),
                    "qty": int(row.get("qty", 0)),
                    "price": float(row.get("price", 0)),
                }
        return {"status": "unknown", "order_id": order_id, "filled_qty": 0, "qty": 0, "price": 0}

    def get_account_balance(self, *, trd_env: str = "SIMULATE") -> list[dict[str, Any]]:
        ctx = self._ensure_trade_ctx()
        trd_env_e = self._ft.TrdEnv.SIMULATE if trd_env.upper() == "SIMULATE" else self._ft.TrdEnv.REAL
        ret, data = ctx.get_account_list(trd_env=trd_env_e)
        if ret != self._ft.RET_OK or data is None:
            return []
        balances: list[dict[str, Any]] = []
        for _, row in data.iterrows():
            balances.append({
                "currency": str(row.get("currency", "")),
                "cash": float(row.get("cash", 0)),
                "market_value": float(row.get("market_val", 0)),
                "power": float(row.get("power", 0)),
            })
        return balances

    def get_positions(self, *, trd_env: str = "SIMULATE") -> list[dict[str, Any]]:
        ctx = self._ensure_trade_ctx()
        trd_env_e = self._ft.TrdEnv.SIMULATE if trd_env.upper() == "SIMULATE" else self._ft.TrdEnv.REAL
        ret, data = ctx.get_position_list(trd_env=trd_env_e)
        if ret != self._ft.RET_OK or data is None:
            return []
        positions: list[dict[str, Any]] = []
        for _, row in data.iterrows():
            positions.append({
                "symbol": str(row.get("code", "")),
                "qty": int(row.get("qty", 0)),
                "cost_price": float(row.get("cost_price", 0)),
                "market_price": float(row.get("market_price", 0)),
            })
        return positions

    def healthcheck(self) -> dict[str, Any]:
        try:
            ctx = self._ensure_quote_ctx()
            ret, _ = ctx.get_global_state()
            connected = ret == 0
        except Exception:
            connected = False
        return {"status": "ok" if connected else "error", "opend_connected": connected}

    def close(self) -> None:
        if self._quote_ctx:
            try:
                self._quote_ctx.close()
            except Exception:
                pass
        if self._trade_ctx:
            try:
                self._trade_ctx.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class FutuAdapter:
    """Exchange adapter for Futu OpenD. Satisfies ExchangeAdapter Protocol.

    Inject FakeFutuClient for tests. _SdkFutuClient is used in production.
    """

    def __init__(
        self,
        *,
        config: ExchangeConfig | None = None,
        futu_env: FutuEnvConfig | None = None,
        client: Any = None,
    ) -> None:
        self._exchange_config = config
        self._futu_env = futu_env or FutuEnvConfig.from_env()
        self._client = client if client is not None else _SdkFutuClient(self._futu_env)

    def __repr__(self) -> str:
        return (
            f"FutuAdapter("
            f"host={self._futu_env.host!r}, "
            f"quote_port={self._futu_env.quote_port!r}, "
            f"dry_run={self._futu_env.dry_run!r})"
        )

    # -- ExchangeAdapter Protocol ---------------------------------------------

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
        now = int(time.time())

        # Dry run
        if self._futu_env.dry_run:
            return ExchangeOrderResult(
                status="dry_run",
                exchange_order_id=None,
                client_order_id=client_order_id,
                symbol=symbol,
                side=side,
                qty=qty,
                price=price,
                filled_qty=0.0,
                ts=now,
                raw={"dry_run": True},
            )

        # Convert float qty → int for Futu (stocks are integer shares)
        int_qty = max(1, int(round(qty)))
        trd_env = "SIMULATE"  # Default to simulate for paper trading

        raw = self._client.place_order(
            symbol=symbol,
            side=side,
            qty=int_qty,
            price=price,
            order_type=order_type,
            trd_env=trd_env,
        )

        raw_status = str(raw.get("status", "unknown"))
        oid = raw.get("order_id")

        if raw_status in ("submitted", "filled"):
            mapped = "accepted" if raw_status == "submitted" else "filled"
        elif raw_status == "rejected":
            mapped = "rejected"
        else:
            mapped = "unknown"

        kwargs: dict[str, Any] = {
            "status": mapped,
            "exchange_order_id": str(oid) if oid else None,
            "client_order_id": client_order_id,
            "symbol": symbol,
            "side": side,
            "qty": float(int_qty),
            "price": price,
            "filled_qty": float(int_qty) if raw_status == "filled" else 0.0,
            "ts": now,
            "raw": raw,
        }
        if mapped == "rejected":
            kwargs["error"] = str(raw.get("error", "rejected"))
        return ExchangeOrderResult(**kwargs)

    def cancel_order(
        self,
        *,
        symbol: str,
        exchange_order_id: str,
    ) -> ExchangeOrderResult:
        now = int(time.time())

        if self._futu_env.dry_run:
            return ExchangeOrderResult(
                status="dry_run",
                exchange_order_id=exchange_order_id,
                client_order_id=None,
                symbol=symbol,
                side="",
                qty=0.0,
                price=None,
                filled_qty=0.0,
                ts=now,
                raw={"dry_run": True},
            )

        raw = self._client.cancel_order(symbol=symbol, order_id=exchange_order_id)
        raw_status = str(raw.get("status", "unknown"))
        mapped = "cancelled" if raw_status == "cancelled" else raw_status

        return ExchangeOrderResult(
            status=mapped,
            exchange_order_id=exchange_order_id,
            client_order_id=None,
            symbol=symbol,
            side="",
            qty=0.0,
            price=None,
            filled_qty=0.0,
            ts=now,
            raw=raw,
        )

    def get_order_status(
        self,
        *,
        symbol: str,
        exchange_order_id: str,
    ) -> ExchangeOrderResult:
        now = int(time.time())
        raw = self._client.get_order_status(order_id=exchange_order_id)

        raw_status = str(raw.get("status", "unknown"))
        if raw_status in ("submitted", "waiting"):
            mapped = "accepted"
        elif raw_status == "filled":
            mapped = "filled"
        elif raw_status == "cancelled":
            mapped = "cancelled"
        elif raw_status == "rejected":
            mapped = "rejected"
        elif raw_status == "partial":
            mapped = "partially_filled"
        else:
            mapped = "unknown"

        kwargs: dict[str, Any] = {
            "status": mapped,
            "exchange_order_id": exchange_order_id,
            "client_order_id": None,
            "symbol": symbol,
            "side": "",
            "qty": float(raw.get("qty", 0)),
            "price": float(raw.get("price", 0)) if raw.get("price") else None,
            "filled_qty": float(raw.get("filled_qty", 0)),
            "ts": now,
            "raw": raw,
        }
        if mapped == "rejected":
            kwargs["error"] = str(raw.get("error", "rejected"))
        return ExchangeOrderResult(**kwargs)

    def get_portfolio_health(
        self,
        *,
        account_id: str | None = None,
    ) -> dict[str, Any]:
        try:
            balances = self._client.get_account_balance()
            positions = self._client.get_positions()
        except Exception:
            balances = []
            positions = []

        return {
            "account_id": account_id or "futu-default",
            "ts": int(time.time()),
            "exchange": "futu-opend",
            "host": self._futu_env.host,
            "testnet": True,
            "balances": balances,
            "positions": positions,
        }

    def fetch_market_depth(
        self,
        *,
        symbol: str,
        limit: int,
    ) -> dict[str, Any]:
        raw = self._client.get_order_book(symbol=symbol, limit=limit)
        return {
            "symbol": symbol,
            "bids": raw.get("bids", []),
            "asks": raw.get("asks", []),
            "ts": int(time.time()),
            "source": "futu-opend",
        }

    # -- Futu-specific convenience methods ------------------------------------

    def get_history_kline(
        self,
        *,
        symbol: str,
        interval: str = "1d",
        limit: int = 100,
    ) -> list[list[float]]:
        return self._client.get_history_kline(symbol=symbol, interval=interval, limit=limit)

    def get_rt_data(self, *, symbol: str) -> dict[str, Any]:
        return self._client.get_rt_data(symbol=symbol)

    def healthcheck(self) -> dict[str, Any]:
        return self._client.healthcheck()

    def close(self) -> None:
        if hasattr(self._client, "close"):
            self._client.close()


__all__ = [
    "FakeFutuClient",
    "FutuAdapter",
    "FutuEnvConfig",
    "normalize_futu_symbol",
]
