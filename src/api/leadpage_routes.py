"""Leadpage / leaderboard endpoints.

Goal: provide a simple durable "public results" surface that can aggregate:
- local backtest summaries under `.runs/backtests/<run_id>/summary.json`
- externally submitted result summaries appended to `.runs/leadpage/external_results.jsonl`

This is intentionally lightweight (JSONL + filesystem) so it works in local dev,
OpenClaw-style sandboxes, and simple container deployments without a DB.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import numbers
import os
import secrets
import time
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from api.leadpage_validation import validate_result
from api.wallet_auth import (
    generate_provider_key,
    make_challenge,
    verify_wallet_signature,
    wallet_to_email,
)
from config.leaderboard_submit import load_leaderboard_submit_config, mask_key
from config.runs_paths import runs_dir as _resolved_runs_dir
from storage.leadpage_db import LeadpageProvider, LeadpageUser
from storage.leadpage_db import (
    active_provider_secret_digest as _db_active_secret_digest,
)
from storage.leadpage_db import (
    database_url as _db_url,
)
from storage.leadpage_db import (
    insert_result as _db_insert_result,
)
from storage.leadpage_db import (
    leaderboard_rows as _db_leaderboard_rows,
)
from storage.leadpage_db import (
    list_providers as _db_list_providers,
)
from storage.leadpage_db import (
    nonce_seen as _db_nonce_seen,
)
from storage.leadpage_db import (
    provider_rows as _db_provider_rows,
)
from storage.leadpage_db import (
    record_nonce as _db_record_nonce,
)

RUNS_DIR = _resolved_runs_dir()
BACKTESTS_DIR = RUNS_DIR / "backtests"
LEADPAGE_DIR = RUNS_DIR / "leadpage"
EXTERNAL_RESULTS_JSONL = LEADPAGE_DIR / "external_results.jsonl"
LOCAL_SCAN_RESULTS_JSONL = LEADPAGE_DIR / "local_scan_results.jsonl"

router = APIRouter(tags=["leadpage"])

PROVIDER_KEYS_ENV = "LEADPAGE_PROVIDER_KEYS"
REQUIRE_KEYS_ENV = "LEADPAGE_REQUIRE_KEYS"
REQUIRE_SIGNED_ENV = "LEADPAGE_REQUIRE_SIGNED"
SIGNED_MAX_SKEW_SEC_ENV = "LEADPAGE_SIGNED_MAX_SKEW_SEC"
NONCES_JSONL = LEADPAGE_DIR / "nonces.jsonl"


def _leaderboard_row_completeness(row: dict[str, Any]) -> int:
    keys = (
        "total_return_pct",
        "sharpe",
        "max_drawdown_pct",
        "trade_count",
        "win_rate",
        "change_pct",
    )
    return sum(1 for k in keys if row.get(k) is not None)


def _dedupe_leaderboard_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse duplicate (provider, run_id) rows, keeping the richest payload."""
    out_map: dict[tuple[str, str], dict[str, Any]] = {}
    tail: list[dict[str, Any]] = []
    for r in rows:
        rid = r.get("run_id")
        if not isinstance(rid, str) or not rid.strip():
            tail.append(r)
            continue
        prov = str(r.get("provider") or "local").strip() or "local"
        k = (prov, rid.strip())
        old = out_map.get(k)
        if old is None:
            out_map[k] = r
            continue
        s_new = _leaderboard_row_completeness(r)
        s_old = _leaderboard_row_completeness(old)
        if s_new > s_old:
            out_map[k] = r
        elif s_new == s_old and old.get("source") != "local" and r.get("source") == "local":
            out_map[k] = r
    return [*tail, *out_map.values()]


