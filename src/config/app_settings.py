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
    trading_enabled: bool
    fee_bps: float
    min_notional_usd: float
    max_notional_fraction: float
    instrument: str
    leverage: float


@dataclass(frozen=True)
class UISettings:
    tail_events: int
    tail_traces: int
    tail_messages: int


@dataclass(frozen=True)
class FlowSettings:
    log_max_mb: int
    detail: str


@dataclass(frozen=True)
class RunsSettings:
    max_total_mb: int
    keep_last: int
    index_max_mb: int
    index_keep_last: int
    backtests_max_total_mb: int
    backtests_keep_last: int
    backtests_retention_enabled: bool


@dataclass(frozen=True)
class MarketSettings:
    default_ticker: str
    universe_size: int
    universe_symbols: list[str]
    ohlcv_cache_dir: str


@dataclass(frozen=True)
class LLMSettings:
    strict_json: bool
    output_retries: int


@dataclass(frozen=True)
class AppSettings:
    paper: PaperSettings
    ui: UISettings
    flow: FlowSettings
    runs: RunsSettings
    market: MarketSettings
    llm: LLMSettings


def load_app_settings(path: Path | None = None) -> AppSettings:
    p = path or Path("config/app.default.json")
    if not p.is_file():
        raise FileNotFoundError(f"missing app settings file: {p}")
    obj = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("app.default.json must be an object")

    paper = obj.get("paper")
    ui = obj.get("ui") or {}
    flow = obj.get("flow") or {}
    runs = obj.get("runs") or {}
    market = obj.get("market")
    llm = obj.get("llm") or {}
    if not isinstance(paper, dict) or not isinstance(market, dict):
        raise ValueError("app.default.json must contain 'paper' and 'market' objects")
    if ui is not None and not isinstance(ui, dict):
        raise ValueError("app.default.json 'ui' must be an object when present")
    if flow is not None and not isinstance(flow, dict):
        raise ValueError("app.default.json 'flow' must be an object when present")
    if runs is not None and not isinstance(runs, dict):
        raise ValueError("app.default.json 'runs' must be an object when present")
    if llm is not None and not isinstance(llm, dict):
        raise ValueError("app.default.json 'llm' must be an object when present")

    start_usdt = paper.get("start_usdt")
    if not isinstance(start_usdt, (int, float)):
        raise ValueError("paper.start_usdt must be a number")
    start_usdt_f = max(0.0, float(start_usdt))

    trading_enabled = paper.get("trading_enabled", True)
    if not isinstance(trading_enabled, bool):
        raise ValueError("paper.trading_enabled must be a boolean")

    fee_bps = paper.get("fee_bps", 10.0)
    if not isinstance(fee_bps, (int, float)):
        raise ValueError("paper.fee_bps must be a number")
    fee_bps_f = max(0.0, min(500.0, float(fee_bps)))

    min_notional_usd = paper.get("min_notional_usd", 25.0)
    if not isinstance(min_notional_usd, (int, float)):
        raise ValueError("paper.min_notional_usd must be a number")
    min_notional_usd_f = max(0.0, float(min_notional_usd))

    max_notional_fraction = paper.get("max_notional_fraction", 0.25)
    if not isinstance(max_notional_fraction, (int, float)):
        raise ValueError("paper.max_notional_fraction must be a number")
    max_notional_fraction_f = max(0.0, min(1.0, float(max_notional_fraction)))

    instrument = str(paper.get("instrument") or "spot").strip().lower()
    if instrument not in ("spot", "perp"):
        raise ValueError("paper.instrument must be 'spot' or 'perp'")
    leverage = paper.get("leverage", 3.0)
    if not isinstance(leverage, (int, float)):
        raise ValueError("paper.leverage must be a number")
    leverage_f = max(1.0, min(125.0, float(leverage)))

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

    def _int(name: str, v: object, *, lo: int, hi: int, default: int) -> int:
        if not isinstance(v, (int, float)):
            v = default
        return max(lo, min(hi, int(float(v))))

    ui_tail_events = _int("ui.tail_events", ui.get("tail_events"), lo=50, hi=200_000, default=1200)
    ui_tail_traces = _int("ui.tail_traces", ui.get("tail_traces"), lo=50, hi=50_000, default=350)
    ui_tail_messages = _int(
        "ui.tail_messages", ui.get("tail_messages"), lo=50, hi=100_000, default=600
    )

    flow_log_max_mb = _int("flow.log_max_mb", flow.get("log_max_mb"), lo=1, hi=10_000, default=50)
    flow_detail = str(flow.get("detail") or "standard").strip().lower()
    if flow_detail not in {"full", "standard", "compact"}:
        raise ValueError("flow.detail must be one of: full, standard, compact")

    runs_max_total_mb = _int(
        "runs.max_total_mb", runs.get("max_total_mb"), lo=50, hi=100_000, default=500
    )
    runs_keep_last = _int("runs.keep_last", runs.get("keep_last"), lo=10, hi=100_000, default=200)
    ix = runs.get("index") if isinstance(runs.get("index"), dict) else {}
    index_max_mb = _int("runs.index.max_mb", (ix or {}).get("max_mb"), lo=1, hi=10_000, default=25)
    index_keep_last = _int(
        "runs.index.keep_last",
        (ix or {}).get("keep_last"),
        lo=100,
        hi=5_000_000,
        default=20000,
    )
    bt = runs.get("backtests") if isinstance(runs.get("backtests"), dict) else {}
    backtests_retention_enabled = bool((bt or {}).get("retention_enabled", False))
    backtests_max_total_mb = _int(
        "runs.backtests.max_total_mb",
        (bt or {}).get("max_total_mb"),
        lo=50,
        hi=100_000,
        default=2000,
    )
    backtests_keep_last = _int(
        "runs.backtests.keep_last",
        (bt or {}).get("keep_last"),
        lo=5,
        hi=100_000,
        default=80,
    )

    strict_json = llm.get("strict_json", True)
    if not isinstance(strict_json, bool):
        raise ValueError("llm.strict_json must be a boolean")
    output_retries = llm.get("output_retries", 2)
    if not isinstance(output_retries, (int, float)):
        raise ValueError("llm.output_retries must be a number")
    output_retries_i = max(0, min(5, int(float(output_retries))))

    return AppSettings(
        paper=PaperSettings(
            start_usdt=start_usdt_f,
            trading_enabled=bool(trading_enabled),
            fee_bps=fee_bps_f,
            min_notional_usd=min_notional_usd_f,
            max_notional_fraction=max_notional_fraction_f,
            instrument=instrument,
            leverage=leverage_f,
        ),
        ui=UISettings(
            tail_events=ui_tail_events,
            tail_traces=ui_tail_traces,
            tail_messages=ui_tail_messages,
        ),
        flow=FlowSettings(log_max_mb=flow_log_max_mb, detail=flow_detail),
        runs=RunsSettings(
            max_total_mb=runs_max_total_mb,
            keep_last=runs_keep_last,
            index_max_mb=index_max_mb,
            index_keep_last=index_keep_last,
            backtests_max_total_mb=backtests_max_total_mb,
            backtests_keep_last=backtests_keep_last,
            backtests_retention_enabled=backtests_retention_enabled,
        ),
        market=MarketSettings(
            default_ticker=default_ticker,
            universe_size=universe_size_i,
            universe_symbols=universe_symbols,
            ohlcv_cache_dir=ohlcv_cache_dir,
        ),
        llm=LLMSettings(strict_json=bool(strict_json), output_retries=output_retries_i),
    )


__all__ = [
    "AppSettings",
    "FlowSettings",
    "LLMSettings",
    "MarketSettings",
    "PaperSettings",
    "RunsSettings",
    "UISettings",
    "load_app_settings",
]
