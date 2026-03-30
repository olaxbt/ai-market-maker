"""JSON Schema validation for Nexus payload contract."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from jsonschema import Draft7Validator


def _load_schema_text() -> str:
    """Load the checked-in Nexus payload schema.

    Works both from a source checkout and from an installed wheel/sdist.
    """
    from importlib.resources import files

    return (files("api.schema") / "nexus_payload.json").read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def _validator() -> Draft7Validator:
    schema = json.loads(_load_schema_text())
    return Draft7Validator(schema)


def validate_nexus_payload(payload: dict[str, Any]) -> None:
    """Raise ValueError with a compact message if payload violates schema."""
    validator = _validator()
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
    if not errors:
        return
    first = errors[0]
    path = ".".join(str(x) for x in first.path) or "<root>"
    raise ValueError(f"Nexus payload schema validation failed at {path}: {first.message}")