def _overlay_disk_summary_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fill gaps from ``.runs/backtests/<run_id>/summary.json`` when Postgres/JSONL rows are stale or partial."""
    out: list[dict[str, Any]] = []
    for row in rows:
        rid = row.get("run_id")
        if not isinstance(rid, str) or not rid.strip():
            out.append(row)
            continue
        summary = _load_local_summary(rid.strip())
        if not summary:
            out.append(row)
            continue
        disk = _leaderboard_row_from_summary(run_id=rid.strip(), summary=summary)
        merged = dict(row)
        for k, v in disk.items():
            if merged.get(k) is None and v is not None:
                merged[k] = v
        out.append(merged)
    return out


def _provider_keys() -> dict[str, str]:
    """Return provider -> shared secret, sourced from env.

    Supported formats:
    - JSON: {"providerA":"keyA","providerB":"keyB"}
    - CSV: providerA:keyA,providerB:keyB
    """
    raw = (os.getenv(PROVIDER_KEYS_ENV) or "").strip()
    if not raw:
        return {}

    if raw.startswith("{"):
        try:
            obj = json.loads(raw)
        except Exception:
            return {}
        if not isinstance(obj, dict):
            return {}
        out: dict[str, str] = {}
        for k, v in obj.items():
            if isinstance(k, str) and isinstance(v, str) and k.strip() and v.strip():
                out[k.strip()] = v.strip()
        return out

    out2: dict[str, str] = {}
    for part in [p.strip() for p in raw.split(",") if p.strip()]:
        if ":" not in part:
            continue
        prov, key = part.split(":", 1)
        prov = prov.strip()
        key = key.strip()
        if prov and key:
            out2[prov] = key
    return out2


def _keys_required() -> bool:
    v = (os.getenv(REQUIRE_KEYS_ENV) or "").strip()
    return v in {"1", "true", "TRUE", "yes", "YES"}


def _signed_required() -> bool:
    v = (os.getenv(REQUIRE_SIGNED_ENV) or "").strip()
    return v in {"1", "true", "TRUE", "yes", "YES"}


def _signed_max_skew_sec() -> int:
    raw = (os.getenv(SIGNED_MAX_SKEW_SEC_ENV) or "").strip() or "300"
    try:
        v = int(raw)
    except Exception:
        v = 300
    return max(30, min(3600, v))


def _presented_provider_key(request: Request) -> str | None:
    # Prefer explicit provider key header; allow generic X-API-Key for gateways.
    k = (request.headers.get("x-leadpage-provider-key") or "").strip()
    if k:
        return k
    k2 = (request.headers.get("x-api-key") or "").strip()
    return k2 or None


def _auth_provider_or_401(request: Request, provider: str) -> None:
    keys = _provider_keys()
    if not keys:
        if _keys_required():
            raise HTTPException(
                status_code=401,
                detail=f"{PROVIDER_KEYS_ENV} is not set but {REQUIRE_KEYS_ENV}=1 requires auth",
            )
        return
    expected = keys.get(provider)
    if not expected:
        raise HTTPException(status_code=401, detail=f"unknown provider: {provider}")
    presented = _presented_provider_key(request)
    if presented != expected:
        raise HTTPException(
            status_code=401,
            detail="unauthorized (set x-leadpage-provider-key or x-api-key)",
        )


def _auth_provider_db_or_env_or_401(request: Request, provider: str) -> None:
    """Auth providers using DB secrets when DATABASE_URL is set; else env keys."""
    presented = _presented_provider_key(request)
    if not presented:
        raise HTTPException(status_code=401, detail="missing provider key header")
    if _db_url():
        digest = _db_active_secret_digest(provider)
        if digest:
            presented_digest = hashlib.sha256(presented.encode("utf-8")).hexdigest()
            if not hmac.compare_digest(presented_digest, digest):
                raise HTTPException(status_code=401, detail="unauthorized")
            return
    _auth_provider_or_401(request, provider)


def _presented_signature(request: Request) -> tuple[str | None, int | None, str | None]:
    sig = (request.headers.get("x-leadpage-signature") or "").strip() or None
    ts_raw = (request.headers.get("x-leadpage-timestamp") or "").strip()
    nonce = (request.headers.get("x-leadpage-nonce") or "").strip() or None
    if not ts_raw:
        return sig, None, nonce
    try:
        ts = int(ts_raw)
    except Exception:
        ts = None
    return sig, ts, nonce


def _canonical_message(*, provider: str, ts: int, nonce: str, body_bytes: bytes) -> bytes:
    # Stable, explicit format. Provider binds signature to the namespace; body binds exact payload.
    # Prefix with a version tag so we can evolve without ambiguity.
    h = hashlib.sha256(body_bytes).hexdigest()
    msg = f"v1\nprovider:{provider}\nts:{ts}\nnonce:{nonce}\nbody_sha256:{h}\n"
    return msg.encode("utf-8")


def _hmac_hex(key: str, msg: bytes) -> str:
    return hmac.new(key.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def _nonce_seen(provider: str, nonce: str, *, now_ts: int, skew_sec: int) -> bool:
    """Best-effort replay protection.

    Uses a JSONL append-only store. We only scan a bounded tail window (recent lines),
    and we prune opportunistically by max bytes to keep it fast.
    """
    if not nonce:
        return False
    if _db_url():
        min_ts = now_ts - max(120, skew_sec * 4)
        return bool(_db_nonce_seen(provider, nonce, min_ts=min_ts))
    try:
        if not NONCES_JSONL.exists():
            return False
        # Scan tail lines only (fast, bounded). Keep enough to cover a few skew windows.
        tail_limit = 2500
        rows = _read_jsonl(NONCES_JSONL, limit=tail_limit)
        # Rows are oldest->newest due to read order. That's ok for membership check.
        min_ts = now_ts - max(120, skew_sec * 4)
        for r in rows:
            if not isinstance(r, dict):
                continue
            if r.get("provider") != provider:
                continue
            if r.get("nonce") != nonce:
                continue
            ts = r.get("ts")
            if isinstance(ts, int) and ts >= min_ts:
                return True
    except Exception:
        return False
    return False


def _record_nonce(provider: str, nonce: str, *, ts: int) -> None:
    if not nonce:
        return
    if _db_url():
        _db_record_nonce(provider, nonce)
        return
    _append_jsonl(NONCES_JSONL, {"ts": int(ts), "provider": provider, "nonce": nonce})
    # Opportunistic prune: keep file size modest.
    try:
        if NONCES_JSONL.exists() and NONCES_JSONL.stat().st_size > 2_000_000:  # ~2MB
            # Keep last N lines by rewriting; use existing helper semantics.
            lines = NONCES_JSONL.read_text(encoding="utf-8").splitlines()[-4000:]
            NONCES_JSONL.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    except OSError:
        return


async def _auth_signed_or_401(request: Request, *, provider: str, body_bytes: bytes) -> None:
    """If signatures are configured/required, validate HMAC signature.

    Headers:
    - x-leadpage-signature: hex(HMAC_SHA256(key, canonical_message))
    - x-leadpage-timestamp: unix epoch seconds (int)
    - x-leadpage-nonce: random string (replay protection)
    """
    keys = _provider_keys()
    if not keys:
        # No keys -> cannot validate HMAC; treat as unsigned environment.
        if _signed_required():
            raise HTTPException(
                status_code=401,
                detail=f"{PROVIDER_KEYS_ENV} is not set but {REQUIRE_SIGNED_ENV}=1 requires signatures",
            )
        return

    key = keys.get(provider)
    if not key:
        raise HTTPException(status_code=401, detail=f"unknown provider: {provider}")

    sig, ts, nonce = _presented_signature(request)
    if not sig or ts is None or not nonce:
        raise HTTPException(
            status_code=401,
            detail="missing signature headers (x-leadpage-signature, x-leadpage-timestamp, x-leadpage-nonce)",
        )

    now = int(time.time())
    skew = _signed_max_skew_sec()
    if abs(now - int(ts)) > skew:
        raise HTTPException(status_code=401, detail="timestamp outside allowed skew window")

    if _nonce_seen(provider, nonce, now_ts=now, skew_sec=skew):
        raise HTTPException(status_code=401, detail="replayed nonce")

    msg = _canonical_message(provider=provider, ts=int(ts), nonce=str(nonce), body_bytes=body_bytes)
    expected = _hmac_hex(key, msg)
    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=401, detail="invalid signature")

    _record_nonce(provider, str(nonce), ts=now)


def _read_jsonl(path: Path, *, limit: int | None = None) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if limit is not None and len(rows) >= limit:
                    break
                s = (line or "").strip()
                if not s:
                    continue
                try:
                    obj = json.loads(s)
                except Exception:
                    continue
                if isinstance(obj, dict):
                    rows.append(obj)
    except OSError:
        return []
    return rows


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, default=str) + "\n")


def _load_local_summary(run_id: str) -> dict[str, Any] | None:
    p = BACKTESTS_DIR / run_id / "summary.json"
    if not p.is_file():
        return None
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _float_or_none(v: Any) -> float | None:
    """Coerce scalars for leaderboard math (handles numpy / Decimal from JSON or ORM)."""
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, numbers.Real):
        try:
            x = float(v)
            return x if math.isfinite(x) else None
        except Exception:
            return None
    try:
        x = float(str(v).strip())
        return x if math.isfinite(x) else None
    except Exception:
        return None


def _leaderboard_row_from_summary(*, run_id: str, summary: dict[str, Any]) -> dict[str, Any]:
    evaluation = summary.get("evaluation") if isinstance(summary.get("evaluation"), dict) else {}
    metrics = summary.get("metrics") if isinstance(summary.get("metrics"), dict) else {}
    bench = summary.get("benchmark") if isinstance(summary.get("benchmark"), dict) else {}

    if evaluation.get("total_return_pct") is not None:
        total_return_pct = _float_or_none(evaluation.get("total_return_pct"))
    elif metrics.get("total_return_pct") is not None:
        total_return_pct = _float_or_none(metrics.get("total_return_pct"))
    else:
        total_return_pct = _float_or_none(bench.get("strategy_total_return_pct"))
    sharpe = _float_or_none(metrics.get("sharpe"))
    if sharpe is None:
        sharpe = _float_or_none(metrics.get("sharpe_ratio"))

    mdd_pct = None
    raw_mdd_pct = metrics.get("max_drawdown_pct")
    if raw_mdd_pct is not None:
        mdd_pct = _float_or_none(raw_mdd_pct)
    if mdd_pct is None:
        mdd_frac = _float_or_none(metrics.get("max_drawdown"))
        if isinstance(mdd_frac, float):
            # Heuristic: stored as fraction (0–1) vs already percent (e.g. 12.3)
            mdd_pct = mdd_frac * 100.0 if abs(mdd_frac) <= 1.0 else mdd_frac

    trade_count = summary.get("trade_count")
    if not isinstance(trade_count, (int, float)):
        for k in ("total_trades", "n_trades", "trades", "num_trades"):
            tv = metrics.get(k)
            if isinstance(tv, (int, float)):
                trade_count = tv
                break

    # Prefer explicit percent; legacy summaries store win_rate as 0–1 fraction.
    win = _float_or_none(metrics.get("win_rate_pct"))
    if win is None:
        wr = _float_or_none(metrics.get("win_rate"))
        if wr is not None:
            win = wr * 100.0 if abs(wr) <= 1.0 else wr

    # "Change" = excess vs buy-and-hold (or equal-weight) when benchmark block exists.
    change_pct: float | None = None
    if isinstance(bench, dict):
        change_pct = _float_or_none(bench.get("excess_return_vs_buy_hold_equity_pct"))
    if change_pct is None and isinstance(evaluation, dict):
        change_pct = _float_or_none(
            evaluation.get("total_return_vs_hold_pct") or evaluation.get("excess_return_pct")
        )
    if change_pct is None:
        change_pct = _float_or_none(summary.get("total_return_vs_hold_pct"))
    if (
        change_pct is None
        and isinstance(bench, dict)
        and isinstance(total_return_pct, (int, float))
    ):
        bh = _float_or_none(bench.get("benchmark_buy_hold_equity_return_pct"))
        ew = _float_or_none(bench.get("benchmark_equal_weight_equity_return_pct"))
        if bh is not None:
            change_pct = float(total_return_pct) - bh
        elif ew is not None:
            change_pct = float(total_return_pct) - ew

    # Perp summaries (and some API responses) expose cash/equity at top level without metrics.
    if total_return_pct is None:
        init = _float_or_none(summary.get("initial_cash"))
        fin = _float_or_none(summary.get("final_equity"))
        if init is not None and init > 0 and fin is not None:
            total_return_pct = (float(fin) - float(init)) / float(init) * 100.0

    # Unix seconds for web "When" column (summary uses end_ts in ms).
    ts_out: int | None = None
    raw_ts = summary.get("ts")
    if isinstance(raw_ts, (int, float)) and raw_ts > 0:
        ts_out = int(raw_ts // 1000) if raw_ts > 10_000_000_000 else int(raw_ts)
    else:
        end_ts = summary.get("end_ts")
        if isinstance(end_ts, (int, float)) and end_ts > 0:
            ts_out = int(end_ts // 1000) if end_ts > 10_000_000_000 else int(end_ts)

    syms = summary.get("symbols")
    ticker = summary.get("ticker")
    if not ticker and isinstance(syms, list) and syms:
        ticker = str(syms[0])

    return {
        "source": "local",
        "provider": "local",
        "ts": ts_out,
        "run_id": run_id,
        "title": summary.get("strategy", {}).get("title")
        if isinstance(summary.get("strategy"), dict)
        else None,
        "ticker": ticker,
        "steps": summary.get("steps") or summary.get("total_bars"),
        "trade_count": int(trade_count) if isinstance(trade_count, (int, float)) else None,
        "total_return_pct": total_return_pct,
        "sharpe": sharpe,
        "max_drawdown_pct": mdd_pct,
        "win_rate": win,
        "change_pct": change_pct,
        "profit_factor": _float_or_none(metrics.get("profit_factor")),
    }


def _enrich_leaderboard_row_from_meta_summary(row: dict[str, Any]) -> dict[str, Any]:
    """Fill optional columns from ``meta.summary`` (e.g. DB rows from local backtest insert)."""
    meta = row.get("meta")
    if not isinstance(meta, dict):
        return row
    summary = meta.get("summary")
    if not isinstance(summary, dict):
        return row
    run_id = str(row.get("run_id") or summary.get("run_id") or "").strip()
    if not run_id:
        return row
    derived = _leaderboard_row_from_summary(run_id=run_id, summary=summary)
    out = dict(row)
    for k in (
        "total_return_pct",
        "sharpe",
        "max_drawdown_pct",
        "trade_count",
        "win_rate",
        "change_pct",
        "ticker",
        "title",
    ):
        if out.get(k) is None and derived.get(k) is not None:
            out[k] = derived[k]
    return out


def _local_backtest_history_rows_from_disk(*, limit: int) -> list[dict[str, Any]]:
    """History rows for provider ``local``, shaped like ``provider_rows`` output, from ``summary.json``."""
    out: list[dict[str, Any]] = []
    if not BACKTESTS_DIR.is_dir():
        return out
    lim = max(1, int(limit))
    for p in sorted(BACKTESTS_DIR.iterdir(), key=lambda x: x.name, reverse=True):
        if len(out) >= lim:
            break
        if not p.is_dir():
            continue
        run_id = p.name
        summary = _load_local_summary(run_id)
        if not summary:
            continue
        lb = _leaderboard_row_from_summary(run_id=run_id, summary=summary)
        ts_raw = lb.get("ts")
        ts_out = (
            int(ts_raw) if isinstance(ts_raw, (int, float)) and ts_raw > 0 else int(time.time())
        )
        out.append(
            {
                "source": "local",
                "ts": ts_out,
                "schema_version": 1,
                "provider": "local",
                "run_id": run_id,
                "title": lb.get("title"),
                "ticker": lb.get("ticker"),
                "total_return_pct": lb.get("total_return_pct"),
                "sharpe": lb.get("sharpe"),
                "max_drawdown_pct": lb.get("max_drawdown_pct"),
                "trade_count": lb.get("trade_count"),
                "meta": {"kind": "local_backtest_summary", "summary": summary},
            }
        )
    return out


def _merge_local_provider_history_rows(
    *,
    disk_rows: list[dict[str, Any]],
    db_rows: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    """Prefer on-disk ``summary.json`` per ``run_id``; add DB-only runs without a disk tree."""
    by_run: dict[str, dict[str, Any]] = {}
    for r in db_rows:
        rid = r.get("run_id")
        if isinstance(rid, str) and rid.strip():
            by_run[rid.strip()] = dict(r)
    for r in disk_rows:
        rid = r.get("run_id")
        if isinstance(rid, str) and rid.strip():
            by_run[rid.strip()] = dict(r)
    merged = sorted(by_run.values(), key=lambda x: int(x.get("ts") or 0), reverse=True)
    return merged[: max(1, int(limit))]


class ExternalResult(BaseModel):
    """Minimal schema for importing other people's results into this engine."""

    schema_version: int = Field(
        1, ge=1, le=10, description="Result schema version for forward compatibility."
    )
    provider: str = Field(..., min_length=1, max_length=80, description="Who produced the result")
    run_id: str = Field(..., min_length=1, max_length=120, description="Provider run id")
    title: str | None = Field(None, max_length=160)
    ticker: str | None = Field(None, max_length=60)
    total_return_pct: float | None = Field(None, description="Total return in percent, e.g. 12.3")
    sharpe: float | None = Field(None)
    max_drawdown_pct: float | None = Field(None)
    trade_count: int | None = Field(None, ge=0, le=10_000_000)
    meta: dict[str, Any] | None = Field(
        None, description="Optional extra metadata (e.g. timeframe, fees, notes)"
    )


