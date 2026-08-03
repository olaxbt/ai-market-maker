"""Read agent decision from iteration receipts (nested or legacy flat)."""

from __future__ import annotations

from typing import Any


def decision_from_iteration(it: dict[str, Any]) -> dict[str, Any]:
    """Return decision dict from iteration row (``decision`` or legacy ``trade_intent``)."""
    dec = it.get("decision")
    if isinstance(dec, dict):
        return dec
    ti = it.get("trade_intent")
    return ti if isinstance(ti, dict) else {}
