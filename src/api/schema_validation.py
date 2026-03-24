"""JSON Schema validation for Nexus payload contract."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

from jsonschema import Draft7Validator

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schema" / "nexus_payload.json"


@lru_cache(maxsize=1)
def _validator() -> Draft7Validator:
    schema = json.loads(SCHEMA_PATH.read_text())
    return Draft7Validator(schema)


def validate_nexus_payload(payload: Dict[str, Any]) -> None:
    """Raise ValueError with a compact message if payload violates schema."""
    validator = _validator()
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
    if not errors:
        return
    first = errors[0]
    path = ".".join(str(x) for x in first.path) or "<root>"
    raise ValueError(f"Nexus payload schema validation failed at {path}: {first.message}")