@router.post("/leadpage/results")
async def post_external_result(result: ExternalResult, request: Request) -> dict[str, Any]:
    """Append an externally produced result to the leadpage ledger (JSONL)."""
    body = await request.body()
    if _signed_required():
        await _auth_signed_or_401(request, provider=result.provider, body_bytes=body)
    else:
        # Accept either signed or key-based auth. If signature headers are present, validate them.
        sig, ts, nonce = _presented_signature(request)
        if sig or ts is not None or nonce:
            await _auth_signed_or_401(request, provider=result.provider, body_bytes=body)
        else:
            _auth_provider_db_or_env_or_401(request, result.provider)

    # ── Fraud protection: validate result before storing ──
    val_errors = validate_result(result.model_dump() if hasattr(result, "model_dump") else {})
    if val_errors:
        raise HTTPException(
            status_code=422, detail=f"Result validation failed: {'; '.join(val_errors)}"
        )

    row = {
        "source": "external",
        "ts": int(time.time()),
        "schema_version": int(result.schema_version),
        "provider": result.provider,
        "run_id": result.run_id,
        "title": result.title,
        "ticker": result.ticker,
        "total_return_pct": result.total_return_pct,
        "sharpe": result.sharpe,
        "max_drawdown_pct": result.max_drawdown_pct,
        "trade_count": result.trade_count,
        "meta": result.meta or {},
    }
    if _db_url():
        stored = _db_insert_result(
            provider=result.provider,
            run_id=result.run_id,
            schema_version=int(result.schema_version),
            title=result.title,
            ticker=result.ticker,
            total_return_pct=result.total_return_pct,
            sharpe=result.sharpe,
            max_drawdown_pct=result.max_drawdown_pct,
            trade_count=result.trade_count,
            meta=result.meta or {},
        )
        row["ts"] = stored.ts
    else:
        _append_jsonl(EXTERNAL_RESULTS_JSONL, row)
    return {"ok": True, "stored": row}


