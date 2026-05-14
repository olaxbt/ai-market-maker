from __future__ import annotations

from typing import Mapping


def env_bool(env: Mapping[str, str], name: str, *, default: bool = False) -> bool:
    raw = (env.get(name) or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


__all__ = ["env_bool"]
