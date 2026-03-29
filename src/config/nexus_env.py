"""Environment helpers for **OLAXBT Nexus**–aligned data and tooling.

When live Nexus market/quant endpoints are wired, adapters read configuration here
so the graph stays configurable without hardcoding URLs.
"""

from __future__ import annotations

import os
from typing import Mapping

# Optional base URL for OLAXBT Nexus data / quant APIs (set when integrating).
NEXUS_DATA_BASE_URL_ENV = "OLAXBT_NEXUS_DATA_BASE_URL"


def load_nexus_data_base_url(*, env: Mapping[str, str] | None = None) -> str | None:
    """Return trimmed URL or ``None`` if unset. Used by ``NexusAdapter`` and future clients."""
    env_map = env if env is not None else os.environ
    raw = (env_map.get(NEXUS_DATA_BASE_URL_ENV) or "").strip()
    return raw or None


__all__ = ["NEXUS_DATA_BASE_URL_ENV", "load_nexus_data_base_url"]
