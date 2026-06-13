"""File-backed decision cache for reproducible backtests and agent_llm replay."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CACHE_ENV = "AIMM_DECISION_CACHE_DIR"
_DEFAULT_CACHE_DIR = ".cache/decisions"


def _cache_dir() -> Path:
    override = (os.getenv(_CACHE_ENV) or "").strip()
    return Path(override) if override else Path(_DEFAULT_CACHE_DIR)


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _cache_key(
    agent_id: str,
    ticker: str,
    date_tag: str,
    prompt_hash: str,
) -> str:
    raw = f"{agent_id}|{ticker}|{date_tag}|{prompt_hash}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _cache_path(key: str) -> Path:
    d = _cache_dir() / key[:2] / key[2:4]
    return d / f"{key}.json"


def decision_cache_enabled() -> bool:
    """Check whether the decision cache is enabled.

    Enabled by default when AIMM_DECISION_CACHE_DIR is set.
    Also enabled automatically in backtest mode.
    """
    env = os.getenv("AIMM_DECISION_CACHE_DIR", "")
    if env.strip():
        return True
    mode = os.getenv("MODE", os.getenv("AIMM_RUN_MODE", "")).strip().lower()
    return mode in ("backtest",)


def read_cached_decision(
    agent_id: str,
    ticker: str,
    date_tag: str,
    prompt_hash: str,
) -> dict[str, Any] | None:
    """Read a cached decision for the given agent + context.

    Returns None if cache miss or disabled.
    """
    if not decision_cache_enabled():
        return None
    key = _cache_key(agent_id, ticker, date_tag, prompt_hash)
    path = _cache_path(key)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text())
        return data.get("decision")
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Decision cache read error for %s: %s", key, e)
        return None


def write_cached_decision(
    agent_id: str,
    ticker: str,
    date_tag: str,
    prompt_hash: str,
    decision: dict[str, Any],
    *,
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Write a decision to the cache.

    Returns True on success.
    """
    if not decision_cache_enabled():
        return False
    key = _cache_key(agent_id, ticker, date_tag, prompt_hash)
    path = _cache_path(key)
    _ensure_dir(path.parent)
    payload = {
        "key": key,
        "agent_id": agent_id,
        "ticker": ticker,
        "date_tag": date_tag,
        "prompt_hash": prompt_hash,
        "decision": decision,
        "metadata": metadata or {},
        "cached_at": time.time(),
    }
    try:
        path.write_text(json.dumps(payload, indent=2, default=str))
        return True
    except OSError as e:
        logger.warning("Decision cache write error for %s: %s", key, e)
        return False


def invalidate_cache(agent_id: str | None = None, ticker: str | None = None) -> int:
    """Invalidate cache entries, optionally filtered by agent_id or ticker.

    Returns number of entries removed.
    """
    removed = 0
    cache_root = _cache_dir()
    if not cache_root.is_dir():
        return 0
    for sub in cache_root.iterdir():
        if not sub.is_dir():
            continue
        for sub2 in sub.iterdir():
            if not sub2.is_dir():
                continue
            for f in sub2.iterdir():
                if f.suffix != ".json":
                    continue
                try:
                    data = json.loads(f.read_text())
                    aid = data.get("agent_id", "")
                    tk = data.get("ticker", "")
                    if agent_id and aid != agent_id:
                        continue
                    if ticker and tk != ticker:
                        continue
                    f.unlink()
                    removed += 1
                except (json.JSONDecodeError, OSError):
                    f.unlink()
                    removed += 1
    return removed


def cache_stats() -> dict[str, Any]:
    """Return cache statistics."""
    cache_root = _cache_dir()
    if not cache_root.is_dir():
        return {"enabled": decision_cache_enabled(), "total_entries": 0, "size_bytes": 0}
    total = 0
    total_bytes = 0
    agents: set[str] = set()
    tickers: set[str] = set()
    for sub in cache_root.iterdir():
        if not sub.is_dir():
            continue
        for sub2 in sub.iterdir():
            if not sub2.is_dir():
                continue
            for f in sub2.iterdir():
                if f.suffix != ".json":
                    continue
                total += 1
                total_bytes += f.stat().st_size
                try:
                    data = json.loads(f.read_text())
                    agents.add(data.get("agent_id", "unknown"))
                    tickers.add(data.get("ticker", "unknown"))
                except Exception:
                    pass
    return {
        "enabled": decision_cache_enabled(),
        "total_entries": total,
        "size_bytes": total_bytes,
        "agents": sorted(agents),
        "tickers": sorted(tickers),
    }


__all__ = [
    "cache_stats",
    "decision_cache_enabled",
    "invalidate_cache",
    "read_cached_decision",
    "write_cached_decision",
]
