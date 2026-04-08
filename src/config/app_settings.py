"""Application settings (single source of truth).

Non-secret defaults live in `config/app.default.json`.
Secrets (API keys) still belong in `.env`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PaperSettings:
    start_usdt: float


@dataclass(frozen=True)
class MarketSettings:
    default_ticker: str
    universe_size: int
    universe_symbols: list[str]
    ohlcv_cache_dir: str


@dataclass(frozen=True)
class AppSettings:
    paper: PaperSettings
    market: MarketSettings


def load_app_settings(path: Path | None = None) -> AppSettings:
    p = path or Path("config/app.default.json")
    if not p.is_file():
        raise FileNotFoundError(f"missing app settings file: {p}")
    obj = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("app.default.json must be an object")

    paper = obj.get("paper")
    market = obj.get("market")
    if not isinstance(paper, dict) or not isinstance(market, dict):
        raise ValueError("app.default.json must contain 'paper' and 'market' objects")

    start_usdt = paper.get("start_usdt")
    if not isinstance(start_usdt, (int, float)):
        raise ValueError("paper.start_usdt must be a number")
    start_usdt_f = max(0.0, float(start_usdt))

    default_ticker = str(market.get("default_ticker") or "").strip()
    if not default_ticker:
        raise ValueError("market.default_ticker is required")

    universe_size = market.get("universe_size")
    if not isinstance(universe_size, (int, float)):
        raise ValueError("market.universe_size must be a number")
    universe_size_i = max(1, int(float(universe_size)))

    universe_symbols_raw = market.get("universe_symbols")
    if not isinstance(universe_symbols_raw, list) or not universe_symbols_raw:
        raise ValueError("market.universe_symbols must be a non-empty list")
    universe_symbols = [str(x).strip() for x in universe_symbols_raw if str(x).strip()]
    if not universe_symbols:
        raise ValueError("market.universe_symbols must contain at least one symbol")

    ohlcv_cache_dir = str(market.get("ohlcv_cache_dir") or "").strip() or "data/ohlcv"

    return AppSettings(
        paper=PaperSettings(start_usdt=start_usdt_f),
        market=MarketSettings(
            default_ticker=default_ticker,
            universe_size=universe_size_i,
            universe_symbols=universe_symbols,
            ohlcv_cache_dir=ohlcv_cache_dir,
        ),
    )


__all__ = ["AppSettings", "MarketSettings", "PaperSettings", "load_app_settings"]
