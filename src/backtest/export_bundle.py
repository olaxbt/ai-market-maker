"""Export bundle writer — CSV/ledger/manifest for backtest analysis.

Generates the files analysts expect after every backtest run:
- trades_record.csv — flat round-trip trade ledger
- equity_curve.csv — bar-by-bar equity with drawdown
- audit_trail_ledger.jsonl — merged chronological audit stream
- export_manifest.json — schema version, file list, run config hash
"""

from __future__ import annotations

import csv
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CSV_DIALECT = "unix"


def _safe(val: Any, default: str = "") -> str:
    """Convert a value to string, returning default on None."""
    if val is None:
        return default
    return str(val)


def _fmt_ts_ms(ts_ms: int | float | None) -> str:
    """Format epoch ms to ISO-8601 UTC string, or empty."""
    if not ts_ms:
        return ""
    try:
        return datetime.fromtimestamp(float(ts_ms) / 1000, tz=timezone.utc).isoformat()
    except (ValueError, OSError):
        return _safe(ts_ms)


def write_trades_csv(trades: list[dict[str, Any]], path: Path) -> None:
    """Write ``trades_record.csv`` — one row per closed round-trip."""
    fields = [
        "run_id",
        "trade_id",
        "symbol",
        "side",
        "entry_ts_ms",
        "exit_ts_ms",
        "entry_bar_index",
        "exit_bar_index",
        "entry_price",
        "exit_price",
        "size",
        "leverage",
        "pnl_usd",
        "pnl_pct",
        "commission_usd",
        "holding_bars",
        "exit_reason",
    ]
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, dialect=CSV_DIALECT)
        w.writeheader()
        for i, t in enumerate(trades):
            direction = t.get("direction", 0)
            side = "long" if direction > 0 else ("short" if direction < 0 else "")
            w.writerow(
                {
                    "run_id": _safe(t.get("run_id")),
                    "trade_id": i + 1,
                    "symbol": _safe(t.get("symbol")),
                    "side": side,
                    "entry_ts_ms": _safe(t.get("entry_ts_ms")),
                    "exit_ts_ms": _safe(t.get("exit_ts_ms")),
                    "entry_bar_index": _safe(t.get("entry_bar_index")),
                    "exit_bar_index": _safe(t.get("exit_bar_index")),
                    "entry_price": _safe(t.get("entry_price")),
                    "exit_price": _safe(t.get("exit_price")),
                    "size": _safe(t.get("size")),
                    "leverage": _safe(t.get("leverage")),
                    "pnl_usd": _safe(t.get("pnl")),
                    "pnl_pct": _safe(t.get("pnl_pct")),
                    "commission_usd": _safe(t.get("commission")),
                    "holding_bars": _safe(t.get("holding_bars")),
                    "exit_reason": _safe(t.get("exit_reason")),
                }
            )


def write_equity_csv(snapshots: list[dict[str, Any]], path: Path) -> None:
    """Write ``equity_curve.csv`` with bar index, timestamps, and drawdown."""
    fields = [
        "bar_index",
        "ts_ms",
        "ts_utc",
        "capital",
        "unrealized_pnl",
        "equity",
        "positions",
        "drawdown_pct",
    ]
    peak = float("-inf")
    records: list[dict[str, Any]] = []
    for idx, s in enumerate(snapshots):
        ts_ms = int(s.get("ts", s.get("timestamp", 0)))
        eq = float(s.get("equity", 0.0))
        if eq > peak:
            peak = eq
        dd = ((eq - peak) / peak * 100) if peak > 0 else 0.0
        records.append(
            {
                "bar_index": idx,
                "ts_ms": ts_ms,
                "ts_utc": _fmt_ts_ms(ts_ms),
                "capital": round(float(s.get("capital", 0.0)), 8),
                "unrealized_pnl": round(float(s.get("unrealized_pnl", 0.0)), 8),
                "equity": round(eq, 8),
                "positions": int(s.get("position_count", s.get("positions", 0))),
                "drawdown_pct": round(dd, 4),
            }
        )
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, dialect=CSV_DIALECT)
        w.writeheader()
        w.writerows(records)


