"""Hyperliquid exchange adapter.

Three classes:
  - FakeHyperliquidClient  — pure-Python test double; no SDK required
  - _SdkHyperliquidClient  — lazy-imports real SDK; only used in production
  - HyperliquidAdapter     — satisfies ExchangeAdapter Protocol; injectable client

Live trading remains opt-in: requires EXCHANGE=hyperliquid + AI_MARKET_MAKER_ALLOW_LIVE=1.
SDK import is lazy: missing SDK raises RuntimeError only when _SdkHyperliquidClient is constructed.
dry_run=True never sends orders to the exchange.
"""

from __future__ import annotations

import time
from typing import Any

from adapters.exchange_protocol import ExchangeOrderResult
from config.exchange_env import ExchangeConfig

_HL_MAINNET_URL = "https://api.hyperliquid.xyz"
_HL_TESTNET_URL = "https://api.hyperliquid-testnet.xyz"


def normalize_hl_symbol(symbol: str) -> str:
    """Map common pair notations to Hyperliquid coin name (e.g. BTC/USDT → BTC)."""
    s = symbol.strip().upper()
    if "/" in s:
        return s.split("/")[0]
    if "-" in s:
        return s.split("-")[0]
    # Strip known suffixes from plain strings like BTCUSDT
    if s.endswith("USDT") and len(s) > 4:
        return s[:-4]
    if s.endswith("PERP") and len(s) > 4:
        return s[:-4]
    if s.endswith("USD") and len(s) > 3:
        return s[:-3]
    return s


def _map_hl_status(raw: str) -> str:
    """Map Hyperliquid API status strings to ExchangeAdapter conventions."""
    if raw == "open":
        return "accepted"
    elif raw == "filled":
        return "filled"
    elif raw == "cancelled":
        return "cancelled"
    elif raw == "rejected":
        return "rejected"
    elif raw in ("partial", "partially_filled"):
        return "partially_filled"
    else:
        return "unknown"


class FakeHyperliquidClient:
    """Pure-Python test double for the Hyperliquid client. Zero SDK imports."""

    def __init__(self, *, default_response: str = "accepted") -> None:
        self.default_response = default_response
        self.submitted_orders: list[dict[str, Any]] = []
        self.cancelled_orders: list[dict[str, Any]] = []

    def place_order(
        self,
        *,
        coin: str,
        is_buy: bool,
        sz: float,
        limit_px: float | None,
        order_type: str,
        reduce_only: bool,
        cloid: str | None,
    ) -> dict[str, Any]:
        record: dict[str, Any] = {
            "coin": coin,
            "is_buy": is_buy,
            "sz": sz,
            "limit_px": limit_px,
            "order_type": order_type,
            "reduce_only": reduce_only,
            "cloid": cloid,
            "ts": int(time.time()),
        }
        self.submitted_orders.append(record)
        oid = f"fake-oid-{len(self.submitted_orders)}"
        if self.default_response == "accepted":
            return {"status": "open", "oid": oid, "cloid": cloid}
        elif self.default_response == "rejected":
            return {
                "status": "rejected",
                "error": "insufficient margin",
                "oid": None,
                "cloid": cloid,
            }
        elif self.default_response == "timeout":
            return {"status": "timeout", "oid": None, "cloid": cloid}
        else:
            return {"status": "unknown", "oid": None, "cloid": cloid}

    def cancel_order(self, *, coin: str, oid: str) -> dict[str, Any]:
        self.cancelled_orders.append({"coin": coin, "oid": oid, "ts": int(time.time())})
        return {"status": "cancelled", "oid": oid}

    def get_order_status(self, *, oid: str) -> dict[str, Any]:
        r = self.default_response
        if r == "accepted":
            return {
                "status": "open",
                "oid": oid,
                "filled_sz": 0.0,
                "sz": 1.0,
                "limit_px": 100.0,
                "side": "B",
            }
        elif r == "filled":
            return {
                "status": "filled",
                "oid": oid,
                "filled_sz": 1.0,
                "sz": 1.0,
                "limit_px": 100.0,
                "side": "B",
            }
        elif r == "rejected":
            return {
                "status": "rejected",
                "oid": oid,
                "filled_sz": 0.0,
                "sz": 0.0,
                "limit_px": None,
                "side": "",
            }
        elif r == "cancelled":
            return {
                "status": "cancelled",
                "oid": oid,
                "filled_sz": 0.0,
                "sz": 1.0,
                "limit_px": 100.0,
                "side": "B",
            }
        elif r == "partial":
            return {
                "status": "partial",
                "oid": oid,
                "filled_sz": 0.5,
                "sz": 1.0,
                "limit_px": 100.0,
                "side": "B",
            }
        else:
            return {
                "status": r,
                "oid": oid,
                "filled_sz": 0.0,
                "sz": 0.0,
                "limit_px": None,
                "side": "",
            }

    def fetch_open_orders(self, *, coin: str | None = None) -> list[dict[str, Any]]:
        if coin is None:
            return list(self.submitted_orders)
        return [o for o in self.submitted_orders if o.get("coin") == coin]

    def fetch_positions(self) -> list[dict[str, Any]]:
        return []

    def fetch_market_depth(self, *, coin: str, limit: int) -> dict[str, Any]:
        mid = 100.0
        bids = [[mid - i * 0.5, 1.0] for i in range(1, limit + 1)]
        asks = [[mid + i * 0.5, 1.0] for i in range(1, limit + 1)]
        return {"coin": coin, "bids": bids, "asks": asks}

    def healthcheck(self) -> dict[str, Any]:
        return {"status": "ok"}


