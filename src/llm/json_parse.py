"""Small utilities for parsing JSON objects from LLM text outputs.

LLMs often return:
- markdown fenced blocks (```json ... ```)
- a short preamble before the JSON
- trailing commentary after the JSON

We keep parsing logic centralized so all nodes behave consistently.
"""

from __future__ import annotations

import json
from typing import Any


def parse_json_object(text: str) -> dict[str, Any] | None:
    """Best-effort JSON object extraction from model text.

    Returns a dict if a JSON object can be parsed, else None.
    """

    raw = (text or "").strip()
    if not raw:
        return None

    # Prefer fenced JSON blocks when present.
    if "```" in raw:
        for block in raw.split("```"):
            chunk = block.strip()
            if chunk.lower().startswith("json"):
                chunk = chunk[4:].lstrip()
            if chunk.startswith("{"):
                raw = chunk
                break

    try:
        out = json.loads(raw)
        return out if isinstance(out, dict) else None
    except Exception:
        pass

    # Fallback: parse the outer-most object substring.
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        try:
            out = json.loads(raw[start : end + 1])
            return out if isinstance(out, dict) else None
        except Exception:
            return None

    return None


__all__ = ["parse_json_object"]
