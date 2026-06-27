"""Optional Adanos Market Sentiment API feed for crypto retail signals."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import quote

import httpx

from nexus_data.symbols import base_asset


@dataclass(frozen=True)
class AdanosSentimentConfig:
    api_base: str = "https://api.adanos.org/reddit/crypto/v1"
    api_key: str | None = None
    timeout_s: float = 5.0
    total_timeout_s: float = 20.0
    lookback_days: int = 7
    max_symbols: int = 8
    max_workers: int = 4

    @staticmethod
    def from_env() -> "AdanosSentimentConfig":
        api_base = os.getenv("ADANOS_API_BASE") or "https://api.adanos.org/reddit/crypto/v1"
        return AdanosSentimentConfig(
            api_base=api_base.strip().rstrip("/"),
            api_key=(os.getenv("ADANOS_API_KEY") or "").strip() or None,
            timeout_s=float(os.getenv("ADANOS_TIMEOUT_S") or "5"),
            total_timeout_s=float(os.getenv("ADANOS_TOTAL_TIMEOUT_S") or "20"),
            lookback_days=max(1, int(os.getenv("ADANOS_LOOKBACK_DAYS") or "7")),
            max_symbols=max(1, int(os.getenv("ADANOS_SYMBOL_MAX") or "8")),
            max_workers=max(1, int(os.getenv("ADANOS_MAX_WORKERS") or "4")),
        )


def adanos_credentials_configured() -> bool:
    return bool((os.getenv("ADANOS_API_KEY") or "").strip())


def adanos_feeds_enabled() -> bool:
    if (os.getenv("ADANOS_DISABLE") or "").lower() in ("1", "true", "yes"):
        return False
    return adanos_credentials_configured()


def _unique_base_assets(universe: list[str], limit: int) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in universe:
        if not isinstance(raw, str):
            continue
        sym = base_asset(raw).strip().upper()
        if not sym or sym in seen:
            continue
        seen.add(sym)
        out.append(sym)
        if len(out) >= limit:
            break
    return out


def _as_float(payload: dict[str, Any], *names: str, default: float = 0.0) -> float:
    for name in names:
        value = payload.get(name)
        if isinstance(value, (int, float)):
            return float(value)
    return default


def _as_int(payload: dict[str, Any], *names: str, default: int = 0) -> int:
    for name in names:
        value = payload.get(name)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
    return default


def _extract_data(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    return data if isinstance(data, dict) else payload


def _normalize_row(symbol: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = _extract_data(payload)
    sentiment = _as_float(data, "sentiment_score", "sentiment", "score")
    bullish_pct = _as_float(data, "bullish_pct", "bullish_percentage")
    bearish_pct = _as_float(data, "bearish_pct", "bearish_percentage")
    return {
        "symbol": symbol,
        "found": bool(data.get("found", True)),
        "mention_count": _as_int(data, "mentions", "mention_count", "mentionCount"),
        "unique_posts": _as_int(data, "unique_posts", "uniquePosts"),
        "subreddit_count": _as_int(data, "subreddit_count", "subredditCount"),
        "total_upvotes": _as_int(data, "total_upvotes", "totalUpvotes"),
        "sentiment_score": sentiment,
        "buzz_score": _as_float(data, "buzz_score", "buzzScore"),
        "bullish_ratio": bullish_pct / 100.0 if bullish_pct > 1.0 else bullish_pct,
        "bearish_ratio": bearish_pct / 100.0 if bearish_pct > 1.0 else bearish_pct,
        "trend": data.get("trend") if isinstance(data.get("trend"), str) else None,
    }


def _fetch_symbol_row(
    symbol: str,
    *,
    cfg: AdanosSentimentConfig,
    start: date,
    end: date,
) -> dict[str, Any]:
    url = f"{cfg.api_base}/token/{quote(symbol, safe='')}"
    with httpx.Client(timeout=cfg.timeout_s) as client:
        resp = client.get(
            url,
            headers={"X-API-Key": cfg.api_key or ""},
            params={"from": start.isoformat(), "to": end.isoformat()},
        )
        if resp.status_code == 404:
            return {"symbol": symbol, "found": False, "mention_count": 0}
        resp.raise_for_status()
        payload = resp.json()
        if not isinstance(payload, dict):
            raise ValueError("Adanos response is not a JSON object")
        return _normalize_row(symbol, payload)


def fetch_adanos_crypto_sentiment_bundle(
    universe: list[str],
    *,
    cfg: AdanosSentimentConfig | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    """Fetch per-token Adanos crypto sentiment for the current trading universe."""
    cfg = cfg or AdanosSentimentConfig.from_env()
    if not cfg.api_key:
        return {"ok": False, "error": "ADANOS_API_KEY is not configured", "data": None}

    end = today or datetime.now(UTC).date()
    start = end - timedelta(days=cfg.lookback_days - 1)
    symbols = _unique_base_assets(universe, cfg.max_symbols)
    rows: list[dict[str, Any]] = []
    errors: list[str] = []

    if symbols:
        rows_by_symbol: dict[str, dict[str, Any]] = {}
        workers = min(cfg.max_workers, len(symbols))
        executor = ThreadPoolExecutor(max_workers=workers)
        futures = {
            executor.submit(_fetch_symbol_row, symbol, cfg=cfg, start=start, end=end): symbol
            for symbol in symbols
        }
        done, pending = wait(futures, timeout=cfg.total_timeout_s)
        for fut in done:
            symbol = futures[fut]
            try:
                rows_by_symbol[symbol] = fut.result()
            except Exception as exc:
                errors.append(f"{symbol}: {exc}")
        for fut in pending:
            symbol = futures[fut]
            fut.cancel()
            errors.append(f"{symbol}: timed out after {cfg.total_timeout_s:.1f}s total budget")
        executor.shutdown(wait=False, cancel_futures=True)
        rows = [rows_by_symbol[symbol] for symbol in symbols if symbol in rows_by_symbol]

    ok = bool(rows) or not errors
    return {
        "ok": ok,
        "data": {
            "success": ok,
            "source": "adanos",
            "window": {"from": start.isoformat(), "to": end.isoformat()},
            "rows": rows,
            "partial_errors": errors,
        },
        "error": "; ".join(errors) if errors else None,
    }