def write_audit_ledger(
    run_dir: Path,
    path: Path,
    *,
    run_id: str,
    events_path: Path | None = None,
) -> None:
    """Merge iterations + flow events into a chronological audit stream.

    Inputs from ``run_dir``:
        - ``iterations.jsonl`` — per-bar decision rows (type=``decision``)
        - ``events_path`` — optional flow events (type=``flow``)

    Output sorted by ``(bar_index, seq)`` then ``ts_ms``.
    """
    rows: list[dict[str, Any]] = []

    iter_path = run_dir / "iterations.jsonl"
    if iter_path.is_file():
        seq = 0
        try:
            for line in iter_path.read_text().splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                seq += 1

                ts_ms = (
                    row.get("ts")
                    or row.get("ts_ms")
                    or row.get("timestamp")
                    or row.get("bar_time_ms", 0)
                )
                if ts_ms and ts_ms < 1e13:
                    ts_ms = int(ts_ms * 1000)
                else:
                    ts_ms = int(ts_ms) if ts_ms else 0

                bar_idx = row.get("bar_index", row.get("index", 0))

                dec = row.get("decision") if isinstance(row.get("decision"), dict) else {}
                dec_action = str(dec.get("action") or row.get("action", ""))
                dec_confidence = float(dec.get("confidence") or row.get("confidence", 0.0))
                dec_stance = str(dec.get("stance") or row.get("stance", ""))
                trade_intent = (
                    dec.get("trade_intent")
                    if isinstance(dec.get("trade_intent"), dict)
                    else row.get("trade_intent", {})
                )

                rows.append(
                    {
                        "seq": seq,
                        "ts_ms": ts_ms,
                        "run_id": run_id,
                        "bar_index": int(bar_idx) if bar_idx else 0,
                        "symbol": str(row.get("symbol", "")),
                        "event_type": "decision",
                        "decision": {
                            "action": dec_action,
                            "confidence": dec_confidence,
                            "stance": dec_stance,
                            "trade_intent": trade_intent,
                        },
                        "tier0_summary": row.get("tier0_summary", []),
                        "data_quality": row.get("data_quality"),
                        "memory_fragment": row.get("memory") or row.get("memory_fragment"),
                    }
                )
        except OSError:
            logger.warning("Could not read %s for audit ledger", iter_path)

    if events_path and events_path.is_file():
        try:
            for line in events_path.read_text().splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    evt = json.loads(line)
                except json.JSONDecodeError:
                    continue
                bar_ts = evt.get("bar_time_utc_ms", evt.get("timestamp_ms", 0))
                rows.append(
                    {
                        "seq": 0,
                        "ts_ms": int(bar_ts) if bar_ts else 0,
                        "run_id": run_id,
                        "bar_index": -1,
                        "event_type": "flow",
                        "flow_node": evt.get("node", ""),
                        "flow_status": evt.get("status", ""),
                    }
                )
        except OSError:
            logger.warning("Could not read events at %s", events_path)

    rows.sort(key=lambda r: (r["bar_index"], r["seq"], r["ts_ms"]))

    with path.open("w") as f:
        for row in rows:
            ts_ms = row.pop("ts_ms", 0)
            row["ts_ms"] = int(ts_ms)
            if ts_ms:
                row["ts_utc"] = _fmt_ts_ms(ts_ms)
            f.write(json.dumps(row, default=str) + "\n")


def write_export_manifest(
    path: Path,
    *,
    run_id: str,
    summary: dict[str, Any],
    files_written: dict[str, str],
    symbols: list[str],
    total_bars: int,
) -> None:
    """Write ``export_manifest.json`` with schema version and metrics summary."""
    metrics = summary.get("metrics", summary)
    quality = summary.get("quality_report", {})
    per_sym = os.environ.get("AIMM_BACKTEST_PER_SYMBOL_INVOKE", "").strip() == "1"
    manifest = {
        "schema_version": "backtest_export/v1",
        "run_id": run_id,
        "created_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        "arbitrator_mode": summary.get(
            "arbitrator_mode", summary.get("resolved_config", {}).get("arbitrator_mode", "")
        ),
        "interval_sec": summary.get(
            "interval_sec", summary.get("resolved_config", {}).get("interval_sec", 300)
        ),
        "timeframe": summary.get("timeframe", ""),
        "symbols": symbols,
        "total_bars": total_bars,
        "files": files_written,
        "metrics_summary": {
            "total_return_pct": metrics.get("total_return_pct"),
            "sharpe": metrics.get("sharpe"),
            "total_pnl_usd": metrics.get("total_pnl_usd", metrics.get("total_pnl")),
            "quality_overall_passed": quality.get("overall_passed", quality.get("passed")),
        },
        "invoke_cache": {
            "shared": not per_sym,
            "per_symbol": per_sym,
        },
    }
    path.write_text(json.dumps(manifest, indent=2, default=str))


def write_analysis_bundle(
    run_dir: Path,
    *,
    run_id: str,
    summary: dict[str, Any],
    trades: list[dict[str, Any]] | None = None,
    snapshots: list[dict[str, Any]] | None = None,
    events_path: Path | None = None,
    symbols: list[str] | None = None,
    total_bars: int | None = None,
) -> dict[str, str]:
    """Write all analysis bundle files and return a ``{name: relpath}`` map.

    Returns
    -------
    dict mapping logical file names to relative paths (e.g.
    ``{"trades_record_csv": "trades_record.csv", ...}``).
    """
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    files_written: dict[str, str] = {}

    if trades:
        csv_path = run_dir / "trades_record.csv"
        write_trades_csv(trades, csv_path)
        files_written["trades_record_csv"] = csv_path.name

    if snapshots:
        csv_path = run_dir / "equity_curve.csv"
        write_equity_csv(snapshots, csv_path)
        files_written["equity_curve_csv"] = csv_path.name

    ledger_path = run_dir / "audit_trail_ledger.jsonl"
    write_audit_ledger(
        run_dir,
        ledger_path,
        run_id=run_id,
        events_path=events_path,
    )
    files_written["audit_trail_ledger_jsonl"] = ledger_path.name

    manifest_path = run_dir / "export_manifest.json"
    write_export_manifest(
        manifest_path,
        run_id=run_id,
        summary=summary,
        files_written=files_written,
        symbols=symbols or [],
        total_bars=total_bars or 0,
    )
    files_written["export_manifest_json"] = manifest_path.name

    logger.info(
        "export_bundle written to %s: %s",
        run_dir,
        ", ".join(files_written.values()),
    )
    return files_written
