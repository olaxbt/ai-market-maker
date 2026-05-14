"""Single place to resolve the `.runs` tree (backtests, leadpage JSONL, event logs).

Historically code used ``Path(".runs")``, which depends on **process cwd**. That breaks
when Uvicorn/Gunicorn is started from a subdirectory, and it confuses Docker Desktop setups
where the UI writes under the host repo but the API container only sees ``/app/.runs``.

Override with absolute path::

    export AIMM_RUNS_DIR=/path/to/your/repo/.runs
"""

from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    """Project root (parent of ``src/``)."""
    # src/config/runs_paths.py -> parents[0]=config, [1]=src, [2]=repo
    return Path(__file__).resolve().parents[2]


def runs_dir() -> Path:
    """Directory for ``backtests/``, ``leadpage/``, ``*.events.jsonl``, etc."""
    raw = (os.getenv("AIMM_RUNS_DIR") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return (repo_root() / ".runs").resolve()
