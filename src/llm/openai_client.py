from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI

from llm.tool_registry import call_tool, openai_tools_payload


def _env_bool(name: str, default: bool = False) -> bool:
    v = (os.getenv(name) or "").strip().lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "y", "on")


def run_tool_calling_chat(
    *,
    system: str,
    user: str,
    tool_specs: List[Any],
    model: Optional[str] = None,
    max_tool_rounds: int = 3,
) -> Tuple[str, List[Dict[str, Any]]]:
    """Run an OpenAI chat with optional tool calls (bounded).

    Returns (final_text, tool_events) where tool_events is a list of {name, args, result}.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required when AI_MARKET_MAKER_USE_LLM=1")

    base_url = (os.getenv("OPENAI_BASE_URL") or "").strip() or None
    client = OpenAI(api_key=api_key, base_url=base_url)
    model_name = model or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    tool_events: List[Dict[str, Any]] = []
    tool_payload = openai_tools_payload(tool_specs)

    for _ in range(max_tool_rounds + 1):
        resp = client.chat.completions.create(
            model=model_name,
            messages=messages,
            tools=tool_payload,
            tool_choice="auto",
        )
        choice = resp.choices[0]
        msg = choice.message

        # OpenAI SDK returns tool_calls on the assistant message when needed.
        tool_calls = getattr(msg, "tool_calls", None) or []
        if tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in tool_calls
                    ],
                }
            )
            for tc in tool_calls:
                name = tc.function.name
                args = json.loads(tc.function.arguments or "{}")
                result = call_tool(tool_specs, name=name, arguments=args)
                # Preserve the provider-facing name and the canonical name when available.
                canonical = None
                for s in tool_specs:
                    if getattr(s, "wire_name", None) == name or getattr(s, "name", None) == name:
                        canonical = getattr(s, "name", None)
                        break
                tool_events.append(
                    {"name": canonical or name, "wire_name": name, "args": args, "result": result}
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result),
                    }
                )
            continue

        # No tool calls -> final
        final_text = msg.content or ""
        return final_text, tool_events

    return "", tool_events


__all__ = ["run_tool_calling_chat"]
