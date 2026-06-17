"""Backtest engine — thin wrapper around PerpEngine.

Keeps the public ``BacktestEngine`` interface for compatibility.
All actual execution logic lives in ``engines/perp.py``.

Perp only (spot removed as of v1.0). Config via dict (no env vars).
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List
from typing import Any as _Any

from config.app_settings import load_app_settings, normalize_hold_signal_fallback
from config.run_mode import RunMode
from flow_log import FlowEventRepo, set_flow_repo
from harness.run_memory import IterationReceiptWriter, RunWorkingMemory, now_s, run_memory_config
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
                # Deploy config extra fields (set dynamically by loop.py)
                "deploy_profile_weights": getattr(config, "deploy_profile_weights", None),
                "deploy_profile_id": getattr(config, "deploy_profile_id", None),
                "deploy_arbitrator_mode": getattr(config, "deploy_arbitrator_mode", None),
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

        bt_dir = runs_dir / "backtests" / run_id
        bt_dir.mkdir(parents=True, exist_ok=True)
        iterations_path = bt_dir / "iterations.jsonl"
        receipt_writer = IterationReceiptWriter(path=iterations_path)

        perp_cfg = {
            "initial_cash": float(c.get("initial_cash_usd", 10_000)),
            "leverage": float(c.get("leverage", 3.0)),
            "taker_rate": float(c.get("fee_bps", 10.0)) / 10_000,
            "maker_rate": float(c.get("fee_bps", 10.0)) / 10_000,
            "slippage": float(c.get("slippage_bps", 5.0)) / 10_000,
            "funding_rate": 0.0001,
            # Used for Sharpe / Sortino annualization in PerpEngine metrics (must match bar spacing).
            "interval_sec": int(c.get("interval_sec", 300)),
        }

        bar_count = max(len(rows) for rows in bars_by_symbol.values())

        settings = load_app_settings()
        run_mem = RunWorkingMemory(cfg=run_memory_config(settings))
        env_fb = (os.getenv("AIMM_BACKTEST_HOLD_FALLBACK") or "").strip()
        hold_signal_fallback = (
            normalize_hold_signal_fallback(env_fb)
            if env_fb
            else settings.backtest.hold_signal_fallback
        )

        def _signal_fn(symbol: str, window: list, positions, capital: float) -> float:
            from schemas.state import initial_hedge_fund_state

            state = initial_hedge_fund_state(ticker=ticker, run_mode=RunMode.BACKTEST.value)

            # Inject deploy config (profile weights + arbitrator mode) when set
            deploy_profile_weights = c.get("deploy_profile_weights")
            if deploy_profile_weights:
                state["profile_weights"] = deploy_profile_weights
            deploy_profile_id = c.get("deploy_profile_id")
            if deploy_profile_id:
                state["profile_id"] = deploy_profile_id
            deploy_arb_mode = c.get("deploy_arbitrator_mode")
            if deploy_arb_mode:
                state["arbitrator_mode"] = deploy_arb_mode
            state["universe"] = list(bars_by_symbol.keys())
            state["market_data"] = {
                s: {
                    "status": "success",
                    "backtest": True,
                    # Slice OHLCV to the current bar (full series if window empty).
                    "ohlcv": list(bars_by_symbol[s])[: len(window)]
                    if window
                    else bars_by_symbol.get(s),
                }
                for s in bars_by_symbol
            }

            sm = state.setdefault("shared_memory", {})
            sm["backtest"] = {
                "cash": float(capital),
                "positions": {
                    k: {"size": v.size, "entry": v.entry_price} for k, v in positions.items()
                },
                "window_len": len(window) if isinstance(window, list) else None,
                "window_last_ts_ms": (
                    float(window[-1][0])
                    if isinstance(window, list)
                    and window
                    and isinstance(window[-1], list)
                    and len(window[-1]) > 0
                    else None
                ),
            }
            # Persisted run memory (bounded, explicit).
            sm["memory"] = run_mem.to_shared_memory_fragment()

            # Record what we "looked at" this step (evidence provenance).
            last_ts = sm["backtest"].get("window_last_ts_ms")
            run_mem.record_view(
                {
                    "symbol": str(symbol),
                    "universe": list(state.get("universe") or []),
                    "window_len": sm["backtest"].get("window_len"),
                    "window_last_ts_ms": last_ts,
                }
            )

            try:
                output = self.workflow.invoke(state)
                # `proposed_signal` can be overwritten later in the graph (e.g. by portfolio_proposal),
                # but `trade_intent` is the stable BUY/SELL/HOLD contract we want to backtest.
                intent = output.get("trade_intent") if isinstance(output, dict) else None
                intent = intent if isinstance(intent, dict) else {}
                action = str(intent.get("action") or "").strip().upper()
                conf_raw = intent.get("confidence", 0.0)
                try:
                    conf = float(conf_raw) if conf_raw is not None else 0.0
                except Exception:
                    conf = 0.0
                conf = max(0.0, min(1.0, conf))

                # Optional HOLD shaping (see ``config/app.default.json`` ``backtest.hold_signal_fallback``).
                # ``legacy`` matched early demos that forced rotation so runs never looked "empty".
                # Default ``momentum`` keeps a tiny drift nudge only — metrics reflect the graph + TA.
                if hold_signal_fallback in ("momentum", "legacy") and action == "HOLD":
                    if isinstance(window, list) and len(window) >= 6:
                        try:
                            look = min(6, len(window))
                            c0 = float(window[-look][4])
                            c1 = float(window[-1][4])
                            if c0 > 0:
                                r = (c1 - c0) / c0
                                if r >= 0.0006:
                                    action = "BUY"
                                elif r <= -0.0006:
                                    action = "SELL"
                        except Exception:
                            pass

                if hold_signal_fallback == "legacy" and action == "HOLD":
                    if isinstance(window, list) and len(window) >= 3:
                        try:
                            cur = positions.get(symbol)
                            if cur is None:
                                action = "BUY" if ((len(window) // 6) % 2 == 0) else "SELL"
                            else:
                                action = "SELL" if getattr(cur, "direction", 0) >= 0 else "BUY"
                        except Exception:
                            pass

                stance = "neutral"
                sign = 0.0
                if action == "BUY":
                    stance = "bullish"
                    sign = 1.0
                elif action == "SELL":
                    stance = "bearish"
                    sign = -1.0
                # Persist a small decision summary for next steps.
                run_mem.record_decision(
                    {
                        "symbol": str(symbol),
                        "action": action,
                        "stance": stance,
                        "confidence": conf,
                    }
                )
                # If an LLM node ran with tools, capture counts (not bulky results).
                try:
                    prop = output.get("proposed_signal") if isinstance(output, dict) else None
                    p_params = prop.get("params") if isinstance(prop, dict) else None
                    te = p_params.get("tool_events") if isinstance(p_params, dict) else None
                    if isinstance(te, list) and te:
                        run_mem.record_tool_event_summary(
                            {
                                "symbol": str(symbol),
                                "tool_events_count": len(te),
                                "tools": [
                                    str(x.get("name") or x.get("wire_name") or "")
                                    for x in te
                                    if isinstance(x, dict)
                                ][:8],
                            }
                        )
                except Exception:
                    pass

                # Persist a compact per-step receipt (what the agent saw + decided).
                try:
                    rec = {
                        "ts": now_s(),
                        "run_id": run_id,
                        "symbol": str(symbol),
                        "backtest": sm.get("backtest"),
                        "memory": run_mem.to_shared_memory_fragment(),
                        "decision": {"action": action, "stance": stance, "confidence": conf},
                    }
                    receipt_writer.append(rec)
                except Exception:
                    pass
                return float(sign * conf)
            except Exception as exc:
                # Always emit a receipt even on failure so operators can see what was attempted.
                try:
                    receipt_writer.append(
                        {
                            "ts": now_s(),
                            "run_id": run_id,
                            "symbol": str(symbol),
                            "backtest": sm.get("backtest"),
                            "memory": run_mem.to_shared_memory_fragment(),
                            "error": str(exc),
                        }
                    )
                except Exception:
                    pass
                import traceback

                tb_str = traceback.format_exc()
                print(f"[Backtest Warning] Workflow failed at step: {exc}\n{tb_str}")
                return 0.0

        result = run_perp_backtest(
            ticker=ticker,
            bars_by_symbol=bars_by_symbol,
            signal_fn=_signal_fn,
            config=perp_cfg,
            run_id=run_id,
            runs_dir=runs_dir,
            progress_callback=c.get("progress_callback"),
        )

        m = result.get("metrics", {})
        events_path = runs_dir / f"{run_id}.events.jsonl"
        bench_raw = result.get("benchmark")
        bench_out: dict[str, Any] = dict(bench_raw) if isinstance(bench_raw, dict) else {}
        return {
            "run_id": result.get("run_id", run_id),
            "steps": result.get("total_bars", bar_count),
            "interval_sec": int(c.get("interval_sec", 300)),
            "trade_count": m.get("total_trades", 0),
            "metrics": m,
            "final_equity": result.get("final_equity", perp_cfg["initial_cash"]),
            "benchmark": bench_out,
            "paths": {
                "summary": str(runs_dir / "backtests" / run_id / "summary.json"),
                "trades": str(runs_dir / "backtests" / run_id / "trades.jsonl"),
                "equity": str(runs_dir / "backtests" / run_id / "equity.jsonl"),
                "iterations": str(iterations_path),
                "events": str(events_path) if events_path.exists() else str(events_path),
            },
        }

    @staticmethod
    def _init_logging(run_id: str, runs_dir: Path) -> None:
        lp = runs_dir / f"{run_id}.events.jsonl"
        if lp.exists():
            lp.unlink()
        flow_repo = FlowEventRepo(run_id=run_id, log_path=lp)
        set_flow_repo(flow_repo)