@router.post("/leadpage/providers/{provider}/results")
async def post_provider_result(
    provider: str, result: ExternalResult, request: Request
) -> dict[str, Any]:
    """Provider-scoped ingest endpoint (recommended)."""
    if result.provider != provider:
        raise HTTPException(status_code=400, detail="provider mismatch (path vs body)")
    body = await request.body()
    if _signed_required():
        await _auth_signed_or_401(request, provider=provider, body_bytes=body)
    else:
        sig, ts, nonce = _presented_signature(request)
        if sig or ts is not None or nonce:
            await _auth_signed_or_401(request, provider=provider, body_bytes=body)
        else:
            _auth_provider_db_or_env_or_401(request, provider)
    row = {
        "source": "external",
        "ts": int(time.time()),
        "schema_version": int(result.schema_version),
        "provider": provider,
        "run_id": result.run_id,
        "title": result.title,
        "ticker": result.ticker,
        "total_return_pct": result.total_return_pct,
        "sharpe": result.sharpe,
        "max_drawdown_pct": result.max_drawdown_pct,
        "trade_count": result.trade_count,
        "meta": result.meta or {},
    }
    if _db_url():
        stored = _db_insert_result(
            provider=provider,
            run_id=result.run_id,
            schema_version=int(result.schema_version),
            title=result.title,
            ticker=result.ticker,
            total_return_pct=result.total_return_pct,
            sharpe=result.sharpe,
            max_drawdown_pct=result.max_drawdown_pct,
            trade_count=result.trade_count,
            meta=result.meta or {},
        )
        row["ts"] = stored.ts
    else:
        _append_jsonl(EXTERNAL_RESULTS_JSONL, row)
    return {"ok": True, "stored": row}


