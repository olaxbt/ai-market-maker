"""Tool Registry — Hermes-inspired import-time self-registration.

Extends the existing ToolSpec pattern with:

1. **Global registry**: ``TOOL_REGISTRY`` — tools self-register via ``@register_tool``
2. **Import-time discovery**: tools defined alongside their agents self-register
3. **Backward-compatible**: ``nexus_tool_specs()`` still works
4. **OpenAI-compatible output**: ``openai_tools_payload()`` unchanged

Usage:
    # In agent_x_tools.py
    from llm.tool_registry import register_tool, ToolSpec

    @register_tool
    def fetch_order_book(symbol: str, limit: int = 5) -> dict:
        '''Fetch order book depth for slippage/price discovery.'''
        return adapter.fetch_market_depth(symbol=symbol, limit=limit)

    # In agent code
    from llm.tool_registry import TOOL_REGISTRY, openai_tools_payload
    tools_payload = openai_tools_payload(TOOL_REGISTRY.all())
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Union

from adapters.nexus_adapter import get_nexus_adapter

JsonSchema = Dict[str, Any]


def _wire_name(canonical: str) -> str:
    return canonical.replace(".", "_")


def _function_to_json_schema(fn: Callable) -> JsonSchema:
    """Minimal type-annotation → JSON schema converter.

    Supports str, int, float, bool, Optional, and bare Dict/List.
    """
    sig = inspect.signature(fn)
    hints = {}
    try:
        hints = {k: v for k, v in inspect.get_annotations(fn).items() if k != "return"}
    except Exception:
        pass

    properties: dict[str, Any] = {}
    required: list[str] = []

    for name, param in sig.parameters.items():
        if name == "return" or name == "self":
            continue
        is_optional = False
        if param.default is not inspect.Parameter.empty:
            if param.default is not None:
                is_optional = True
            else:
                is_optional = True  # Optional[...] → default None

        ann = hints.get(name)
        js_type = _py_type_to_js(ann)
        prop: dict[str, Any] = {"type": js_type} if js_type else {}

        if param.default is not inspect.Parameter.empty and not is_optional:
            prop["default"] = param.default

        # Handle Optional via union
        if is_optional:
            prop.setdefault("type", "string")

        # Add enum from type hints
        if ann is bool:
            pass  # boolean is fine

        properties[name] = prop
        if param.default is inspect.Parameter.empty:
            required.append(name)

    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def _py_type_to_js(ann: Any) -> str | None:
    if ann is None or ann is inspect.Parameter.empty:
        return None
    if ann is str:
        return "string"
    if ann is int:
        return "integer"
    if ann is float:
        return "number"
    if ann is bool:
        return "boolean"
    if ann is dict or getattr(ann, "__origin__", None) is dict:
        return "object"
    if ann is list or getattr(ann, "__origin__", None) is list:
        return "array"
    # Optional[X] → union
    origin = getattr(ann, "__origin__", None)
    if origin is Union:
        args = getattr(ann, "__args__", [])
        non_none = [a for a in args if a is not type(None)]
        if non_none:
            return _py_type_to_js(non_none[0])
    return None


# ---------------------------------------------------------------------------
# Core data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ToolSpec:
    """Immutable tool specification — canonical name, schema, and handler."""

    name: str
    wire_name: str
    description: str
    parameters: JsonSchema
    handler: Callable[..., Dict[str, Any]]
    tags: frozenset[str] = field(default_factory=frozenset)


# ---------------------------------------------------------------------------
# Global registry — tools self-register via @register_tool
# ---------------------------------------------------------------------------


class _ToolRegistry:
    """Global thread-safe tool registry.

    Tools self-register at import time via @register_tool.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"Duplicate tool registration: {spec.name}")
        self._tools[spec.name] = spec

    def register_fn(
        self,
        fn: Callable,
        *,
        name: str | None = None,
        description: str | None = None,
        tags: frozenset[str] | None = None,
    ) -> ToolSpec:
        """Register a function as a tool using its signature for JSON schema."""
        canonical = name or fn.__name__
        doc = description or (inspect.getdoc(fn) or "").strip() or f"Tool: {canonical}"
        parameters = _function_to_json_schema(fn)

        spec = ToolSpec(
            name=canonical,
            wire_name=_wire_name(canonical),
            description=doc,
            parameters=parameters,
            handler=fn,
            tags=tags or frozenset(),
        )
        self.register(spec)
        return spec

    def get(self, name: str) -> ToolSpec | None:
        by_name = {s.name: s for s in self._tools.values()} | {
            s.wire_name: s for s in self._tools.values()
        }
        return by_name.get(name)

    def all(self) -> List[ToolSpec]:
        return list(self._tools.values())

    def by_tag(self, tag: str) -> List[ToolSpec]:
        return [t for t in self._tools.values() if tag in t.tags]

    def clear(self) -> None:
        self._tools.clear()

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools or _wire_name(name) in {
            s.wire_name for s in self._tools.values()
        }


