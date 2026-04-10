from __future__ import annotations

import json
import logging
import os
import signal
import threading
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI

from llm.tool_registry import call_tool, openai_tools_payload

logger = logging.getLogger(__name__)


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
    temperature: Optional[float] = None,
    max_tool_rounds: int = 3,
    max_tokens: Optional[int] = None,
) -> Tuple[str, List[Dict[str, Any]]]:
    """Run an OpenAI chat with optional tool calls (bounded).

    Returns (final_text, tool_events) where tool_events is a list of {name, args, result}.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required when AI_MARKET_MAKER_USE_LLM=1")

    base_url = (os.getenv("OPENAI_BASE_URL") or "").strip() or None
    timeout_s_raw = (os.getenv("AIMM_LLM_TIMEOUT_S") or "").strip()
    try:
        timeout_s = float(timeout_s_raw) if timeout_s_raw else 60.0
    except ValueError:
        timeout_s = 60.0
    timeout_s = max(5.0, min(300.0, timeout_s))

    # OpenAI SDK options vary across versions; keep a safe fallback if kwargs are unsupported.
    try:
        client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout_s, max_retries=2)
    except TypeError:
        try:
            client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout_s)
        except TypeError:
            client = OpenAI(api_key=api_key, base_url=base_url)
    env_model = os.getenv("OPENAI_MODEL")
    model_name = model or env_model or "gpt-4o-mini"
    if base_url and "deepseek" in base_url and env_model and model and model != env_model:
        # This is the classic "provider supports X but we forced Y" mismatch.
        logger.warning(
            "LLM model override detected (base_url=%s, OPENAI_MODEL=%s, override_model=%s). "
            "If the provider rejects the override, remove per-agent model pins in config/agent_prompts.json.",
            base_url,
            env_model,
            model,
        )
    elif base_url and "deepseek" in base_url and not env_model:
        logger.warning(
            "OPENAI_BASE_URL looks like DeepSeek but OPENAI_MODEL is unset; defaulting to %s",
            model_name,
        )

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    tool_events: List[Dict[str, Any]] = []
    tool_payload = openai_tools_payload(tool_specs)

    for _ in range(max_tool_rounds + 1):
        create_kwargs: Dict[str, Any] = {"model": model_name, "messages": messages}
        if temperature is not None:
            try:
                t = float(temperature)
            except (TypeError, ValueError):
                t = None
            if t is not None:
                # OpenAI-compatible: 0..2
                create_kwargs["temperature"] = max(0.0, min(2.0, t))
        if max_tokens is not None:
            try:
                mt = int(max_tokens)
            except (TypeError, ValueError):
                mt = None
            if mt is not None and mt > 0:
                create_kwargs["max_tokens"] = mt
        if tool_payload:
            create_kwargs["tools"] = tool_payload
            create_kwargs["tool_choice"] = "auto"
        # Hard timeout guard: OpenAI-compatible endpoints occasionally hang without returning.
        # Use SIGALRM on Unix so backtests can proceed with a neutral fallback upstream.
        alarm_s = int(timeout_s)
        old_handler = None
        can_alarm = (
            alarm_s >= 1
            and hasattr(signal, "SIGALRM")
            and threading.current_thread() is threading.main_thread()
        )
        if can_alarm:
            old_handler = signal.getsignal(signal.SIGALRM)

            def _raise_timeout(_signum, _frame, *, _alarm_s: int = alarm_s):
                raise TimeoutError(f"LLM request exceeded {_alarm_s}s")

            signal.signal(signal.SIGALRM, _raise_timeout)
            signal.alarm(alarm_s)
        try:
            resp = client.chat.completions.create(**create_kwargs)
        except Exception as exc:
            # Provider errors are often opaque; include the resolved model/base_url in logs.
            logger.error(
                "LLM request failed (base_url=%s, model=%s): %s",
                base_url or "https://api.openai.com/v1",
                model_name,
                exc,
            )
            raise
        finally:
            if can_alarm:
                signal.alarm(0)
                if old_handler is not None:
                    signal.signal(signal.SIGALRM, old_handler)
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


def stream_chat_completion(
    *,
    system: str,
    user: str,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
) -> Any:
    """Return an OpenAI streaming iterator yielding assistant text deltas.

    This intentionally does **not** support tool calls. It's used for UI chat streaming.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required when AI_MARKET_MAKER_USE_LLM=1")

    base_url = (os.getenv("OPENAI_BASE_URL") or "").strip() or None
    timeout_s_raw = (os.getenv("AIMM_LLM_TIMEOUT_S") or "").strip()
    try:
        timeout_s = float(timeout_s_raw) if timeout_s_raw else 60.0
    except ValueError:
        timeout_s = 60.0
    timeout_s = max(5.0, min(300.0, timeout_s))

    try:
        client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout_s, max_retries=2)
    except TypeError:
        try:
            client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout_s)
        except TypeError:
            client = OpenAI(api_key=api_key, base_url=base_url)

    model_name = model or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    create_kwargs: Dict[str, Any] = {"model": model_name, "messages": messages, "stream": True}
    if max_tokens is not None:
        try:
            mt = int(max_tokens)
        except (TypeError, ValueError):
            mt = None
        if mt is not None and mt > 0:
            create_kwargs["max_tokens"] = mt
    return client.chat.completions.create(**create_kwargs)


__all__ = ["run_tool_calling_chat", "stream_chat_completion"]