@router.post("/leadpage/external_result")
async def post_external_result_leaderboard_submit(request: Request) -> dict[str, Any]:
    """Canonical leaderboard ingest (AIMM submitter & OpenAPI `/leadpage/external_result`).

    Accepts summarized backtest/live/paper scan payloads; maps into `LeadpageResult` / JSONL.
    """
    body_bytes = await request.body()
    try:
        payload = json.loads(body_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="invalid JSON body") from exc

    provider = str(payload.get("provider") or "").strip()
    ticker = str(payload.get("ticker") or "").strip()
    if not provider or not ticker:
        raise HTTPException(status_code=422, detail="provider and ticker are required")

    if _signed_required():
        await _auth_signed_or_401(request, provider=provider, body_bytes=body_bytes)
    else:
        sig, ts, nonce = _presented_signature(request)
        if sig or ts is not None or nonce:
            await _auth_signed_or_401(request, provider=provider, body_bytes=body_bytes)
        else:
            _auth_provider_db_or_env_or_401(request, provider)

    val_errors = validate_result(payload if isinstance(payload, dict) else {})
    if val_errors:
        raise HTTPException(status_code=422, detail={"errors": val_errors})

    summary_raw = payload.get("summary") or {}
    summary = summary_raw if isinstance(summary_raw, dict) else {}

    result_type_raw = payload.get("result_type", "")
    result_type_str = (
        result_type_raw if isinstance(result_type_raw, str) else str(result_type_raw or "")
    )
    submitted_at_raw = payload.get("submitted_at")
    submitted_at = (
        int(submitted_at_raw) if isinstance(submitted_at_raw, (int, float)) else int(time.time())
    )
    run_id = f"{result_type_str}_{submitted_at}_{secrets.token_hex(4)}"

    title = (
        f"{result_type_str} · {ticker}".strip()
        if result_type_str
        else f"external · {ticker}".strip()
    )

    meta: dict[str, Any] = {"result_type": result_type_str, "summary": summary}

    stored_row: dict[str, Any]

    tr_raw = summary.get("total_return_pct")
    total_return_pct_f: float | None = float(tr_raw) if isinstance(tr_raw, (int, float)) else None
    sharpe_v_raw = (
        summary.get("sharpe_ratio")
        if summary.get("sharpe_ratio") is not None
        else summary.get("sharpe")
    )
    sharpe_f: float | None = float(sharpe_v_raw) if isinstance(sharpe_v_raw, (int, float)) else None
    md_raw = (
        summary.get("max_drawdown_pct")
        if summary.get("max_drawdown_pct") is not None
        else summary.get("max_drawdown")
    )
    max_dd_f: float | None = float(md_raw) if isinstance(md_raw, (int, float)) else None
    trades_v = summary.get("total_trades")
    trade_count = int(trades_v) if isinstance(trades_v, (int, float)) else None

    if _db_url():
        stored = _db_insert_result(
            provider=provider,
            run_id=run_id,
            schema_version=1,
            title=title,
            ticker=ticker,
            total_return_pct=total_return_pct_f,
            sharpe=sharpe_f,
            max_drawdown_pct=max_dd_f,
            trade_count=trade_count,
            meta=meta,
        )
        stored_row = {
            "source": "external",
            "ts": stored.ts,
            "schema_version": stored.schema_version,
            "provider": stored.provider,
            "run_id": stored.run_id,
            "title": stored.title,
            "ticker": stored.ticker,
            "total_return_pct": stored.total_return_pct,
            "sharpe": stored.sharpe,
            "max_drawdown_pct": stored.max_drawdown_pct,
            "trade_count": stored.trade_count,
            "meta": stored.meta or {},
        }
    else:
        ts = submitted_at if isinstance(submitted_at_raw, (int, float)) else int(time.time())
        stored_row = {
            "source": "external",
            "ts": ts,
            "schema_version": 1,
            "provider": provider,
            "run_id": run_id,
            "title": title,
            "ticker": ticker,
            "total_return_pct": total_return_pct_f,
            "sharpe": sharpe_f,
            "max_drawdown_pct": max_dd_f,
            "trade_count": trade_count,
            "meta": meta,
        }
        _append_jsonl(EXTERNAL_RESULTS_JSONL, stored_row)

    return {"ok": True, "run_id": run_id, "provider": provider}


