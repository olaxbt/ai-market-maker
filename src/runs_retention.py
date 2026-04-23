"""Retention policy for `.runs/` artifacts.

Backtests and live runs can accumulate quickly (events.jsonl, iterations, bundles, evaluations).
This module enforces a simple safety policy:

- keep at least the most recent N artifacts (by mtime)
- cap total disk usage under `.runs/`

This is config-first (config/app.default.json) with env overrides for emergencies.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from config.app_settings import load_app_settings


@dataclass(frozen=True)
class RunsRetention:
    max_total_mb: int
    keep_last: int
    backtests_max_total_mb: int
    backtests_keep_last: int


def _env_int(name: str) -> int | None:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def load_runs_retention() -> RunsRetention:
    s = load_app_settings()
    max_total_mb = int(s.runs.max_total_mb)
    keep_last = int(s.runs.keep_last)
    backtests_max_total_mb = int(s.runs.backtests_max_total_mb)
    backtests_keep_last = int(s.runs.backtests_keep_last)
    # Optional env overrides
    v = _env_int("AIMM_RUNS_MAX_TOTAL_MB")
    if v is not None:
        max_total_mb = v
    v = _env_int("AIMM_RUNS_KEEP_LAST")
    if v is not None:
        keep_last = v
    v = _env_int("AIMM_RUNS_BACKTESTS_MAX_TOTAL_MB")
    if v is not None:
        backtests_max_total_mb = v
    v = _env_int("AIMM_RUNS_BACKTESTS_KEEP_LAST")
    if v is not None:
        backtests_keep_last = v
    max_total_mb = max(50, min(100_000, int(max_total_mb)))
    keep_last = max(10, min(100_000, int(keep_last)))
    backtests_max_total_mb = max(50, min(100_000, int(backtests_max_total_mb)))
    backtests_keep_last = max(5, min(100_000, int(backtests_keep_last)))
    return RunsRetention(
        max_total_mb=max_total_mb,
        keep_last=keep_last,
        backtests_max_total_mb=backtests_max_total_mb,
        backtests_keep_last=backtests_keep_last,
    )


def enforce_runs_retention(
    *, runs_dir: Path | None = None, keep_run_id: str | None = None
) -> dict[str, int]:
    """Enforce retention under `.runs/`.

    Returns a small stats dict for logging.
    """

    base = (runs_dir or Path(".runs")).resolve()
    if not base.exists() or not base.is_dir():
        return {"deleted_files": 0, "deleted_dirs": 0, "bytes_freed": 0}

    policy = load_runs_retention()
    max_bytes = int(policy.max_total_mb) * 1024 * 1024

    # Always preserve these root files.
    preserve_names = {"latest_run.txt", "policy_memory.jsonl", "index.jsonl"}

    # Collect deletable candidates (files + dirs) with mtime + size.
    files: list[tuple[float, int, Path]] = []
    dirs: list[tuple[float, int, Path]] = []
    for p in base.iterdir():
        if p.name in preserve_names:
            continue
        # Backtests are retained separately.
        if p.name == "backtests" and p.is_dir():
            continue
        if keep_run_id and p.name.startswith(keep_run_id):
            continue
        try:
            st = p.stat()
        except OSError:
            continue
        if p.is_file():
            files.append((st.st_mtime, st.st_size, p))
        elif p.is_dir():
            # Approximate dir size by summing contained files (bounded; okay for retention).
            sz = 0
            try:
                for f in p.rglob("*"):
                    if f.is_file():
                        try:
                            sz += f.stat().st_size
                        except OSError:
                            pass
            except OSError:
                sz = 0
            dirs.append((st.st_mtime, sz, p))

    # Current usage (recursive).
    total = 0
    for f in base.rglob("*"):
        if f.is_file():
            try:
                total += f.stat().st_size
            except OSError:
                pass

    # Keep last N by mtime across both files and dirs.
    candidates: list[tuple[float, int, Path, str]] = [
        (mt, sz, p, "file") for mt, sz, p in files
    ] + [(mt, sz, p, "dir") for mt, sz, p in dirs]
    candidates.sort(key=lambda r: r[0], reverse=True)  # newest first
    to_consider = candidates[policy.keep_last :]
    # Oldest first for deletion.
    to_consider.sort(key=lambda r: r[0])

    deleted_files = deleted_dirs = 0
    bytes_freed = 0
    for _mt, sz, p, kind in to_consider:
        if total <= max_bytes:
            break
        try:
            if kind == "file" and p.is_file():
                p.unlink(missing_ok=True)
                deleted_files += 1
                bytes_freed += int(sz)
                total -= int(sz)
            elif kind == "dir" and p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
                deleted_dirs += 1
                bytes_freed += int(sz)
                total -= int(sz)
        except OSError:
            continue

    return {
        "deleted_files": deleted_files,
        "deleted_dirs": deleted_dirs,
        "bytes_freed": bytes_freed,
    }


def _dir_size_bytes(p: Path) -> int:
    sz = 0
    for f in p.rglob("*"):
        if f.is_file():
            try:
                sz += f.stat().st_size
            except OSError:
                pass
    return sz


def enforce_backtests_retention(*, runs_dir: Path | None = None) -> dict[str, int]:
    """Enforce retention within `.runs/backtests/` by deleting oldest run directories."""

    base = (runs_dir or Path(".runs")).resolve()
    bt = base / "backtests"
    if not bt.exists() or not bt.is_dir():
        return {"deleted_dirs": 0, "bytes_freed": 0}

    policy = load_runs_retention()
    try:
        if not load_app_settings().runs.backtests_retention_enabled:
            return {"deleted_dirs": 0, "bytes_freed": 0}
    except Exception:
        # If settings can't be loaded, default to non-destructive behavior.
        return {"deleted_dirs": 0, "bytes_freed": 0}
    max_bytes = int(policy.backtests_max_total_mb) * 1024 * 1024

    run_dirs = []
    for d in bt.iterdir():
        if d.is_dir():
            try:
                st = d.stat()
            except OSError:
                continue
            run_dirs.append((st.st_mtime, _dir_size_bytes(d), d))
    run_dirs.sort(key=lambda r: r[0], reverse=True)  # newest first

    # Total usage
    total = sum(sz for _mt, sz, _d in run_dirs)

    # Never delete newest keep_last
    to_consider = run_dirs[policy.backtests_keep_last :]
    to_consider.sort(key=lambda r: r[0])  # oldest first

    deleted = 0
    freed = 0
    for _mt, sz, d in to_consider:
        if total <= max_bytes:
            break
        shutil.rmtree(d, ignore_errors=True)
        deleted += 1
        freed += int(sz)
        total -= int(sz)
    return {"deleted_dirs": deleted, "bytes_freed": freed}


__all__ = [
    "RunsRetention",
    "enforce_backtests_retention",
    "enforce_runs_retention",
    "load_runs_retention",
]
