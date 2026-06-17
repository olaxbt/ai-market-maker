"""Per-agent LLM inference when ``arbitrator_mode == "agent_llm"``.

Deterministic Tier-0 output is prompt context only. On failure, emit
``source: error`` (no deterministic fallback).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any

from openai import OpenAI

# Lazy-loaded decision cache
_DECISION_CACHE: Any = None


def _get_decision_cache() -> Any:
    global _DECISION_CACHE
    if _DECISION_CACHE is not None:
        return _DECISION_CACHE
    try:
        from llm.decision_cache import (
            decision_cache_enabled,
            read_cached_decision,
            write_cached_decision,
        )

        _DECISION_CACHE = {
            "read": read_cached_decision,
            "write": write_cached_decision,
            "enabled": decision_cache_enabled,
        }
    except ImportError:
        _DECISION_CACHE = {}
    return _DECISION_CACHE


def _cache_key_for_agent(
    agent_id: str,
    ticker: str | None,
    prompt_text: str,
) -> str | None:
    """Generate a deterministic cache key for this agent call.

    Returns None if caching is disabled.
    """
    cache = _get_decision_cache()
    enabled_fn = cache.get("enabled")
    if enabled_fn and not enabled_fn():
        return None
    raw = f"{agent_id}|{ticker or ''}|{prompt_text}"
    return hashlib.sha256(raw.encode()).hexdigest()


logger = logging.getLogger(__name__)


_AGENT_INFO: dict[str, dict[str, str]] = {
    "1.1": {"name": "Monetary Sentinel", "dir": "1.1_monetary_sentinel"},
    "1.2": {"name": "News & Narrative Miner", "dir": "1.2_news_narrative_miner"},
    "2.1": {"name": "Pattern Recognition Bot", "dir": "2.1_pattern_recognition_bot"},
    "2.2": {"name": "Statistical Alpha Engine", "dir": "2.2_statistical_alpha_engine"},
    "2.3": {"name": "Technical TA Engine", "dir": "2.3_technical_ta_engine"},
    "3.1": {"name": "Retail Hype Tracker", "dir": "3.1_retail_hype_tracker"},
    "3.2": {"name": "Pro Bias Analyst", "dir": "3.2_pro_bias_analyst"},
    "4.1": {"name": "Whale Behavior Analyst", "dir": "4.1_whale_behavior_analyst"},
    "4.2": {"name": "Liquidity & Order Flow", "dir": "4.2_liquidity_order_flow"},
}

# Per-agent PascalCase schema (weight_assigner extractors read these fields).
# Nested keys are documented inline; underscores denote nesting.
_AGENT_OUTPUT_SCHEMA: dict[str, list[str]] = {
    "1.1": ["macro_regime_state", "Liquidity_Score"],
    "1.2": ["News_Impact_Score", "Event_Type"],
    "2.1": ["Setup_Score", "pattern"],
    "2.2": ["cross_sectional_z_score", "kalman_support", "alpha_signal"],
    "2.3": [
        "ta_indicators.rsi",
        "ta_indicators.macd_hist",
        "ta_indicators.obv",
        "ta_indicators.atr_pct",
        "ta_indicators.adx",
        "ta_indicators.ema.fast",
        "ta_indicators.ema.slow",
        "ta_indicators.volume",
        "ta_indicators.pattern_rec",
    ],
    "3.1": ["FOMO_Level", "Divergence_Warning"],
    "3.2": ["Pro_Bias", "ETF_Trend"],
    "4.1": ["Dump_Probability", "Sell_Pressure_Gauge"],
    "4.2": ["Slippage_Risk_Score", "Order_Imbalance"],
}

# Neutral defaults for every field — returned when LLM fails or omits a field.
_NEUTRAL_CONTRACT: dict[str, dict[str, Any]] = {
    "1.1": {"macro_regime_state": "neutral", "Liquidity_Score": 50},
    "1.2": {"News_Impact_Score": 50, "Event_Type": "neutral"},
    "2.1": {"Setup_Score": 50, "pattern": "none"},
    "2.2": {"cross_sectional_z_score": 0.0, "kalman_support": 50, "alpha_signal": 0.0},
    "2.3": {
        "ta_indicators": {
            "rsi": 50,
            "macd_hist": 0.0,
            "obv": 0,
            "atr_pct": 0.0,
            "adx": 25,
            "ema": {"fast": 0.0, "slow": 0.0},
            "volume": 0,
            "pattern_rec": "none",
        }
    },
    "3.1": {"FOMO_Level": 50, "Divergence_Warning": 50},
    "3.2": {"Pro_Bias": 50, "ETF_Trend": 50},
    "4.1": {"Dump_Probability": 50, "Sell_Pressure_Gauge": 50},
    "4.2": {"Slippage_Risk_Score": 50, "Order_Imbalance": 0.0},
}

_AGENTS_BASE = Path(__file__).resolve().parent.parent / "agents" / "operator"


def _env(key: str, default: str = "") -> str:
    return (os.getenv(key) or default).strip()


_LLM_CLIENT: OpenAI | None = None
_LLM_MODEL: str = "deepseek-chat"


def _init_llm() -> None:
    """Initialise the LLM client. Raises ValueError if no API key."""
    global _LLM_CLIENT, _LLM_MODEL
    if _LLM_CLIENT is not None:
        return

    api_key = _env("DEEPSEEK_API_KEY") or _env("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "agent_llm mode requires an LLM API key. "
            "Set DEEPSEEK_API_KEY or OPENAI_API_KEY environment variable."
        )
    base_url = _env("AIMM_LLM_BASE_URL", default="https://api.deepseek.com/v1")
    _LLM_CLIENT = OpenAI(api_key=api_key, base_url=base_url)
    _LLM_MODEL = _env("AIMM_LLM_MODEL", default="deepseek-chat")
    logger.info("agent_llm client initialised (model=%s, base=%s)", _LLM_MODEL, base_url)


def _get_client() -> OpenAI:
    _init_llm()
    assert _LLM_CLIENT is not None
    return _LLM_CLIENT


def get_default_model() -> str:
    _init_llm()
    return _LLM_MODEL


def _load_persona(agent_id: str) -> str:
    info = _AGENT_INFO.get(agent_id)
    if not info:
        return f"You are a generic trading analyst (agent {agent_id})."
    persona_path = _AGENTS_BASE / info["dir"] / "persona.md"
    if not persona_path.is_file():
        return f"You are {info['name']} (agent {agent_id})."
    return persona_path.read_text(encoding="utf-8")


def _load_skill(agent_id: str) -> str:
    info = _AGENT_INFO.get(agent_id)
    if not info:
        return ""
    skill_path = _AGENTS_BASE / info["dir"] / "SKILL.md"
    if not skill_path.is_file():
        return ""
    return skill_path.read_text(encoding="utf-8")


def _ohlcv_for_ticker(state: dict[str, Any], ticker: str) -> list[Any]:
    """Get OHLCV bars for a ticker from state (same logic as desk_inputs)."""
    md = state.get("market_data")
    if not isinstance(md, dict):
        return []
    row = md.get(ticker)
    if not isinstance(row, dict):
        return []
    ohlcv = row.get("ohlcv")
    return ohlcv if isinstance(ohlcv, list) else []


def _ohlcv_summary(ohlcv: list[Any], max_bars: int = 30) -> str:
    """Compact OHLCV summary: last N bars + key stats."""
    if not ohlcv:
        return "no OHLCV data"
    window = ohlcv[-max_bars:] if len(ohlcv) > max_bars else ohlcv
    lines = [f"Bars: {len(window)} (showing last {min(len(window), max_bars)} of {len(ohlcv)})"]
    try:
        closes = [float(b[4]) for b in window if len(b) > 4]
        if closes:
            high = max(closes)
            low = min(closes)
            current = closes[-1]
            change_pct = ((current - closes[0]) / closes[0] * 100) if closes[0] else 0
            lines.append(f"Price range: {low:.2f} – {high:.2f}")
            lines.append(f"Current: {current:.2f} ({change_pct:+.2f}% over window)")
            recent = ", ".join(f"{c:.2f}" for c in closes[-5:])
            lines.append(f"Last 5 closes: {recent}")
    except (IndexError, TypeError, ValueError):
        lines.append("(unable to parse OHLCV values)")
    try:
        vols = [float(b[5]) for b in window if len(b) > 5]
        if vols:
            lines.append(f"Avg volume: {sum(vols) / len(vols):.0f}")
    except (IndexError, TypeError, ValueError):
        pass
    return "\n".join(lines)


def _build_nexus_context(state: dict[str, Any]) -> str:
    """Extract Nexus bundle from shared_memory."""
    sm = state.get("shared_memory") or {}
    nexus = sm.get("nexus") or {}
    if not isinstance(nexus, dict):
        return ""
    parts = []
    news = nexus.get("news")
    if isinstance(news, list) and news:
        for n in news[:5]:
            if isinstance(n, dict):
                title = n.get("title", "")[:100]
                sentiment = n.get("sentiment", "")
                if title:
                    parts.append(f"  - [{sentiment}] {title}")
    funding = nexus.get("funding")
    if funding is not None:
        parts.append(f"Funding rate: {funding}")
    oi = nexus.get("open_interest") or nexus.get("oi")
    if oi is not None:
        parts.append(f"Open interest: {oi}")
    onchain = nexus.get("onchain")
    if isinstance(onchain, dict):
        for k, v in onchain.items():
            if v is not None:
                parts.append(f"On-chain ({k}): {v}")
    return "\n".join(parts) if parts else ""


def _build_depth_context(state: dict[str, Any], ticker: str) -> str:
    """Extract order-book depth from market_data[ticker].nexus_depth."""
    md = state.get("market_data")
    if not isinstance(md, dict):
        return ""
    row = md.get(ticker)
    if not isinstance(row, dict):
        return ""
    depth = row.get("nexus_depth") or row.get("orderbook") or {}
    if not isinstance(depth, dict):
        return ""
    bids = depth.get("bids") or []
    asks = depth.get("asks") or []
    if not bids and not asks:
        return ""
    parts = [f"Order book depth: {len(bids)} bids / {len(asks)} asks"]
    if bids:
        try:
            best_bid = float(bids[0][0]) if isinstance(bids[0], (list, tuple)) else 0
            bid_vol = sum(
                float(b[1]) for b in bids[:5] if isinstance(b, (list, tuple)) and len(b) > 1
            )
            parts.append(f"  Best bid: {best_bid:.2f} (top-5 vol: {bid_vol:.2f})")
        except (IndexError, TypeError, ValueError):
            pass
    if asks:
        try:
            best_ask = float(asks[0][0]) if isinstance(asks[0], (list, tuple)) else 0
            ask_vol = sum(
                float(a[1]) for a in asks[:5] if isinstance(a, (list, tuple)) and len(a) > 1
            )
            parts.append(f"  Best ask: {best_ask:.2f} (top-5 vol: {ask_vol:.2f})")
        except (IndexError, TypeError, ValueError):
            pass
        spread = abs(best_ask - best_bid) if best_bid and best_ask else 0
        parts.append(f"  Spread: {spread:.4f}")
    return "\n".join(parts)


def _build_universe_context(state: dict[str, Any]) -> str:
    """List the trading universe."""
    universe = state.get("universe")
    if not universe or not isinstance(universe, (list, tuple)):
        return ""
    valid = [str(s) for s in universe][:10]
    return f"Universe ({len(valid)} tickers): {', '.join(valid)}"


def _build_deterministic_context(contract: dict[str, Any] | None, agent_id: str) -> str:
    """Format a deterministic Tier-0 contract as LLM context only (not fallback)."""
    if not contract:
        return "No deterministic analysis available."
    allowed = _AGENT_OUTPUT_SCHEMA.get(agent_id, [])
    if not allowed:
        return "No deterministic analysis available."

    parts = ["Deterministic analysis (context only):"]
    for key in allowed:
        # Handle nested keys like "ta_indicators"
        if key.startswith("ta_indicators"):
            ti = contract.get("ta_indicators")
            if isinstance(ti, dict):
                parts.append(f"  ta_indicators: {json.dumps(ti, default=str)[:500]}")
        else:
            val = contract.get(key)
            if val is not None:
                parts.append(f"  {key}: {val}")
    return "\n".join(parts)


def _build_market_context(
    state: dict[str, Any],
    ticker: str | None = None,
    deterministic_contract: dict[str, Any] | None = None,
    agent_id: str | None = None,
) -> str:
    """Build rich market context for an LLM agent prompt.

    Includes:
    - Ticker and universe
    - OHLCV bars (last 30, price stats)
    - Order book depth
    - Nexus news / funding / OI / on-chain
    - Deterministic Tier-0 findings (context only, not fallback)
    """
    if not ticker:
        ticker = state.get("ticker", "BTC/USDT")
    lines = [f"Ticker: {ticker}"]

    uni = _build_universe_context(state)
    if uni:
        lines.append(f"\n## Universe\n{uni}")

    ohlcv = _ohlcv_for_ticker(state, ticker)
    ohlcv_str = _ohlcv_summary(ohlcv, max_bars=30)
    lines.append(f"\n## OHLCV Data ({ticker})\n{ohlcv_str}")

    depth = _build_depth_context(state, ticker)
    if depth:
        lines.append(f"\n## Order Book\n{depth}")

    nexus = _build_nexus_context(state)
    if nexus:
        lines.append(f"\n## Nexus Data\n{nexus}")

    if deterministic_contract is not None and agent_id is not None:
        det = _build_deterministic_context(deterministic_contract, agent_id)
        if det:
            lines.append(f"\n## Deterministic Baseline\n{det}")

    return "\n".join(lines)


def _output_schema_json(agent_id: str) -> str:
    """Return the JSON schema the LLM must output, with exact field types."""
    neutral = _NEUTRAL_CONTRACT.get(agent_id, {})
    return json.dumps(neutral, indent=2)


def _build_agent_prompt(
    agent_id: str,
    persona: str,
    skill: str,
    market_context: str,
) -> tuple[str, str]:
    """Build system + user prompt for a single agent LLM inference.

    The LLM is instructed to produce the SAME PascalCase fields the
    weight assigner reads, with no fallback to deterministic math.
    """
    agent_name = _AGENT_INFO.get(agent_id, {}).get("name", f"Agent {agent_id}")
    schema_json = _output_schema_json(agent_id)

    system = (
        f"You are {agent_name} (agent ID: {agent_id}), a specialised agent "
        f"in a multi-agent trading system.\n\n"
        f"## Your Persona\n{persona}\n\n"
        f"## Your Capabilities (SKILL.md)\n{skill}\n\n"
        "## Your Task\n"
        "Analyse the market data below and produce structured output "
        "that matches the expected agent schema exactly.\n\n"
        "### Critical Rules:\n"
        "- The deterministic analysis is **context only**. Do NOT copy it verbatim.\n"
        "- You must reason from the raw market data and produce your OWN assessment.\n"
        "- Output ONLY valid JSON with these exact fields:\n"
        "```json\n"
        f"{schema_json}\n"
        "```\n"
        "- Every field is required. If you have no strong opinion, use the neutral default shown above.\n"
        '- Add a "reasoning" field (string) explaining your key signal adjustments.\n'
        "Output ONLY the JSON on a single line or pretty-printed. No preamble, no markdown fences.\n"
    )

    user = f"## Current Market Data\n{market_context}\n\nProduce your structured signal now."

    return system, user


def _parse_llm_json(text: str | None) -> dict[str, Any]:
    """Robust JSON extraction from LLM output."""
    if not text or not text.strip():
        return {}
    raw = text.strip()
    if raw.startswith("```"):
        idx = raw.find("\n")
        if idx != -1:
            raw = raw[idx:].strip()
        if raw.endswith("```"):
            raw = raw[:-3].strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        raw = raw[start : end + 1]
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else {}
    except json.JSONDecodeError:
        return {}


def _fill_missing_fields(output: dict[str, Any], agent_id: str) -> dict[str, Any]:
    """Fill any missing PascalCase fields with neutral defaults.

    Ensures the weight assigner always gets a complete schema.
    """
    neutral = _NEUTRAL_CONTRACT.get(agent_id, {})
    if not neutral:
        return output

    # Fill top-level scalar fields
    for key, default in neutral.items():
        if isinstance(default, dict) and key not in output:
            # Entire nested dict missing (e.g. ta_indicators)
            output[key] = _deep_copy(default)
        elif isinstance(default, dict) and key in output:
            # Merge nested dict fields
            existing = output[key]
            if isinstance(existing, dict):
                for subkey, subdefault in default.items():
                    if subkey not in existing:
                        # Handle deeper nesting (e.g. ema.fast)
                        if isinstance(subdefault, dict):
                            existing[subkey] = _deep_copy(subdefault)
                        else:
                            existing[subkey] = subdefault
            else:
                output[key] = _deep_copy(default)
        elif key not in output:
            output[key] = default

    return output


def _deep_copy(val: Any) -> Any:
    if isinstance(val, dict):
        return {k: _deep_copy(v) for k, v in val.items()}
    if isinstance(val, list):
        return [v for v in val]
    return val


def _error_contract(agent_id: str, error_reason: str) -> dict[str, Any]:
    """Return a neutral contract with error flag — **not** deterministic data.

    This is what gets emitted when the LLM call fails. The deterministic
    contract is NOT substituted. The system sees a clear error signal.
    """
    neutral = _NEUTRAL_CONTRACT.get(agent_id, {})
    contract = _deep_copy(neutral)
    contract["agent"] = agent_id
    contract["agent_id"] = agent_id
    contract["label"] = _AGENT_INFO.get(agent_id, {}).get("name", agent_id)
    contract["source"] = "error"
    contract["llm_enabled"] = True
    contract["llm_error"] = error_reason
    contract["confidence"] = 0.0
    contract["composite"] = 50
    return contract


def infer_agent(
    agent_id: str,
    state: dict[str, Any],
    *,
    deterministic_contract: dict[str, Any] | None = None,
    ticker: str | None = None,
    model: str | None = None,
    temperature: float = 0.1,
    max_tokens: int = 1024,
) -> dict[str, Any]:
    """Run a single agent's LLM inference.

    **No fallback to deterministic.** If the LLM call fails, an error
    contract with neutral values is returned (source: error).

    Args:
        agent_id: Agent identifier (e.g., ``"2.3"``).
        state: Full HedgeFundState dict.
        deterministic_contract: Tier-0 deterministic findings —
            used ONLY as context in the prompt. NOT a fallback output.
        ticker: Override primary ticker (default from state).
        model: Model override (default from ``AIMM_LLM_MODEL`` env).
        temperature: LLM temperature.
        max_tokens: Max output tokens.

    Returns:
        Dict with the agent's PascalCase fields + metadata.
        ``source`` is ``"agent_llm"`` on success, ``"error"`` on failure.
    """
    try:
        client = _get_client()
    except ValueError as e:
        raise ValueError(
            f"agent_llm mode requires an LLM API key for agent {agent_id}. "
            "Set DEEPSEEK_API_KEY or OPENAI_API_KEY."
        ) from e

    persona = _load_persona(agent_id)
    skill = _load_skill(agent_id)
    market_context = _build_market_context(
        state,
        ticker=ticker,
        deterministic_contract=deterministic_contract,
        agent_id=agent_id,
    )

    system, user = _build_agent_prompt(agent_id, persona, skill, market_context)

    # Decision cache: check before LLM call
    cache = _get_decision_cache()
    full_prompt = system + "\n" + user
    ck = _cache_key_for_agent(agent_id, ticker or state.get("ticker", ""), full_prompt)
    if ck:
        cached = cache.get("read")
        if cached:
            hit = cached(agent_id, ck)
            if hit is not None:
                logger.info("agent_llm: cache HIT for %s (key=%s...)", agent_id, ck[:12])
                hit["agent"] = agent_id
                hit["agent_id"] = agent_id
                hit["source"] = "agent_llm"
                hit["llm_enabled"] = True
                hit["cached"] = True
                return _fill_missing_fields(hit, agent_id)

    try:
        resp = client.chat.completions.create(
            model=model or get_default_model(),
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=45,
        )
    except Exception as e:
        logger.warning("agent_llm: LLM call failed for %s: %s", agent_id, e)
        return _error_contract(agent_id, f"API error: {e}")

    text = resp.choices[0].message.content or ""
    obj = _parse_llm_json(text)
    if not obj:
        logger.warning("agent_llm: unparseable output for %s", agent_id)
        return _error_contract(agent_id, "unparseable LLM response")

    result = _fill_missing_fields(obj, agent_id)
    result["agent"] = agent_id
    result["agent_id"] = agent_id
    result["label"] = _AGENT_INFO.get(agent_id, {}).get("name", agent_id)
    result["source"] = "agent_llm"
    result["llm_enabled"] = True

    # Write to cache for reproducibility
    write_fn = cache.get("write")
    if ck and write_fn:
        try:
            write_fn(agent_id, ck, result)
        except Exception as e:
            logger.debug("agent_llm: cache write failed: %s", e)

    return result


def check_api_key() -> str | None:
    """Return None if API key is available, or an error message string.

    Idempotent. Use at startup to validate env before entering agent_llm mode.
    """
    try:
        _init_llm()
        return None
    except ValueError as e:
        return str(e)


__all__ = [
    "infer_agent",
    "check_api_key",
    "get_default_model",
]