@router.get("/leadpage/providers")
def list_providers() -> dict[str, Any]:
    """Discoverable providers for the UI.

    Includes:
    - providers present in env keys
    - providers present in the external JSONL ledger
    - the implicit "local" provider (your own backtest runs)
    """
    providers: set[str] = set(_provider_keys().keys())
    if _db_url():
        providers.update(_db_list_providers())
    for r in _read_jsonl(EXTERNAL_RESULTS_JSONL, limit=5000):
        p = r.get("provider")
        if isinstance(p, str) and p.strip():
            providers.add(p.strip())
    out = sorted(providers)
    return {"providers": ["local", *out]}


@router.get("/leadpage/providers/{provider}/rows")
def get_provider_rows(
    provider: str,
    limit: int = Query(500, ge=1, le=10_000),
) -> dict[str, Any]:
    """Raw row history for a provider.

    External providers: Postgres or ``external_results.jsonl``.

    ``local``: merged view of ``.runs/backtests/*/summary.json`` (canonical) plus optional
    ``LeadpageResult`` rows for provider ``local`` when a database is configured.
    """
    if provider.strip().lower() == "local":
        disk = _local_backtest_history_rows_from_disk(limit=int(limit))
        if _db_url():
            db = _db_provider_rows("local", limit=int(limit))
            merged = _merge_local_provider_history_rows(
                disk_rows=disk, db_rows=db, limit=int(limit)
            )
            return {"provider": "local", "count": len(merged), "rows": merged}
        return {"provider": "local", "count": len(disk), "rows": disk}
    if _db_url():
        rows = _db_provider_rows(provider, limit=int(limit))
        return {"provider": provider, "count": len(rows), "rows": rows}
    rows = [
        r
        for r in _read_jsonl(EXTERNAL_RESULTS_JSONL, limit=50_000)
        if r.get("provider") == provider
    ]
    rows.sort(key=lambda r: int(r.get("ts") or 0), reverse=True)
    return {"provider": provider, "count": len(rows), "rows": rows[: int(limit)]}


