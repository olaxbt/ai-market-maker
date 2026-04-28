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
import os
import time
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

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

RUNS_DIR = Path(".runs")
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
        if not digest:
            raise HTTPException(status_code=401, detail=f"unknown provider: {provider}")
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
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v))
    except Exception:
        return None


def _leaderboard_row_from_summary(*, run_id: str, summary: dict[str, Any]) -> dict[str, Any]:
    evaluation = summary.get("evaluation") if isinstance(summary.get("evaluation"), dict) else {}
    metrics = summary.get("metrics") if isinstance(summary.get("metrics"), dict) else {}
    bench = summary.get("benchmark") if isinstance(summary.get("benchmark"), dict) else {}

    total_return_pct = (
        _float_or_none(evaluation.get("total_return_pct"))
        if evaluation.get("total_return_pct") is not None
        else _float_or_none(bench.get("strategy_total_return_pct"))
    )
    sharpe = _float_or_none(metrics.get("sharpe"))
    mdd_frac = _float_or_none(metrics.get("max_drawdown"))
    mdd_pct = (mdd_frac * 100.0) if isinstance(mdd_frac, float) else None

    return {
        "source": "local",
        "ts": summary.get("ts") if summary.get("ts") is not None else None,
        "run_id": run_id,
        "title": summary.get("strategy", {}).get("title")
        if isinstance(summary.get("strategy"), dict)
        else None,
        "ticker": summary.get("ticker"),
        "steps": summary.get("steps"),
        "trade_count": summary.get("trade_count"),
        "total_return_pct": total_return_pct,
        "sharpe": sharpe,
        "max_drawdown_pct": mdd_pct,
        "win_rate": _float_or_none(metrics.get("win_rate")),
        "profit_factor": _float_or_none(metrics.get("profit_factor")),
    }


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
    """Raw row history for a provider (external only)."""
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

    def key_return(r: dict[str, Any]) -> float:
        v = _float_or_none(r.get("total_return_pct"))
        return v if isinstance(v, float) else float("-inf")

    def key_sharpe(r: dict[str, Any]) -> float:
        v = _float_or_none(r.get("sharpe"))
        return v if isinstance(v, float) else float("-inf")

    def key_mdd(r: dict[str, Any]) -> float:
        # For drawdown, "better" is smaller. Sort ascending; missing treated as +inf.
        v = _float_or_none(r.get("max_drawdown_pct"))
        return v if isinstance(v, float) else float("inf")

    if sort_by == "sharpe":
        rows.sort(key=key_sharpe, reverse=True)
    elif sort_by == "mdd":
        rows.sort(key=key_mdd)
    else:
        rows.sort(key=key_return, reverse=True)

    return {"count": len(rows), "rows": rows[: int(limit)]}


@router.get("/leadpage/providers/{provider}/leaderboard")
def get_provider_leaderboard(
    provider: str,
    limit: int = Query(50, ge=1, le=500),
    sort_by: Literal["return", "sharpe", "mdd"] = Query("return"),
) -> dict[str, Any]:
    """Convenience wrapper for provider pages (external rows only)."""
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
