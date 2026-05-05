"""Auto-submit backtest and scan results to the leaderboard API.

Runs after each workflow cycle (or backtest completion) to optionally publish
performance results to a centralized leaderboard server, as well as a local
JSONL fallback.

Opt-in controlled via AIMM_LB_* environment variables (see config/leaderboard_submit.py).
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from config.leaderboard_submit import LeaderboardSubmitConfig, load_leaderboard_submit_config

logger = logging.getLogger(__name__)

LEADPAGE_DIR = Path(".runs") / "leadpage"
LOCAL_SCAN_RESULTS_JSONL = LEADPAGE_DIR / "local_scan_results.jsonl"


def _ensure_local_dir() -> None:
    LEADPAGE_DIR.mkdir(parents=True, exist_ok=True)


def _write_local_jsonl(path: Path, row: dict[str, Any]) -> None:
    _ensure_local_dir()
    with open(path, "a") as f:
        f.write(json.dumps(row, default=str) + "\n")


def _submit_remote(cfg: LeaderboardSubmitConfig, payload: dict[str, Any]) -> bool:
    """POST result to leaderboard server. Returns True on success."""
    url = cfg.leaderboard_url.rstrip("/") + "/leadpage/external_result"
    body = json.dumps(payload).encode("utf-8")
    req = Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-leadpage-provider-key": cfg.provider_key,
            "User-Agent": "AIMM-Leaderboard-Submitter/1.0",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=15) as resp:
            if resp.status == 200:
                logger.info("Leaderboard submission accepted: %s", payload.get("ticker"))
                return True
            logger.warning(
                "Leaderboard submission rejected (HTTP %s): %s", resp.status, resp.read()
            )
            return False
    except Exception as exc:
        logger.warning("Leaderboard submission failed: %s", exc)
        return False


def _build_submit_payload(
    *,
    provider: str,
    ticker: str,
    result_type: str,
    summary: dict[str, Any],
) -> dict[str, Any]:
    """Build the leaderboard external result payload."""
    return {
        "provider": provider,
        "ticker": ticker,
        "result_type": result_type,
        "summary": {
            "total_return_pct": summary.get("total_return_pct") or summary.get("total_return"),
            "total_return_vs_hold_pct": summary.get("total_return_vs_hold_pct")
            or summary.get("excess_return"),
            "sharpe_ratio": summary.get("sharpe_ratio") or summary.get("sharpe"),
            "max_drawdown_pct": summary.get("max_drawdown_pct") or summary.get("max_drawdown"),
            "win_rate_pct": summary.get("win_rate_pct") or summary.get("win_rate"),
            "total_trades": summary.get("total_trades"),
            "avg_hold_bars": summary.get("avg_hold_bars"),
            "start_time": summary.get("start_time"),
            "end_time": summary.get("end_time"),
            "initial_capital_usd": summary.get("initial_capital_usd"),
            "final_value_usd": summary.get("final_value_usd"),
        },
        "submitted_at": int(time.time()),
    }


def submit_scan_result(
    *,
    ticker: str,
    run_mode: str,
    summary: dict[str, Any],
    config: LeaderboardSubmitConfig | None = None,
) -> None:
    """Called after each workflow cycle to optionally submit live/paper scan results."""
    cfg = config or load_leaderboard_submit_config()
    if not cfg.enabled:
        return
    if not cfg.submit_scans:
        logger.debug("Leaderboard scan submission disabled (AIMM_LB_SUBMIT_SCANS=0)")
        return

    result_type = "live_scan" if run_mode == "live" else "paper_scan"
    provider = cfg.provider or "local"

    payload = _build_submit_payload(
        provider=provider,
        ticker=ticker,
        result_type=result_type,
        summary=summary,
    )

    # Always write local fallback
    if cfg.local_fallback:
        _write_local_jsonl(LOCAL_SCAN_RESULTS_JSONL, payload)
        logger.debug("Wrote scan result to local JSONL: %s", ticker)

    # Remote submission
    if cfg.leaderboard_url and cfg.provider_key:
        _submit_remote(cfg, payload)
    elif cfg.leaderboard_url and not cfg.provider_key:
        logger.warning("Leaderboard URL set but no provider key — skipping remote submission")
    else:
        logger.debug("No leaderboard URL configured — local fallback only")


def submit_backtest_result(
    *,
    ticker: str,
    summary: dict[str, Any],
    config: LeaderboardSubmitConfig | None = None,
) -> None:
    """Called after backtest to submit results to leaderboard."""
    cfg = config or load_leaderboard_submit_config()
    if not cfg.enabled:
        return
    if not cfg.submit_backtests:
        logger.debug("Leaderboard backtest submission disabled (AIMM_LB_SUBMIT_BACKTESTS=0)")
        return

    provider = cfg.provider or "local"

    payload = _build_submit_payload(
        provider=provider,
        ticker=ticker,
        result_type="backtest",
        summary=summary,
    )

    if cfg.local_fallback:
        _write_local_jsonl(LOCAL_SCAN_RESULTS_JSONL, payload)

    if cfg.leaderboard_url and cfg.provider_key:
        _submit_remote(cfg, payload)
    elif cfg.leaderboard_url and not cfg.provider_key:
        logger.warning("Leaderboard URL set but no provider key — skipping remote submission")
    else:
        logger.debug("No leaderboard URL configured — local fallback only")