@router.get("/leadpage/leaderboard")
def get_leaderboard(
    limit: int = Query(50, ge=1, le=500),
    include_local: bool = Query(True),
    include_external: bool = Query(True),
    sort_by: Literal["return", "sharpe", "mdd"] = Query("return"),
    provider: str | None = Query(None, description="Optional filter for external provider id."),
) -> dict[str, Any]:
    """Aggregate and rank results for the dashboard leadpage."""
    rows: list[dict[str, Any]] = []

    def _fix_local_scan_return(row: dict[str, Any]) -> dict[str, Any]:
        """Best-effort correction for local scan rows.

        Early local scan emitters computed return from cash delta only, which looks negative when cash is
        deployed into inventory. Here we approximate equity using cost-basis (qty * avg_entry) if present.
        """

        try:
            meta = row.get("meta")
            if not isinstance(meta, dict) or meta.get("kind") != "local_scan":
                return row
            paper = meta.get("paper_account")
            if not isinstance(paper, dict):
                return row

            start_cash_raw = (os.getenv("AIMM_PAPER_START_USDT") or "10000").strip() or "10000"
            start_cash = float(start_cash_raw)
            if start_cash <= 0:
                return row

            cash = _float_or_none(paper.get("cash_usdt"))
            if cash is None:
                return row

            positions = paper.get("positions")
            if not isinstance(positions, list):
                positions = (
                    paper.get("spot_positions")
                    if isinstance(paper.get("spot_positions"), list)
                    else []
                )

            notional_cost = 0.0
            any_pos = False
            for p in positions:
                if not isinstance(p, dict):
                    continue
                qty = _float_or_none(p.get("qty"))
                avg = _float_or_none(p.get("avg_entry"))
                if qty is None or avg is None:
                    continue
                any_pos = True
                notional_cost += float(qty) * float(avg)

            if not any_pos:
                return row

            equity = float(cash) + notional_cost
            row["total_return_pct"] = ((equity - start_cash) / start_cash) * 100.0
            return row
        except Exception:
            return row

    if include_local:
        if _db_url():
            # In DB mode, local results can be synced by a platform worker (decoupled from engine/backtest code).
            rows.extend(
                _db_leaderboard_rows(limit=int(limit) * 4, provider="local", sort_by=sort_by)
            )
        if BACKTESTS_DIR.is_dir():
            # File-based fallback (also works even when DB mode is on).
            for p in sorted(BACKTESTS_DIR.iterdir(), reverse=True):
                if not p.is_dir():
                    continue
                run_id = p.name
                summary = _load_local_summary(run_id)
                if not summary:
                    continue
                rows.append(_leaderboard_row_from_summary(run_id=run_id, summary=summary))
        # Local scan loop results (paper/live runs) emitted by `src/main.py`.
        for r in _read_jsonl(LOCAL_SCAN_RESULTS_JSONL, limit=2000):
            if isinstance(r, dict):
                rows.append(_fix_local_scan_return(r))

    if include_external:
        if _db_url():
            ext = _db_leaderboard_rows(limit=int(limit) * 4, provider=provider, sort_by=sort_by)
        else:
            ext = _read_jsonl(EXTERNAL_RESULTS_JSONL)
        if provider:
            ext = [r for r in ext if r.get("provider") == provider]
        else:
            # Avoid double-counting local results if they were also inserted as "external".
            ext = [r for r in ext if r.get("provider") != "local"]
        rows.extend(ext)

    rows = [_enrich_leaderboard_row_from_meta_summary(dict(r)) for r in rows]
    rows = _dedupe_leaderboard_rows(rows)
    rows = _overlay_disk_summary_rows(rows)

    for row in rows:
        if str(row.get("provider") or "").strip():
            continue
        rid = row.get("run_id")
        if isinstance(rid, str) and rid.startswith("bt_"):
            row["provider"] = "local"
        elif row.get("source") == "local":
            row["provider"] = "local"

    def key_return(r: dict[str, Any]) -> tuple[float, float]:
        v = _float_or_none(r.get("total_return_pct"))
        ret = v if isinstance(v, float) else float("-inf")
        sh = _float_or_none(r.get("sharpe"))
        sharpe_tie = sh if isinstance(sh, float) else float("-inf")
        return (ret, sharpe_tie)

    def key_sharpe(r: dict[str, Any]) -> tuple[float, float]:
        v = _float_or_none(r.get("sharpe"))
        sh = v if isinstance(v, float) else float("-inf")
        rret = _float_or_none(r.get("total_return_pct"))
        ret_tie = rret if isinstance(rret, float) else float("-inf")
        return (sh, ret_tie)

    def key_mdd(r: dict[str, Any]) -> tuple[float, float]:
        # For drawdown, "better" is smaller. Sort ascending; missing treated as +inf.
        v = _float_or_none(r.get("max_drawdown_pct"))
        mdd = v if isinstance(v, float) else float("inf")
        rret = _float_or_none(r.get("total_return_pct"))
        ret_tie = -(rret if isinstance(rret, float) else float("-inf"))
        return (mdd, ret_tie)

    if sort_by == "sharpe":
        rows.sort(key=key_sharpe, reverse=True)
    elif sort_by == "mdd":
        rows.sort(key=key_mdd)
    else:
        rows.sort(key=key_return, reverse=True)

    return {"count": len(rows), "rows": rows[: int(limit)]}


@router.get("/leadpage/runs-surface")
def get_leadpage_runs_surface() -> dict[str, Any]:
    """Where the API looks for ``summary.json`` trees (debugging empty leaderboards)."""
    n = 0
    if BACKTESTS_DIR.is_dir():
        for p in BACKTESTS_DIR.iterdir():
            if p.is_dir() and (p / "summary.json").is_file():
                n += 1
    return {
        "runs_dir": str(RUNS_DIR.resolve()),
        "backtests_dir": str(BACKTESTS_DIR),
        "summary_json_count": n,
        "database_url_configured": bool(_db_url()),
        "hint": (
            "If summary_json_count is 0 but you have backtests on disk, set AIMM_RUNS_DIR to that "
            "repo's .runs, or ensure the API container bind-mounts host ./.runs (docker-compose.prod.yml does this by default)."
        ),
    }


@router.get("/leadpage/providers/{provider}/leaderboard")
def get_provider_leaderboard(
    provider: str,
    limit: int = Query(50, ge=1, le=500),
    sort_by: Literal["return", "sharpe", "mdd"] = Query("return"),
) -> dict[str, Any]:
    """Provider-scoped leaderboard slice.

    ``local`` includes this machine's backtest summaries (same as global leaderboard without externals).
    Other providers return externally submitted rows only.
    """
    if provider.strip().lower() == "local":
        return get_leaderboard(
            limit=limit,
            include_local=True,
            include_external=False,
            sort_by=sort_by,
            provider=None,
        )
    return get_leaderboard(
        limit=limit,
        include_local=False,
        include_external=True,
        sort_by=sort_by,
        provider=provider,
    )