class _SdkHyperliquidClient:
    """Wraps the real hyperliquid-python-sdk. SDK is imported lazily.

    SDK import is lazy: RuntimeError raised only on construction if SDK is absent.
    """

    def __init__(self, config: ExchangeConfig) -> None:
        try:
            import hyperliquid  # noqa: F401
            from hyperliquid.exchange import Exchange
            from hyperliquid.info import Info
        except ImportError as exc:
            raise RuntimeError(
                "hyperliquid-python-sdk is required to use HyperliquidAdapter with a real client. "
                "Install it with: pip install 'ai-market-maker[hyperliquid]'"
            ) from exc

        self._config = config
        if config.hyperliquid_api_base:
            base_url = config.hyperliquid_api_base
        elif config.testnet:
            base_url = _HL_TESTNET_URL
        else:
            base_url = _HL_MAINNET_URL

        self._exchange = Exchange(
            base_url=base_url,
            wallet=config.hyperliquid_api_key,
            private_key=config.hyperliquid_secret,
        )
        self._info = Info(base_url=base_url, skip_ws=True)

    def __repr__(self) -> str:
        return (
            f"_SdkHyperliquidClient("
            f"api_key={self._config.hyperliquid_api_key!r}, "
            f"secret=[REDACTED], "
            f"testnet={self._config.testnet!r})"
        )

    def place_order(self, *, coin, is_buy, sz, limit_px, order_type, reduce_only, cloid):
        raise NotImplementedError("SDK integration not yet implemented")

    def cancel_order(self, *, coin, oid):
        raise NotImplementedError("SDK integration not yet implemented")

    def get_order_status(self, *, oid):
        raise NotImplementedError("SDK integration not yet implemented")

    def fetch_open_orders(self, *, coin=None):
        raise NotImplementedError("SDK integration not yet implemented")

    def fetch_positions(self):
        raise NotImplementedError("SDK integration not yet implemented")

    def fetch_market_depth(self, *, coin, limit):
        raise NotImplementedError("SDK integration not yet implemented")

    def healthcheck(self):
        raise NotImplementedError("SDK integration not yet implemented")


