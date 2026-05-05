from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from config.leaderboard_submit import load_leaderboard_submit_config
from leaderboard_submitter import submit_scan_result

logger = logging.getLogger(__name__)


def append_local_scan_result(*, run_id: str, state: dict[str, Any]) -> None:
    """Emit a lightweight local result record for each strategy run.

    This is intentionally decoupled from the platform DB: it writes an append-only JSONL file under
    `.runs/leadpage/` which the leadpage aggregator (and optional worker sync) can ingest.
    """

    rid = (run_id or "").strip()
    if not rid:
        return

    runs_dir = Path(".runs")
    out_path = runs_dir / "leadpage" / "local_scan_results.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    ticker = state.get("ticker")
    exec_res = (
        state.get("execution_result") if isinstance(state.get("execution_result"), dict) else {}
    )
    paper = (
        exec_res.get("paper_account") if isinstance(exec_res.get("paper_account"), dict) else None
    )

    start_cash = float((os.getenv("AIMM_PAPER_START_USDT") or "10000").strip() or "10000")
    cash = float(paper.get("cash_usdt") or 0.0) if isinstance(paper, dict) else 0.0
    realized = float(paper.get("realized_pnl_usdt") or 0.0) if isinstance(paper, dict) else 0.0

    total_return_pct: float | None = None
    if start_cash > 0 and isinstance(paper, dict):
        # For open positions, cash-only delta can look artificially negative (cash deployed into inventory).
        # We approximate equity using cost-basis (qty * avg_entry) when available.
        def _f(x: Any) -> float | None:
            try:
                return float(x)
            except Exception:
                return None

        positions = paper.get("positions")
        if not isinstance(positions, list):
            positions = (
                paper.get("spot_positions") if isinstance(paper.get("spot_positions"), list) else []
            )

        notional_cost = 0.0
        any_pos = False
        for p in positions:
            if not isinstance(p, dict):
                continue
            qty = _f(p.get("qty"))
            avg = _f(p.get("avg_entry"))
            if qty is None or avg is None:
                continue
            any_pos = True
            notional_cost += qty * avg

        equity = cash + (notional_cost if any_pos else 0.0)
        delta = equity - start_cash
        if abs(delta) < 1e-9 and not any_pos:
            # If equity ~= start and no positions, fall back to realized pnl.
            delta = realized
        total_return_pct = (delta / start_cash) * 100.0

    row: dict[str, Any] = {
        "source": "local",
        "ts": int(time.time()),
        "provider": "local",
        "run_id": rid,
        "title": "Local scan",
        "ticker": ticker,
        "total_return_pct": total_return_pct,
        "trade_count": None,
        "meta": {
            "kind": "local_scan",
            "execution_status": exec_res.get("status") if isinstance(exec_res, dict) else None,
            "paper_account": paper,
        },
    }

    try:
        with out_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, default=str) + "\n")
    except OSError:
        logger.warning("Failed to write local scan result: %s", out_path)
        return

    # Auto-submit to leaderboard if enabled
    try:
        lb_cfg = load_leaderboard_submit_config()
        if lb_cfg.enabled:
            summary = {
                "total_return_pct": total_return_pct,
                "total_return_vs_hold_pct": None,
                "sharpe_ratio": None,
                "max_drawdown_pct": None,
                "win_rate_pct": None,
                "total_trades": (
                    row.get("trade_count") if isinstance(row.get("trade_count"), int) else None
                ),
                "avg_hold_bars": None,
                "start_time": None,
                "end_time": None,
                "initial_capital_usd": start_cash,
                "final_value_usd": cash + (notional_cost if any_pos else 0.0),
            }
            exec_res_raw = state.get("execution_result", {})
            exec_res_d = exec_res_raw if isinstance(exec_res_raw, dict) else {}
            run_mode = exec_res_d.get("mode", "paper")
            submit_scan_result(
                ticker=state.get("ticker", ""),
                run_mode=run_mode,
                summary=summary,
                config=lb_cfg,
            )
    except Exception as exc:
        logger.debug("Leaderboard submission (scan) skipped: %s", exc)


__all__ = ["append_local_scan_result"]
