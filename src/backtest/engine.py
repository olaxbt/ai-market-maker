"""Backtest engine — thin wrapper around PerpEngine.

Keeps the public ``BacktestEngine`` interface for compatibility.
All actual execution logic lives in ``engines/perp.py``.

Perp only (spot removed as of v1.0). Config via dict (no env vars).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List
from typing import Any as _Any

from config.run_mode import RunMode
from flow_log import FlowEventRepo, set_flow_repo
from main import build_workflow

from .langgraph_adapter import run_perp_backtest


@dataclass
class BacktestConfig:
    """Backward-compatible config dataclass (perp only).

    Maps to PerpEngine dict config internally.
    """

    initial_cash_usd: float = 10_000.0
    initial_btc: float = 0.0
    fee_bps: float = 10.0
    slippage_bps: float = 5.0
    interval_sec: int = 300
    max_steps: int | None = None
    progress_callback: _Any | None = None
    runs_dir: _Any | None = None
    export_bundle: bool = True
    min_bars_between_trades: int = 0
    instrument: str = "perp"
    leverage: float = 3.0


class BacktestEngine:
    """Backtest entry point — perp only as of v1.0.

    Usage::

        engine = BacktestEngine(config)
        result = engine.run("BTC/USDT", bars=bars_list)
    """

    def __init__(self, config: BacktestConfig | dict | None = None):
        if isinstance(config, BacktestConfig):
            self._cfg = {
                "initial_cash_usd": config.initial_cash_usd,
                "initial_btc": config.initial_btc,
                "fee_bps": config.fee_bps,
                "slippage_bps": config.slippage_bps,
                "interval_sec": config.interval_sec,
                "max_steps": config.max_steps,
                "progress_callback": config.progress_callback,
                "runs_dir": config.runs_dir,
                "export_bundle": config.export_bundle,
                "instrument": config.instrument,
                "leverage": config.leverage,
            }
        else:
            self._cfg = dict(config or {})
        self.workflow = build_workflow().compile()

    def run(
        self,
        ticker: str = "BTC/USDT",
        bars: List[List[Any]] | None = None,
        bars_by_symbol: Dict[str, List[List[Any]]] | None = None,
        run_id: str | None = None,
        runs_dir: Path | None = None,
    ) -> Dict[str, Any]:
        """Run a perpetual backtest.

        Delegates to ``run_perp_backtest()`` with the LangGraph workflow
        as the per-bar signal function.

        ``bars`` (single-symbol) is shorthand for
        ``bars_by_symbol={ticker: bars}``.
        """
        if bars is not None and bars_by_symbol is not None:
            raise ValueError("provide bars OR bars_by_symbol, not both")
        if bars_by_symbol is None:
            if bars is None:
                raise ValueError("provide bars or bars_by_symbol")
            bars_by_symbol = {ticker: list(bars)}

        if bars is not None and ticker not in bars_by_symbol:
            bars_by_symbol[ticker] = list(bars)

        c = self._cfg
        run_id = run_id or f"bt_{int(time.time())}"
        cfg_rd = c.get("runs_dir")
        if cfg_rd is None:
            cfg_rd = ".runs"
        runs_dir = runs_dir or (cfg_rd if isinstance(cfg_rd, Path) else Path(cfg_rd))
        self._init_logging(run_id, runs_dir)

        perp_cfg = {
            "initial_cash": float(c.get("initial_cash_usd", 10_000)),
            "leverage": float(c.get("leverage", 3.0)),
            "taker_rate": float(c.get("fee_bps", 10.0)) / 10_000,
            "maker_rate": float(c.get("fee_bps", 10.0)) / 10_000,
            "slippage": float(c.get("slippage_bps", 5.0)) / 10_000,
            "funding_rate": 0.0001,
        }

        bar_count = max(len(rows) for rows in bars_by_symbol.values())

        def _signal_fn(symbol: str, window: list, positions, capital: float) -> float:
            from schemas.state import initial_hedge_fund_state

            state = initial_hedge_fund_state(ticker=ticker, run_mode=RunMode.BACKTEST.value)
            state["universe"] = list(bars_by_symbol.keys())
            state["market_data"] = {
                s: {"status": "success", "backtest": True, "ohlcv": bars_by_symbol.get(s, window)}
                for s in bars_by_symbol
            }

            sm = state.setdefault("shared_memory", {})
            sm["backtest"] = {
                "cash": float(capital),
                "positions": {
                    k: {"size": v.size, "entry": v.entry_price} for k, v in positions.items()
                },
            }

            try:
                output = self.workflow.invoke(state)
                sig = output.get("proposed_signal") or output.get("trade_intent") or {}
                params = sig.get("params") if isinstance(sig, dict) else {}
                return float(params.get("confidence", 0.0))
            except Exception as exc:
                print(f"[Backtest Warning] Workflow failed at step: {exc}")
                return 0.0

        result = run_perp_backtest(
            ticker=ticker,
            bars_by_symbol=bars_by_symbol,
            signal_fn=_signal_fn,
            config=perp_cfg,
            run_id=run_id,
            runs_dir=runs_dir,
        )

        m = result.get("metrics", {})
        return {
            "run_id": result.get("run_id", run_id),
            "steps": result.get("total_bars", bar_count),
            "interval_sec": int(c.get("interval_sec", 300)),
            "trade_count": m.get("total_trades", 0),
            "metrics": m,
            "final_equity": result.get("final_equity", perp_cfg["initial_cash"]),
            "benchmark": {},
            "paths": {
                "summary": str(runs_dir / "backtests" / run_id / "summary.json"),
                "trades": str(runs_dir / "backtests" / run_id / "trades.jsonl"),
                "equity": str(runs_dir / "backtests" / run_id / "equity.jsonl"),
            },
        }

    @staticmethod
    def _init_logging(run_id: str, runs_dir: Path) -> None:
        lp = runs_dir / f"{run_id}.events.jsonl"
        if lp.exists():
            lp.unlink()
        flow_repo = FlowEventRepo(run_id=run_id, log_path=lp)
        set_flow_repo(flow_repo)
