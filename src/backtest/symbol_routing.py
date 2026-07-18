"""Per-symbol strategy routing for backtests (agent-led vs VCP pattern)."""

from __future__ import annotations

import os
from typing import Any

DEFAULT_AGENT_LED_SYMBOLS: frozenset[str] = frozenset({"BTC/USDT", "ETH/USDT", "SOL/USDT"})


def parse_symbol_list(raw: str) -> list[str]:
    return [s.strip() for s in raw.split(",") if s.strip()]


def resolve_agent_led_symbols(
    *,
    universe: list[str] | None = None,
    deploy_cfg: dict[str, Any] | None = None,
    explicit: list[str] | None = None,
    env: dict[str, str] | None = None,
) -> frozenset[str]:
    """Symbols that use LangGraph agent signals; others use VCP pattern scanner."""
    if explicit:
        return frozenset(str(s) for s in explicit if str(s).strip())

    env = env if env is not None else dict(os.environ)
    env_raw = (env.get("AIMM_AGENT_LED_SYMBOLS") or "").strip()
    if env_raw:
        return frozenset(parse_symbol_list(env_raw))

    if deploy_cfg:
        exec_cfg = deploy_cfg.get("execution") or {}
        als = exec_cfg.get("agent_led_symbols")
        if isinstance(als, list) and als:
            return frozenset(str(s) for s in als if str(s).strip())
        bt = deploy_cfg.get("agent_led_symbols")
        if isinstance(bt, list) and bt:
            return frozenset(str(s) for s in bt if str(s).strip())

    if universe:
        ul = list(universe)
        led = [s for s in ul if s in DEFAULT_AGENT_LED_SYMBOLS]
        if led:
            return frozenset(led)
    return frozenset(DEFAULT_AGENT_LED_SYMBOLS)


def uses_mixed_routing(agent_led: frozenset[str], universe: list[str]) -> bool:
    ul = set(universe)
    vcp = ul - agent_led
    return bool(vcp) and bool(ul & agent_led)


__all__ = [
    "DEFAULT_AGENT_LED_SYMBOLS",
    "parse_symbol_list",
    "resolve_agent_led_symbols",
    "uses_mixed_routing",
]