@router.get("/leadpage/external_results")
def get_external_results(limit: int = Query(200, ge=1, le=2000)) -> dict[str, Any]:
    if not EXTERNAL_RESULTS_JSONL.exists():
        return {"rows": []}
    return {"rows": _read_jsonl(EXTERNAL_RESULTS_JSONL, limit=int(limit))}


@router.delete("/leadpage/external_results")
def delete_external_results(confirm: bool = Query(False)) -> dict[str, Any]:
    """Operator helper to reset external results during development."""
    if not confirm:
        raise HTTPException(status_code=400, detail="Pass confirm=1 to delete external results.")
    try:
        if EXTERNAL_RESULTS_JSONL.exists():
            EXTERNAL_RESULTS_JSONL.unlink()
    except OSError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {"ok": True}


# ── Opt-in Config Endpoint ──


@router.get("/leadpage/submit-config")
def get_leaderboard_submit_config() -> dict[str, Any]:
    """Return the current leaderboard submission configuration.

    This endpoint is informational: it reflects the local env settings so
    that the UI or operators can see the current submission state.
    """
    cfg = load_leaderboard_submit_config()
    return {
        "enabled": cfg.enabled,
        "submit_backtests": cfg.submit_backtests,
        "submit_scans": cfg.submit_scans,
        "leaderboard_url": cfg.leaderboard_url,
        "provider": cfg.provider,
        "provider_key_hint": mask_key(cfg.provider_key) if cfg.provider_key else "",
        "local_fallback": cfg.local_fallback,
    }


# ── Wallet Auth Endpoints ──


LEADPAGE_NONCE_STORE: dict[str, dict] = {}  # simple in-memory; TODO: persist


@router.get("/leadpage/auth/wallet/challenge")
def wallet_challenge(
    wallet: str = Query(..., description="Ethereum wallet address"),
) -> dict[str, Any]:
    """Generate a challenge message for wallet-based auth.

    The agent signs this message with its wallet private key and sends
    the signature back to /leadpage/auth/wallet/login.
    """
    nonce = secrets.token_hex(12)
    challenge = make_challenge(wallet, nonce=nonce)
    LEADPAGE_NONCE_STORE[nonce] = {"wallet": wallet.lower(), "created": int(time.time())}
    return {"challenge": challenge, "nonce": nonce, "wallet": wallet}


@router.post("/leadpage/auth/wallet/login")
def wallet_login(body: dict[str, str]) -> dict[str, Any]:
    """Authenticate with a wallet signature.

    Body: { wallet, challenge, signature }

    Verifies the signature, then creates or logs in the wallet user.
    Returns a session token + provider info.
    """
    from storage.leadpage_db import (
        create_provider,
        create_provider_secret,
        create_user,
        get_session,
    )

    wallet = body.get("wallet", "").strip()
    challenge = body.get("challenge", "").strip()
    signature = body.get("signature", "").strip()

    if not wallet or not challenge or not signature:
        return {"ok": False, "error": "Missing wallet, challenge, or signature"}

    # Verify
    if not verify_wallet_signature(wallet=wallet, challenge=challenge, signature=signature):
        return {"ok": False, "error": "Signature verification failed"}

    email = wallet_to_email(wallet)

    with get_session() as session:
        user = session.execute(
            select(LeadpageUser).where(LeadpageUser.email == email)
        ).scalar_one_or_none()

        if user is None:
            # Create new user + default provider
            pwh = hashlib.sha256(wallet.encode()).hexdigest()  # wallet never reveals password
            user = create_user(email=email, password_hash=pwh)
            provider_slug = f"wallet-{wallet[-6:].lower()}"
            create_provider(provider=provider_slug, owner_user_id=user.id)
            key = generate_provider_key()
            create_provider_secret(provider=provider_slug, secret=key)
            provider_key = key
            is_new = True
        else:
            # Existing user — look up their providers
            providers = (
                session.execute(
                    select(LeadpageProvider).where(LeadpageProvider.owner_user_id == user.id)
                )
                .scalars()
                .all()
            )
            provider_key = None
            provider_slug = providers[0].provider if providers else None
            is_new = False

    session_token = secrets.token_hex(24)
    return {
        "ok": True,
        "token": session_token,
        "user": {"id": user.id, "wallet": wallet, "email": email, "is_new": is_new},
        "provider": provider_slug,
        "provider_key_hint": (provider_key[:8] + "...") if provider_key else None,
    }


@router.get("/leadpage/validate")
def validate_submission(
    ticker: str = Query(...),
    total_return_pct: float = Query(0),
    sharpe_ratio: float = Query(0, alias="sharpe_ratio"),
    submit_start_time: str | None = Query(None, alias="start_time"),
) -> dict[str, Any]:
    """Client-side validation endpoint. Returns expected issues before submitting.

    Useful for the submitter to check if its data will be accepted.
    """
    payload = {
        "ticker": ticker,
        "result_type": "backtest",
        "summary": {
            "total_return_pct": total_return_pct,
            "sharpe_ratio": sharpe_ratio,
            "start_time": submit_start_time,
        },
    }
    errors = validate_result(payload)
    return {"valid": len(errors) == 0, "errors": errors}
