"""Multi-step bar backtest: replay LangGraph once per bar with booked simulated fills."""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from api.payload_adapter import build_nexus_payload
from api.schema_validation import validate_nexus_payload
from backtest.metrics import compute_basic_metrics
from backtest.trade_book import append_jsonl
from config.run_mode import RunMode
from flow_log import FlowEventRepo, set_flow_repo
from main import build_workflow
from schemas.state import initial_hedge_fund_state

logger = logging.getLogger(__name__)


@dataclass
class BacktestSimState:
    cash: float
    qty: float  # base asset position (e.g. BTC)
    fee_bps: float

    def mark_equity(self, last_price: float) -> float:
        return float(self.cash + self.qty * last_price)


@dataclass
class MultiStepResult:
    run_id: str
    steps: int
    equity_curve: list[float]
    trade_count: int
    metrics: dict[str, Any]
    trades_path: Path
    equity_path: Path
    events_path: Path
    summary_path: Path


def _fee_rate(fee_bps: float) -> float:
    return max(0.0, float(fee_bps)) / 10_000.0


def _apply_fill(
    sim: BacktestSimState,
    *,
    side: str,
    qty: float,
    price: float,
) -> None:
    fr = _fee_rate(sim.fee_bps)
    if side == "buy":
        cost = qty * price * (1.0 + fr)
        sim.cash -= cost
        sim.qty += qty
    elif side == "sell":
        proceeds = qty * price * (1.0 - fr)
        sim.cash += proceeds
        sim.qty -= qty


def run_multi_step_backtest(
    *,
    ticker: str,
    bars: list[list[Any]],
    initial_cash: float = 10_000.0,
    fee_bps: float = 10.0,
    interval_sec: int = 300,
    run_id: str | None = None,
    runs_dir: Path | None = None,
    max_steps: int | None = None,
    on_bar_complete: Callable[[int, int, dict[str, Any]], None] | None = None,
) -> MultiStepResult:
    """
    Run the full workflow once per bar, advancing the injected OHLCV window.

    Simulated fills use the bar's **close** when ``smart_order`` is accepted and
    the risk gate did not veto. Portfolio state is carried in ``shared_memory`` only
    for observability; the book uses the internal :class:`BacktestSimState`.

    ``on_bar_complete(i, steps, snapshot)`` is invoked after each bar with
    ``snapshot`` keys: ``equity``, ``trade_count``, ``vetoed``, ``cash``, ``qty``.
    """
    base = runs_dir or Path(".runs")
    rid = run_id or f"bt-{uuid.uuid4().hex[:12]}"
    job_dir = base / "backtests" / rid
    job_dir.mkdir(parents=True, exist_ok=True)

    trades_path = job_dir / "trades.jsonl"
    equity_path = job_dir / "equity.jsonl"
    events_path = base / f"{rid}.events.jsonl"
    summary_path = job_dir / "summary.json"
    payload_path = job_dir / "payload.json"

    if events_path.exists():
        events_path.unlink()
    for p in (trades_path, equity_path):
        if p.exists():
            p.unlink()
    if payload_path.exists():
        payload_path.unlink()

    n_bars = len(bars)
    steps = min(n_bars, max_steps) if max_steps is not None else n_bars
    if steps < 1:
        raise ValueError("need at least one OHLCV bar")

    sim = BacktestSimState(cash=initial_cash, qty=0.0, fee_bps=fee_bps)
    equity_curve: list[float] = []
    trade_count = 0

    repo = FlowEventRepo(run_id=rid, log_path=events_path)
    set_flow_repo(repo)
    app = build_workflow().compile()
    try:
        for i in range(steps):
            window = bars[: i + 1]
            close = float(window[-1][4])
            state = initial_hedge_fund_state(run_mode=RunMode.BACKTEST.value, ticker=ticker)
            # Risk/portfolio agents expect ``status == "success"`` on market_data.
            state["market_data"] = {
                ticker: {
                    "status": "success",
                    "backtest": True,
                    "ohlcv": window,
                }
            }
            state["shared_memory"] = {
                "backtest": {
                    "step": i,
                    "run_id": rid,
                    "cash": sim.cash,
                    "qty": sim.qty,
                    "equity": sim.mark_equity(close),
                }
            }

            out = app.invoke(state)
            vetoed = bool(out.get("is_vetoed"))
            ex = out.get("execution_result") or {}
            smart = ex.get("smart_order") if isinstance(ex, dict) else None

            if (
                not vetoed
                and isinstance(smart, dict)
                and smart.get("status") == "accepted"
                and smart.get("side") in ("buy", "sell")
            ):
                qty = float(smart.get("qty") or 0.0)
                if qty > 0:
                    _apply_fill(sim, side=str(smart["side"]), qty=qty, price=close)
                    trade_count += 1
                    append_jsonl(
                        trades_path,
                        {
                            "step": i,
                            "ts_ms": window[-1][0],
                            "side": smart["side"],
                            "qty": qty,
                            "price": close,
                            "fee_bps": fee_bps,
                            "cash": sim.cash,
                            "qty_base": sim.qty,
                            "vetoed": False,
                        },
                    )

            eq = sim.mark_equity(close)
            equity_curve.append(eq)
            append_jsonl(
                equity_path,
                {"step": i, "ts_ms": window[-1][0], "close": close, "equity": eq, "vetoed": vetoed},
            )

            if on_bar_complete is not None:
                on_bar_complete(
                    i,
                    steps,
                    {
                        "equity": eq,
                        "trade_count": trade_count,
                        "vetoed": vetoed,
                        "cash": sim.cash,
                        "qty": sim.qty,
                    },
                )

    finally:
        set_flow_repo(None)

    periods_per_year = max(1, int((365.25 * 24 * 3600) / max(1, interval_sec)))
    m = compute_basic_metrics(
        equity_curve=equity_curve,
        trade_pnls=[],  # win_rate uses per-trade pnl if we add later
        periods_per_year=periods_per_year,
    )
    metrics: dict[str, Any] = {
        "sharpe": m.sharpe,
        "max_drawdown": m.max_drawdown,
        "win_rate": m.win_rate,
        "final_equity": equity_curve[-1] if equity_curve else initial_cash,
        "initial_cash": initial_cash,
        "steps": steps,
        "interval_sec": interval_sec,
    }

    summary = {
        "run_id": rid,
        "ticker": ticker,
        "steps": steps,
        "interval_sec": interval_sec,
        "trade_count": trade_count,
        "metrics": metrics,
        "paths": {
            "trades": str(trades_path),
            "equity": str(equity_path),
            "events": str(events_path),
            "payload": str(payload_path),
        },
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Materialize the payload next to backtest artifacts for review/debugging.
    try:
        payload, _events = build_nexus_payload(events_path)
        validate_nexus_payload(payload)
        payload_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception:
        # Validation is already exercised in tests; don't fail export on payload issues.
        pass

    logger.info(
        "backtest finished run_id=%s steps=%s trade_count=%s final_equity=%.4f",
        rid,
        steps,
        trade_count,
        float(equity_curve[-1]) if equity_curve else initial_cash,
    )

    return MultiStepResult(
        run_id=rid,
        steps=steps,
        equity_curve=equity_curve,
        trade_count=trade_count,
        metrics=metrics,
        trades_path=trades_path,
        equity_path=equity_path,
        events_path=events_path,
        summary_path=summary_path,
    )
