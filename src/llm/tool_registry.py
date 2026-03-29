from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from adapters.nexus_adapter import get_nexus_adapter

JsonSchema = Dict[str, Any]

_NAME_PATTERN_NOTE = "Provider tool names must match ^[a-zA-Z0-9_-]+$ (no dots)."


def _wire_name(canonical: str) -> str:
    # OpenAI is permissive, but some OpenAI-compatible providers (e.g. DeepSeek)
    # reject dots in function names.
    return canonical.replace(".", "_")


@dataclass(frozen=True)
class ToolSpec:
    # Canonical tool name used in our app / manifest.
    name: str
    # Provider-safe name used when sending to OpenAI-compatible APIs.
    wire_name: str
    description: str
    parameters: JsonSchema
    handler: Callable[..., Dict[str, Any]]


def nexus_tool_specs(*, include_write_tools: bool = True) -> List[ToolSpec]:
    adapter = get_nexus_adapter()
    tools: List[ToolSpec] = [
        ToolSpec(
            name="nexus.fetch_market_depth",
            wire_name=_wire_name("nexus.fetch_market_depth"),
            description="Fetch order book depth for slippage/price discovery.",
            parameters={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 5},
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

    return tools


def openai_tools_payload(specs: List[ToolSpec]) -> List[Dict[str, Any]]:
    """Convert ToolSpec into OpenAI 'tools' payload for chat.completions."""
    return [
        {
            "type": "function",
            "function": {
                "name": s.wire_name,
                "description": f"{s.description} ({_NAME_PATTERN_NOTE})",
                "parameters": s.parameters,
            },
        }
        for s in specs
    ]


def call_tool(specs: List[ToolSpec], *, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    # Accept either canonical name or provider wire name.
    by_name = {s.name: s for s in specs} | {s.wire_name: s for s in specs}
    spec = by_name.get(name)
    if not spec:
        return {"status": "error", "error": f"unknown_tool: {name}"}
    try:
        return spec.handler(**(arguments or {}))
    except Exception as e:
        return {"status": "error", "error": str(e)}


__all__ = ["ToolSpec", "call_tool", "nexus_tool_specs", "openai_tools_payload"]