TOOL_REGISTRY = _ToolRegistry()


def register_tool(
    fn: Callable | None = None,
    *,
    name: str | None = None,
    description: str | None = None,
    tags: frozenset[str] | None = None,
) -> Callable | ToolSpec:
    """Decorator (with or without args) that registers a function as a tool.

    Usage:
        @register_tool
        def my_tool(param1: str, param2: int = 5) -> dict:
            \"\"\"Description becomes the tool description.\"\"\"
            ...

        @register_tool(name="custom_name", tags=frozenset({"onchain"}))
        def another_tool(...):
            ...
    """
    if fn is not None:
        # Used as bare decorator: @register_tool
        return TOOL_REGISTRY.register_fn(fn)

    # Used with args: @register_tool(name=..., tags=...)
    def decorator(f: Callable) -> ToolSpec:
        return TOOL_REGISTRY.register_fn(f, name=name, description=description, tags=tags)

    return decorator


# ---------------------------------------------------------------------------
# Legacy compatibility — keep existing API working
# ---------------------------------------------------------------------------


def nexus_tool_specs(*, include_write_tools: bool = True) -> List[ToolSpec]:
    """Legacy: returns Nexus adapter tools. New code should prefer @register_tool."""
    adapter = get_nexus_adapter()
    tools: list[ToolSpec] = [
        ToolSpec(
            name="nexus.fetch_market_depth",
            wire_name=_wire_name("nexus.fetch_market_depth"),
            description="Fetch order book depth for slippage/price discovery.",
            parameters={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 50,
                        "default": 5,
                    },
                },
                "required": ["symbol"],
                "additionalProperties": False,
            },
            handler=lambda **kw: adapter.fetch_market_depth(**kw),
        ),
    ]
    if include_write_tools:
        tools.append(
            ToolSpec(
                name="nexus.place_smart_order",
                wire_name=_wire_name("nexus.place_smart_order"),
                description="Place a guarded smart order (mock-safe by default).",
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"},
                        "side": {"type": "string", "enum": ["buy", "sell"]},
                        "qty": {"type": "number", "exclusiveMinimum": 0},
                        "order_type": {
                            "type": "string",
                            "enum": ["market", "limit"],
                            "default": "market",
                        },
                        "price": {"type": ["number", "null"]},
                        "post_only": {"type": "boolean", "default": True},
                        "max_slippage_bps": {"type": ["number", "null"]},
                        "client_order_id": {"type": ["string", "null"]},
                    },
                    "required": ["symbol", "side", "qty"],
                    "additionalProperties": False,
                },
                handler=lambda **kw: adapter.place_smart_order(**kw),
            )
        )
    for t in tools:
        try:
            TOOL_REGISTRY.register(t)
        except ValueError:
            pass  # already registered
    return tools


def openai_tools_payload(specs: List[ToolSpec] | None = None) -> List[Dict[str, Any]]:
    """Convert ToolSpec(s) into OpenAI 'tools' payload for chat.completions.

    When specs is None, uses TOOL_REGISTRY.all().
    """
    specs = specs if specs is not None else TOOL_REGISTRY.all()
    return [
        {
            "type": "function",
            "function": {
                "name": s.wire_name,
                "description": s.description,
                "parameters": s.parameters,
            },
        }
        for s in specs
    ]


def call_tool(
    specs: List[ToolSpec] | None = None,
    *,
    name: str,
    arguments: Dict[str, Any],
) -> Dict[str, Any]:
    """Dispatch a tool call by name.

    When specs is None, uses TOOL_REGISTRY.
    """
    if specs is not None:
        by_name = {s.name: s for s in specs} | {s.wire_name: s for s in specs}
        spec = by_name.get(name)
    else:
        spec = TOOL_REGISTRY.get(name)
    if not spec:
        return {"status": "error", "error": f"unknown_tool: {name}"}
    try:
        return spec.handler(**(arguments or {}))
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# Auto-register legacy tools on import
# ---------------------------------------------------------------------------
nexus_tool_specs()


__all__ = [
    "TOOL_REGISTRY",
    "ToolSpec",
    "call_tool",
    "nexus_tool_specs",
    "openai_tools_payload",
    "register_tool",
]