class HyperliquidAdapter:
    """Exchange adapter for Hyperliquid. Satisfies ExchangeAdapter Protocol.

    Inject FakeHyperliquidClient for tests. _SdkHyperliquidClient is used in production.
    """

    def __init__(self, *, config: ExchangeConfig, client: Any = None) -> None:
        self._config = config
        # Lazy SDK client only when no test double injected
        self._client = client if client is not None else _SdkHyperliquidClient(config)

    def __repr__(self) -> str:
        return (
            f"HyperliquidAdapter("
            f"exchange={self._config.exchange_name!r}, "
            f"testnet={self._config.testnet!r}, "
            f"dry_run={self._config.dry_run!r}, "
            f"api_key={self._config.hyperliquid_api_key!r})"
        )

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
        # dry_run never sends orders to the exchange
        if self._config.dry_run:
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

        coin = normalize_hl_symbol(symbol)
        is_buy = side.lower() == "buy"
        raw = self._client.place_order(
            coin=coin,
            is_buy=is_buy,
            sz=qty,
            limit_px=price,
            order_type=order_type,
            reduce_only=False,
            cloid=client_order_id,
        )
        oid = raw.get("oid")
        mapped_status = _map_hl_status(str(raw.get("status", "unknown")))
        kwargs: dict[str, Any] = {
            "status": mapped_status,
            "exchange_order_id": str(oid) if oid is not None else None,
            "client_order_id": client_order_id,
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "price": price,
            "filled_qty": 0.0,
            "ts": now,
            "raw": raw,
        }
        if mapped_status in ("rejected", "error"):
            kwargs["error"] = str(raw.get("error", mapped_status))
        return ExchangeOrderResult(**kwargs)

    def cancel_order(
        self,
        *,
        symbol: str,
        exchange_order_id: str,
    ) -> ExchangeOrderResult:
        now = int(time.time())
        # dry_run never sends cancellations to the exchange
        if self._config.dry_run:
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
        coin = normalize_hl_symbol(symbol)
        raw = self._client.cancel_order(coin=coin, oid=exchange_order_id)
        mapped_status = _map_hl_status(str(raw.get("status", "unknown")))
        return ExchangeOrderResult(
            status=mapped_status,
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
        raw = self._client.get_order_status(oid=exchange_order_id)
        mapped_status = _map_hl_status(str(raw.get("status", "unknown")))
        filled_qty = float(raw.get("filled_sz", 0.0))
        raw_price = raw.get("limit_px")
        price = float(raw_price) if raw_price is not None else None
        raw_side = raw.get("side", "")
        side = "buy" if raw_side == "B" else ("sell" if raw_side == "A" else "")
        kwargs: dict[str, Any] = {
            "status": mapped_status,
            "exchange_order_id": exchange_order_id,
            "client_order_id": None,
            "symbol": symbol,
            "side": side,
            "qty": float(raw.get("sz", 0.0)),
            "price": price,
            "filled_qty": filled_qty,
            "ts": now,
            "raw": raw,
        }
        if mapped_status in ("rejected", "error"):
            kwargs["error"] = str(raw.get("error", mapped_status))
        return ExchangeOrderResult(**kwargs)

    def get_portfolio_health(
        self,
        *,
        account_id: str | None = None,
    ) -> dict[str, Any]:
        positions_raw = self._client.fetch_positions()
        return {
            "account_id": account_id or "default",
            "ts": int(time.time()),
            "exchange": "hyperliquid",
            "testnet": self._config.testnet,
            "positions": positions_raw,
            "raw": positions_raw,
        }

    def fetch_market_depth(
        self,
        *,
        symbol: str,
        limit: int,
    ) -> dict[str, Any]:
        coin = normalize_hl_symbol(symbol)
        raw = self._client.fetch_market_depth(coin=coin, limit=limit)
        return {
            "symbol": symbol,
            "coin": coin,
            "bids": raw.get("bids", []),
            "asks": raw.get("asks", []),
            "ts": int(time.time()),
            "source": "hyperliquid",
        }

    def fetch_open_orders(
        self,
        *,
        symbol: str | None = None,
    ) -> list[dict[str, Any]]:
        coin = normalize_hl_symbol(symbol) if symbol is not None else None
        return self._client.fetch_open_orders(coin=coin)

    def fetch_positions(self) -> list[dict[str, Any]]:
        return self._client.fetch_positions()

    def healthcheck(self) -> dict[str, Any]:
        return self._client.healthcheck()


__all__ = [
    "FakeHyperliquidClient",
    "HyperliquidAdapter",
    "normalize_hl_symbol",
]
