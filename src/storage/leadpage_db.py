from __future__ import annotations

import hashlib
import os
import secrets
import time
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import JSON, Float, Integer, String, UniqueConstraint, create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


def database_url() -> str | None:
    url = (os.getenv("DATABASE_URL") or "").strip()
    return url or None


class Base(DeclarativeBase):
    pass


class LeadpageProvider(Base):
    __tablename__ = "leadpage_providers"

    provider: Mapped[str] = mapped_column(String(80), primary_key=True)
    owner_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_ts: Mapped[int] = mapped_column(Integer, nullable=False)


class LeadpageUser(Base):
    __tablename__ = "leadpage_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_ts: Mapped[int] = mapped_column(Integer, nullable=False)


class LeadpageProviderSecret(Base):
    __tablename__ = "leadpage_provider_secrets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    secret_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_ts: Mapped[int] = mapped_column(Integer, nullable=False)
    disabled_ts: Mapped[int | None] = mapped_column(Integer, nullable=True)


class LeadpageSignal(Base):
    __tablename__ = "leadpage_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(80), nullable=False, index=True)

    # "strategy" | "ops" | "discussion"
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(String(8000), nullable=False)
    ticker: Mapped[str | None] = mapped_column(String(80), nullable=True)

    # Optional link to a published result (provider-run or local id)
    result_provider: Mapped[str | None] = mapped_column(String(80), nullable=True)
    result_run_id: Mapped[str | None] = mapped_column(String(160), nullable=True)

    meta: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class LeadpageResult(Base):
    __tablename__ = "leadpage_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    provider: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(160), nullable=False)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ticker: Mapped[str | None] = mapped_column(String(80), nullable=True)

    total_return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    sharpe: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_drawdown_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    trade_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    meta: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class LeadpageNonce(Base):
    __tablename__ = "leadpage_nonces"
    __table_args__ = (UniqueConstraint("provider", "nonce", name="uq_provider_nonce"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    nonce: Mapped[str] = mapped_column(String(120), nullable=False)


class LeadpageFollow(Base):
    __tablename__ = "leadpage_follows"
    __table_args__ = (UniqueConstraint("user_id", "provider", name="uq_follow_user_provider"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(80), nullable=False, index=True)


class LeadpageInboxItem(Base):
    __tablename__ = "leadpage_inbox"
    __table_args__ = (UniqueConstraint("user_id", "signal_id", name="uq_inbox_user_signal"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    signal_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(String(8000), nullable=False)
    ticker: Mapped[str | None] = mapped_column(String(80), nullable=True)
    read_ts: Mapped[int | None] = mapped_column(Integer, nullable=True)


class LeadpageFanoutCursor(Base):
    __tablename__ = "leadpage_fanout_cursor"

    name: Mapped[str] = mapped_column(String(80), primary_key=True)
    last_signal_id: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_ts: Mapped[int] = mapped_column(Integer, nullable=False)


class LeadpageCopySetting(Base):
    __tablename__ = "leadpage_copy_settings"
    __table_args__ = (UniqueConstraint("user_id", "provider", name="uq_copy_user_provider"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 0/1
    auto_execute: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 0/1
    instrument: Mapped[str] = mapped_column(String(16), nullable=False, default="spot")
    max_notional_usdt: Mapped[float | None] = mapped_column(Float, nullable=True)


class LeadpageExecution(Base):
    __tablename__ = "leadpage_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    signal_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    inbox_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[str] = mapped_column(String(24), nullable=False)
    detail: Mapped[str] = mapped_column(String(2000), nullable=False)
    trade: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class LeadpagePaperAccount(Base):
    __tablename__ = "leadpage_paper_accounts"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cash_usdt: Mapped[float] = mapped_column(Float, nullable=False)
    realized_pnl_usdt: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # Store positions as JSON blobs for simplicity (spot_positions + perp_positions).
    state: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    updated_ts: Mapped[int] = mapped_column(Integer, nullable=False)


class LeadpagePaperTrade(Base):
    __tablename__ = "leadpage_paper_trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    trade: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


_ENGINE: Engine | None = None


def engine() -> Engine | None:
    global _ENGINE
    url = database_url()
    if not url:
        return None
    if _ENGINE is None:
        _ENGINE = create_engine(url, pool_pre_ping=True)
        # In production, prefer Alembic migrations. For local dev, autocreate can be enabled.
        auto = (os.getenv("AIMM_DB_AUTOCREATE") or "").strip()
        if auto in {"1", "true", "TRUE", "yes", "YES"}:
            Base.metadata.create_all(_ENGINE)
    return _ENGINE


def _now() -> int:
    return int(time.time())


def ensure_provider(session: Session, provider: str) -> None:
    if session.get(LeadpageProvider, provider) is not None:
        return
    session.add(LeadpageProvider(provider=provider, created_ts=_now()))


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def create_user(*, email: str, password_hash: str) -> int:
    eng = engine()
    if eng is None:
        raise RuntimeError("DATABASE_URL is not set")
    with Session(eng) as s:
        u = LeadpageUser(
            email=email.strip().lower(), password_hash=password_hash, created_ts=_now()
        )
        s.add(u)
        s.commit()
        return int(u.id)


def get_user_by_email(email: str) -> LeadpageUser | None:
    eng = engine()
    if eng is None:
        return None
    with Session(eng) as s:
        q = select(LeadpageUser).where(LeadpageUser.email == email.strip().lower())
        return s.scalars(q).first()


def get_user_by_id(user_id: int) -> LeadpageUser | None:
    eng = engine()
    if eng is None:
        return None
    with Session(eng) as s:
        return s.get(LeadpageUser, int(user_id))


def create_provider_for_user(*, provider: str, user_id: int) -> str:
    eng = engine()
    if eng is None:
        raise RuntimeError("DATABASE_URL is not set")
    with Session(eng) as s:
        existing = s.get(LeadpageProvider, provider)
        if existing is not None:
            raise ValueError("provider already exists")
        s.add(LeadpageProvider(provider=provider, owner_user_id=int(user_id), created_ts=_now()))
        s.commit()
        return provider


def list_providers_for_user(user_id: int) -> list[str]:
    eng = engine()
    if eng is None:
        return []
    with Session(eng) as s:
        q = (
            select(LeadpageProvider.provider)
            .where(LeadpageProvider.owner_user_id == int(user_id))
            .order_by(LeadpageProvider.provider.asc())
        )
        rows = s.scalars(q).all()
        return [str(x) for x in rows if x]


def rotate_provider_secret(*, provider: str, user_id: int) -> str:
    """Generate and persist a new provider secret (returns the plaintext once)."""
    eng = engine()
    if eng is None:
        raise RuntimeError("DATABASE_URL is not set")
    new_secret = secrets.token_urlsafe(32)
    digest = _sha256_hex(new_secret)
    with Session(eng) as s:
        p = s.get(LeadpageProvider, provider)
        if p is None:
            raise ValueError("provider not found")
        if p.owner_user_id != int(user_id):
            raise PermissionError("forbidden")
        # Disable old secrets
        olds = s.scalars(
            select(LeadpageProviderSecret).where(
                LeadpageProviderSecret.provider == provider,
                LeadpageProviderSecret.disabled_ts.is_(None),
            )
        ).all()
        now = _now()
        for o in olds:
            o.disabled_ts = now
        s.add(
            LeadpageProviderSecret(
                provider=provider, secret_sha256=digest, created_ts=now, disabled_ts=None
            )
        )
        s.commit()
    return new_secret


def active_provider_secret_digest(provider: str) -> str | None:
    eng = engine()
    if eng is None:
        return None
    with Session(eng) as s:
        q = (
            select(LeadpageProviderSecret.secret_sha256)
            .where(
                LeadpageProviderSecret.provider == provider,
                LeadpageProviderSecret.disabled_ts.is_(None),
            )
            .order_by(LeadpageProviderSecret.created_ts.desc(), LeadpageProviderSecret.id.desc())
            .limit(1)
        )
        return s.scalars(q).first()


@dataclass(frozen=True)
class DbRow:
    provider: str
    run_id: str
    ts: int
    schema_version: int
    title: str | None
    ticker: str | None
    total_return_pct: float | None
    sharpe: float | None
    max_drawdown_pct: float | None
    trade_count: int | None
    meta: dict[str, Any] | None


def insert_result(
    *,
    provider: str,
    run_id: str,
    schema_version: int,
    title: str | None,
    ticker: str | None,
    total_return_pct: float | None,
    sharpe: float | None,
    max_drawdown_pct: float | None,
    trade_count: int | None,
    meta: dict[str, Any] | None,
) -> DbRow:
    eng = engine()
    if eng is None:
        raise RuntimeError("DATABASE_URL is not set")
    with Session(eng) as s:
        ensure_provider(s, provider)
        row = LeadpageResult(
            ts=_now(),
            schema_version=int(schema_version),
            provider=provider,
            run_id=run_id,
            title=title,
            ticker=ticker,
            total_return_pct=total_return_pct,
            sharpe=sharpe,
            max_drawdown_pct=max_drawdown_pct,
            trade_count=trade_count,
            meta=meta,
        )
        s.add(row)
        s.commit()
        return DbRow(
            provider=row.provider,
            run_id=row.run_id,
            ts=row.ts,
            schema_version=row.schema_version,
            title=row.title,
            ticker=row.ticker,
            total_return_pct=row.total_return_pct,
            sharpe=row.sharpe,
            max_drawdown_pct=row.max_drawdown_pct,
            trade_count=row.trade_count,
            meta=row.meta,
        )


def list_providers() -> list[str]:
    eng = engine()
    if eng is None:
        return []
    with Session(eng) as s:
        rows = s.scalars(
            select(LeadpageProvider.provider).order_by(LeadpageProvider.provider.asc())
        ).all()
        return [str(x) for x in rows if x]


def provider_rows(provider: str, *, limit: int) -> list[dict[str, Any]]:
    eng = engine()
    if eng is None:
        return []
    with Session(eng) as s:
        q = (
            select(LeadpageResult)
            .where(LeadpageResult.provider == provider)
            .order_by(LeadpageResult.ts.desc(), LeadpageResult.id.desc())
            .limit(int(limit))
        )
        out: list[dict[str, Any]] = []
        for r in s.scalars(q).all():
            out.append(
                {
                    "source": "external",
                    "ts": r.ts,
                    "schema_version": r.schema_version,
                    "provider": r.provider,
                    "run_id": r.run_id,
                    "title": r.title,
                    "ticker": r.ticker,
                    "total_return_pct": r.total_return_pct,
                    "sharpe": r.sharpe,
                    "max_drawdown_pct": r.max_drawdown_pct,
                    "trade_count": r.trade_count,
                    "meta": r.meta or {},
                }
            )
        return out


def leaderboard_rows(
    *,
    limit: int,
    provider: str | None,
    sort_by: Literal["return", "sharpe", "mdd"],
) -> list[dict[str, Any]]:
    eng = engine()
    if eng is None:
        return []
    with Session(eng) as s:
        q = select(LeadpageResult)
        if provider:
            q = q.where(LeadpageResult.provider == provider)

        # Sorting in SQL is tricky with NULLS; do a two-step approach:
        # - fetch a bounded pool (latest N) then rank in Python
        pool = max(int(limit) * 20, 500)
        q = q.order_by(LeadpageResult.ts.desc(), LeadpageResult.id.desc()).limit(pool)
        rows = list(s.scalars(q).all())

    def f(x: float | None, *, default: float) -> float:
        return float(x) if isinstance(x, (int, float)) else default

    if sort_by == "sharpe":
        rows.sort(key=lambda r: f(r.sharpe, default=float("-inf")), reverse=True)
    elif sort_by == "mdd":
        rows.sort(key=lambda r: f(r.max_drawdown_pct, default=float("inf")))
    else:
        rows.sort(key=lambda r: f(r.total_return_pct, default=float("-inf")), reverse=True)

    out: list[dict[str, Any]] = []
    for r in rows[: int(limit)]:
        out.append(
            {
                "source": "external",
                "ts": r.ts,
                "schema_version": r.schema_version,
                "provider": r.provider,
                "run_id": r.run_id,
                "title": r.title,
                "ticker": r.ticker,
                "total_return_pct": r.total_return_pct,
                "sharpe": r.sharpe,
                "max_drawdown_pct": r.max_drawdown_pct,
                "trade_count": r.trade_count,
                "meta": r.meta or {},
            }
        )
    return out


def result_exists(*, provider: str, run_id: str) -> bool:
    eng = engine()
    if eng is None:
        return False
    with Session(eng) as s:
        q = (
            select(LeadpageResult.id)
            .where(
                LeadpageResult.provider == provider,
                LeadpageResult.run_id == run_id,
            )
            .limit(1)
        )
        return s.execute(q).first() is not None


def insert_local_backtest_result_if_missing(*, summary: dict[str, Any]) -> bool:
    """Idempotent insert for `.runs/backtests/<run_id>/summary.json` style payloads."""
    run_id = str(summary.get("run_id") or "").strip()
    if not run_id:
        return False
    if result_exists(provider="local", run_id=run_id):
        return False
    evaluation = summary.get("evaluation") if isinstance(summary.get("evaluation"), dict) else {}
    metrics = summary.get("metrics") if isinstance(summary.get("metrics"), dict) else {}
    bench = summary.get("benchmark") if isinstance(summary.get("benchmark"), dict) else {}
    total_return_pct = (
        float(evaluation.get("total_return_pct"))
        if isinstance(evaluation.get("total_return_pct"), (int, float))
        else (
            float(bench.get("strategy_total_return_pct"))
            if isinstance(bench.get("strategy_total_return_pct"), (int, float))
            else None
        )
    )
    sharpe = (
        float(metrics.get("sharpe")) if isinstance(metrics.get("sharpe"), (int, float)) else None
    )
    mdd_pct = (
        float(metrics.get("max_drawdown")) * 100.0
        if isinstance(metrics.get("max_drawdown"), (int, float))
        else None
    )
    trade_count = summary.get("trade_count")
    trade_count_i = int(trade_count) if isinstance(trade_count, (int, float)) else None
    insert_result(
        provider="local",
        run_id=run_id,
        schema_version=1,
        title=(summary.get("strategy") or {}).get("title")
        if isinstance(summary.get("strategy"), dict)
        else None,
        ticker=str(summary.get("ticker") or "") or None,
        total_return_pct=total_return_pct,
        sharpe=sharpe,
        max_drawdown_pct=mdd_pct,
        trade_count=trade_count_i,
        meta={"source": "local_backtest_summary", "summary": summary},
    )
    return True


def nonce_seen(provider: str, nonce: str, *, min_ts: int) -> bool:
    eng = engine()
    if eng is None:
        return False
    with Session(eng) as s:
        q = select(LeadpageNonce).where(
            LeadpageNonce.provider == provider,
            LeadpageNonce.nonce == nonce,
            LeadpageNonce.ts >= int(min_ts),
        )
        return s.execute(q).first() is not None


def record_nonce(provider: str, nonce: str) -> None:
    eng = engine()
    if eng is None:
        return
    with Session(eng) as s:
        ensure_provider(s, provider)
        s.add(LeadpageNonce(ts=_now(), provider=provider, nonce=nonce))
        try:
            s.commit()
        except Exception:
            s.rollback()


def insert_signal(
    *,
    provider: str,
    kind: str,
    title: str,
    body: str,
    ticker: str | None,
    result_provider: str | None,
    result_run_id: str | None,
    meta: dict[str, Any] | None,
) -> dict[str, Any]:
    eng = engine()
    if eng is None:
        raise RuntimeError("DATABASE_URL is not set")
    with Session(eng) as s:
        ensure_provider(s, provider)
        row = LeadpageSignal(
            ts=_now(),
            provider=provider,
            kind=kind,
            title=title,
            body=body,
            ticker=ticker,
            result_provider=result_provider,
            result_run_id=result_run_id,
            meta=meta,
        )
        s.add(row)
        s.commit()
        return {
            "id": int(row.id),
            "ts": int(row.ts),
            "provider": row.provider,
            "kind": row.kind,
            "title": row.title,
            "body": row.body,
            "ticker": row.ticker,
            "result_provider": row.result_provider,
            "result_run_id": row.result_run_id,
            "meta": row.meta or {},
        }


def feed_signals(*, limit: int, provider: str | None = None) -> list[dict[str, Any]]:
    eng = engine()
    if eng is None:
        return []
    with Session(eng) as s:
        q = select(LeadpageSignal)
        if provider:
            q = q.where(LeadpageSignal.provider == provider)
        q = q.order_by(LeadpageSignal.ts.desc(), LeadpageSignal.id.desc()).limit(int(limit))
        rows = s.scalars(q).all()
        return [
            {
                "id": int(r.id),
                "ts": int(r.ts),
                "provider": r.provider,
                "kind": r.kind,
                "title": r.title,
                "body": r.body,
                "ticker": r.ticker,
                "result_provider": r.result_provider,
                "result_run_id": r.result_run_id,
                "meta": r.meta or {},
            }
            for r in rows
        ]


def get_signal(signal_id: int) -> dict[str, Any] | None:
    eng = engine()
    if eng is None:
        return None
    with Session(eng) as s:
        r = s.get(LeadpageSignal, int(signal_id))
        if r is None:
            return None
        return {
            "id": int(r.id),
            "ts": int(r.ts),
            "provider": r.provider,
            "kind": r.kind,
            "title": r.title,
            "body": r.body,
            "ticker": r.ticker,
            "result_provider": r.result_provider,
            "result_run_id": r.result_run_id,
            "meta": r.meta or {},
        }


def upsert_copy_setting(
    *,
    user_id: int,
    provider: str,
    enabled: bool,
    auto_execute: bool = False,
    instrument: str,
    max_notional_usdt: float | None,
) -> dict[str, Any]:
    eng = engine()
    if eng is None:
        raise RuntimeError("DATABASE_URL is not set")
    inst = (instrument or "spot").strip().lower()
    if inst not in {"spot", "perp"}:
        inst = "spot"
    with Session(eng) as s:
        ensure_provider(s, provider)
        existing = s.scalars(
            select(LeadpageCopySetting).where(
                LeadpageCopySetting.user_id == int(user_id),
                LeadpageCopySetting.provider == provider,
            )
        ).first()
        now = _now()
        if existing is None:
            existing = LeadpageCopySetting(
                ts=now,
                user_id=int(user_id),
                provider=provider,
                enabled=1 if enabled else 0,
                auto_execute=1 if auto_execute else 0,
                instrument=inst,
                max_notional_usdt=max_notional_usdt,
            )
            s.add(existing)
        else:
            existing.ts = now
            existing.enabled = 1 if enabled else 0
            existing.auto_execute = 1 if auto_execute else 0
            existing.instrument = inst
            existing.max_notional_usdt = max_notional_usdt
        s.commit()
        return {
            "provider": provider,
            "enabled": bool(existing.enabled),
            "auto_execute": bool(existing.auto_execute),
            "instrument": existing.instrument,
            "max_notional_usdt": existing.max_notional_usdt,
            "ts": int(existing.ts),
        }


def get_copy_setting(user_id: int, provider: str) -> dict[str, Any] | None:
    eng = engine()
    if eng is None:
        return None
    with Session(eng) as s:
        r = s.scalars(
            select(LeadpageCopySetting).where(
                LeadpageCopySetting.user_id == int(user_id),
                LeadpageCopySetting.provider == provider,
            )
        ).first()
        if r is None:
            return None
        return {
            "provider": provider,
            "enabled": bool(r.enabled),
            "auto_execute": bool(r.auto_execute),
            "instrument": r.instrument,
            "max_notional_usdt": r.max_notional_usdt,
            "ts": int(r.ts),
        }


def record_execution(
    *,
    user_id: int,
    provider: str,
    signal_id: int,
    inbox_id: int | None,
    status: str,
    detail: str,
    trade: dict[str, Any] | None,
) -> dict[str, Any]:
    eng = engine()
    if eng is None:
        raise RuntimeError("DATABASE_URL is not set")
    with Session(eng) as s:
        row = LeadpageExecution(
            ts=_now(),
            user_id=int(user_id),
            provider=provider,
            signal_id=int(signal_id),
            inbox_id=int(inbox_id) if inbox_id is not None else None,
            status=str(status),
            detail=str(detail)[:2000],
            trade=trade,
        )
        s.add(row)
        s.commit()
        return {
            "id": int(row.id),
            "ts": int(row.ts),
            "user_id": int(row.user_id),
            "provider": row.provider,
            "signal_id": int(row.signal_id),
            "inbox_id": row.inbox_id,
            "status": row.status,
            "detail": row.detail,
            "trade": row.trade,
        }


def list_executions(user_id: int, *, limit: int = 200) -> list[dict[str, Any]]:
    eng = engine()
    if eng is None:
        return []
    with Session(eng) as s:
        q = (
            select(LeadpageExecution)
            .where(LeadpageExecution.user_id == int(user_id))
            .order_by(LeadpageExecution.ts.desc(), LeadpageExecution.id.desc())
            .limit(int(limit))
        )
        rows = s.scalars(q).all()
        return [
            {
                "id": int(r.id),
                "ts": int(r.ts),
                "provider": r.provider,
                "signal_id": int(r.signal_id),
                "inbox_id": r.inbox_id,
                "status": r.status,
                "detail": r.detail,
                "trade": r.trade,
            }
            for r in rows
        ]


def get_or_init_paper_account(user_id: int, *, start_usdt: float) -> dict[str, Any]:
    eng = engine()
    if eng is None:
        raise RuntimeError("DATABASE_URL is not set")
    uid = int(user_id)
    with Session(eng) as s:
        row = s.get(LeadpagePaperAccount, uid)
        if row is None:
            now = _now()
            state = {
                "account_id": f"user-{uid}",
                "cash_usdt": float(start_usdt),
                "realized_pnl_usdt": 0.0,
                "spot_positions": [],
                "perp_positions": [],
                "updated_ts": now,
            }
            row = LeadpagePaperAccount(
                user_id=uid,
                cash_usdt=float(start_usdt),
                realized_pnl_usdt=0.0,
                state=state,
                updated_ts=now,
            )
            s.add(row)
            s.commit()
        return dict(row.state or {})


def save_paper_account(user_id: int, snapshot: dict[str, Any]) -> None:
    eng = engine()
    if eng is None:
        raise RuntimeError("DATABASE_URL is not set")
    uid = int(user_id)
    with Session(eng) as s:
        row = s.get(LeadpagePaperAccount, uid)
        if row is None:
            row = LeadpagePaperAccount(
                user_id=uid,
                cash_usdt=float(snapshot.get("cash_usdt") or 0.0),
                realized_pnl_usdt=float(snapshot.get("realized_pnl_usdt") or 0.0),
                state=snapshot,
                updated_ts=int(snapshot.get("updated_ts") or _now()),
            )
            s.add(row)
        else:
            row.cash_usdt = float(snapshot.get("cash_usdt") or 0.0)
            row.realized_pnl_usdt = float(snapshot.get("realized_pnl_usdt") or 0.0)
            row.state = snapshot
            row.updated_ts = int(snapshot.get("updated_ts") or _now())
        s.commit()


def append_paper_trade(user_id: int, trade: dict[str, Any]) -> None:
    eng = engine()
    if eng is None:
        raise RuntimeError("DATABASE_URL is not set")
    uid = int(user_id)
    with Session(eng) as s:
        ts = int(trade.get("ts") or _now())
        s.add(LeadpagePaperTrade(ts=ts, user_id=uid, trade=trade))
        s.commit()


def list_paper_trades(user_id: int, *, limit: int = 200) -> list[dict[str, Any]]:
    eng = engine()
    if eng is None:
        return []
    uid = int(user_id)
    with Session(eng) as s:
        q = (
            select(LeadpagePaperTrade)
            .where(LeadpagePaperTrade.user_id == uid)
            .order_by(LeadpagePaperTrade.ts.desc(), LeadpagePaperTrade.id.desc())
            .limit(int(limit))
        )
        rows = s.scalars(q).all()
        return [dict(r.trade or {}) for r in rows]


def follow_provider(*, user_id: int, provider: str) -> None:
    eng = engine()
    if eng is None:
        raise RuntimeError("DATABASE_URL is not set")
    with Session(eng) as s:
        ensure_provider(s, provider)
        s.add(LeadpageFollow(ts=_now(), user_id=int(user_id), provider=provider))
        try:
            s.commit()
        except Exception:
            s.rollback()


def unfollow_provider(*, user_id: int, provider: str) -> None:
    eng = engine()
    if eng is None:
        raise RuntimeError("DATABASE_URL is not set")
    with Session(eng) as s:
        rows = s.scalars(
            select(LeadpageFollow).where(
                LeadpageFollow.user_id == int(user_id), LeadpageFollow.provider == provider
            )
        ).all()
        for r in rows:
            s.delete(r)
        s.commit()


def list_following(user_id: int) -> list[str]:
    eng = engine()
    if eng is None:
        return []
    with Session(eng) as s:
        q = (
            select(LeadpageFollow.provider)
            .where(LeadpageFollow.user_id == int(user_id))
            .order_by(LeadpageFollow.provider.asc())
        )
        rows = s.scalars(q).all()
        return [str(x) for x in rows if x]


def inbox_items(user_id: int, *, limit: int) -> list[dict[str, Any]]:
    eng = engine()
    if eng is None:
        return []
    with Session(eng) as s:
        q = (
            select(LeadpageInboxItem)
            .where(LeadpageInboxItem.user_id == int(user_id))
            .order_by(LeadpageInboxItem.ts.desc(), LeadpageInboxItem.id.desc())
            .limit(int(limit))
        )
        rows = s.scalars(q).all()
        return [
            {
                "id": int(r.id),
                "ts": int(r.ts),
                "user_id": int(r.user_id),
                "signal_id": int(r.signal_id),
                "provider": r.provider,
                "kind": r.kind,
                "title": r.title,
                "body": r.body,
                "ticker": r.ticker,
                "read_ts": r.read_ts,
            }
            for r in rows
        ]


def unread_ops_inbox(user_id: int, provider: str, *, limit: int = 25) -> list[dict[str, Any]]:
    """Unread ops inbox items for auto-execute."""
    eng = engine()
    if eng is None:
        return []
    with Session(eng) as s:
        q = (
            select(LeadpageInboxItem)
            .where(
                LeadpageInboxItem.user_id == int(user_id),
                LeadpageInboxItem.provider == provider,
                LeadpageInboxItem.kind == "ops",
                LeadpageInboxItem.read_ts.is_(None),
            )
            .order_by(LeadpageInboxItem.ts.asc(), LeadpageInboxItem.id.asc())
            .limit(int(limit))
        )
        rows = s.scalars(q).all()
        return [
            {
                "id": int(r.id),
                "ts": int(r.ts),
                "user_id": int(r.user_id),
                "signal_id": int(r.signal_id),
                "provider": r.provider,
                "kind": r.kind,
                "title": r.title,
                "body": r.body,
                "ticker": r.ticker,
                "read_ts": r.read_ts,
            }
            for r in rows
        ]


def auto_execute_targets(*, limit: int = 500) -> list[tuple[int, str]]:
    """Return (user_id, provider) pairs with enabled+auto_execute."""
    eng = engine()
    if eng is None:
        return []
    with Session(eng) as s:
        q = (
            select(LeadpageCopySetting.user_id, LeadpageCopySetting.provider)
            .where(LeadpageCopySetting.enabled == 1, LeadpageCopySetting.auto_execute == 1)
            .order_by(LeadpageCopySetting.user_id.asc())
            .limit(int(limit))
        )
        return [(int(a), str(b)) for a, b in s.execute(q).all()]


def mark_inbox_read(user_id: int, inbox_id: int) -> None:
    eng = engine()
    if eng is None:
        return
    with Session(eng) as s:
        it = s.get(LeadpageInboxItem, int(inbox_id))
        if it is None or int(it.user_id) != int(user_id):
            return
        it.read_ts = _now()
        s.commit()


def _get_cursor(session: Session, name: str) -> LeadpageFanoutCursor:
    c = session.get(LeadpageFanoutCursor, name)
    if c is None:
        c = LeadpageFanoutCursor(name=name, last_signal_id=0, updated_ts=_now())
        session.add(c)
        session.flush()
    return c


def fanout_new_signals(*, cursor_name: str = "default", limit: int = 200) -> dict[str, Any]:
    """Fan out newly published signals into follower inboxes (idempotent via unique constraint)."""
    eng = engine()
    if eng is None:
        raise RuntimeError("DATABASE_URL is not set")
    processed = 0
    inserted = 0
    with Session(eng) as s:
        cur = _get_cursor(s, cursor_name)
        last_id = int(cur.last_signal_id)
        # Pull new signals in id order for stable cursoring.
        sigs = s.scalars(
            select(LeadpageSignal)
            .where(LeadpageSignal.id > last_id)
            .order_by(LeadpageSignal.id.asc())
            .limit(int(limit))
        ).all()
        if not sigs:
            return {"processed": 0, "inserted": 0, "last_signal_id": last_id}

        for sig in sigs:
            processed += 1
            followers = s.scalars(
                select(LeadpageFollow.user_id).where(LeadpageFollow.provider == sig.provider)
            ).all()
            for uid in followers:
                item = LeadpageInboxItem(
                    ts=int(sig.ts),
                    user_id=int(uid),
                    signal_id=int(sig.id),
                    provider=str(sig.provider),
                    kind=str(sig.kind),
                    title=str(sig.title),
                    body=str(sig.body),
                    ticker=sig.ticker,
                    read_ts=None,
                )
                s.add(item)
                try:
                    s.flush()
                    inserted += 1
                except Exception:
                    s.rollback()
                    # Re-open session transaction after rollback by starting a new one is heavy;
                    # instead, use a nested approach: just continue in a fresh transaction.
                    # Simplest: re-add cursor row after rollback.
                    s.begin()
                    cur = _get_cursor(s, cursor_name)
                    continue

            cur.last_signal_id = int(sig.id)
            cur.updated_ts = _now()

        s.commit()
        return {
            "processed": processed,
            "inserted": inserted,
            "last_signal_id": int(cur.last_signal_id),
        }
