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

from config.llm_env import resolve_llm_config
from llm.json_parse import parse_json_object

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


def _date_tag_from_state(state: dict[str, Any]) -> str:
    sm = state.get("shared_memory") if isinstance(state.get("shared_memory"), dict) else {}
    bt = sm.get("backtest") if isinstance(sm.get("backtest"), dict) else {}
    ts = bt.get("window_last_ts_ms")
    if ts is None:
        ts = state.get("ts_ms")
    try:
        return str(int(float(ts)))
    except (TypeError, ValueError):
        return "na"


def _prompt_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


logger = logging.getLogger(__name__)


_AGENT_INFO: dict[str, dict[str, str]] = {
    "monetary_sentinel": {"name": "Monetary Sentinel", "dir": "1.1_monetary_sentinel"},
    "news_narrative_miner": {"name": "News & Narrative Miner", "dir": "1.2_news_narrative_miner"},
    "pattern_recognition_bot": {
        "name": "Pattern Recognition Bot",
        "dir": "2.1_pattern_recognition_bot",
    },
    "statistical_alpha_engine": {
        "name": "Statistical Alpha Engine",
        "dir": "2.2_statistical_alpha_engine",
    },
    "technical_ta_engine": {"name": "Technical TA Engine", "dir": "2.3_technical_ta_engine"},
    "retail_hype_tracker": {"name": "Retail Hype Tracker", "dir": "3.1_retail_hype_tracker"},
    "pro_bias_analyst": {"name": "Pro Bias Analyst", "dir": "3.2_pro_bias_analyst"},
    "whale_behavior_analyst": {
        "name": "Whale Behavior Analyst",
        "dir": "4.1_whale_behavior_analyst",
    },
    "liquidity_order_flow": {"name": "Liquidity & Order Flow", "dir": "4.2_liquidity_order_flow"},
}

# Per-agent PascalCase schema (weight_assigner extractors read these fields).
# Nested keys are documented inline; underscores denote nesting.
_AGENT_OUTPUT_SCHEMA: dict[str, list[str]] = {
    "monetary_sentinel": ["macro_regime_state", "Liquidity_Score"],
    "news_narrative_miner": ["News_Impact_Score", "Event_Type"],
    "pattern_recognition_bot": ["Setup_Score", "pattern"],
    "statistical_alpha_engine": ["cross_sectional_z_score", "kalman_support", "alpha_signal"],
    "technical_ta_engine": [
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
    "retail_hype_tracker": ["FOMO_Level", "Divergence_Warning"],
    "pro_bias_analyst": ["Pro_Bias", "ETF_Trend"],
    "whale_behavior_analyst": ["Dump_Probability", "Sell_Pressure_Gauge"],
    "liquidity_order_flow": ["Slippage_Risk_Score", "Order_Imbalance"],
}

# Neutral defaults for every field — returned when LLM fails or omits a field.
_NEUTRAL_CONTRACT: dict[str, dict[str, Any]] = {
    "monetary_sentinel": {"macro_regime_state": "neutral", "Liquidity_Score": 50},
    "news_narrative_miner": {"News_Impact_Score": 50, "Event_Type": "neutral"},
    "pattern_recognition_bot": {"Setup_Score": 50, "pattern": "none"},
    "statistical_alpha_engine": {
        "cross_sectional_z_score": 0.0,
        "kalman_support": 50,
        "alpha_signal": 0.0,
    },
    "technical_ta_engine": {
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
    "retail_hype_tracker": {"FOMO_Level": 50, "Divergence_Warning": 50},
    "pro_bias_analyst": {"Pro_Bias": 50, "ETF_Trend": 50},
    "whale_behavior_analyst": {"Dump_Probability": 50, "Sell_Pressure_Gauge": 50},
    "liquidity_order_flow": {"Slippage_Risk_Score": 50, "Order_Imbalance": 0.0},
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

    llm_config = resolve_llm_config(
        key_names=("DEEPSEEK_API_KEY", "OPENAI_API_KEY", "LLM_API_KEY"),
        base_url_names=("AIMM_LLM_BASE_URL", "OPENAI_BASE_URL"),
        model_names=("AIMM_LLM_MODEL", "OPENAI_MODEL"),
        default_base_url="https://api.deepseek.com/v1",
        default_model="deepseek-chat",
    )
    if not llm_config.api_key:
        raise ValueError(
            "agent_llm mode requires an LLM API key. "
            "Set DEEPSEEK_API_KEY, OPENAI_API_KEY, ATLASCLOUD_API_KEY, or ORCAROUTER_API_KEY."
        )
    _LLM_CLIENT = OpenAI(api_key=llm_config.api_key, base_url=llm_config.base_url)
    _LLM_MODEL = llm_config.model
    logger.info(
        "agent_llm client initialised (model=%s, base=%s)",
        _LLM_MODEL,
        llm_config.base_url,
    )


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
            avg_v = sum(vols) / len(vols)
            last_v = vols[-1]
            ratio = (last_v / avg_v) if avg_v else 0.0
            lines.append(f"Volume: last {last_v:.0f} vs avg {avg_v:.0f} ({ratio:.2f}x)")
    except (IndexError, TypeError, ValueError):
        pass
    return "\n".join(lines)


def _endpoint_data(endpoints: dict[str, Any], name: str) -> dict[str, Any] | None:
    row = endpoints.get(name)
    if not isinstance(row, dict) or not row.get("ok"):
        return None
    data = row.get("data")
    return data if isinstance(data, dict) else None


def _news_items_from_nexus(nexus: dict[str, Any]) -> list[dict[str, Any]]:
    raw = nexus.get("news")
    if isinstance(raw, list):
        return [n for n in raw if isinstance(n, dict)]
    endpoints = nexus.get("endpoints")
    if not isinstance(endpoints, dict):
        return []
    data = _endpoint_data(endpoints, "news")
    if not data:
        return []
    items = data.get("news")
    if isinstance(items, list):
        return [n for n in items if isinstance(n, dict)]
    return []


def _build_nexus_context(state: dict[str, Any]) -> str:
    """Extract Nexus bundle from shared_memory (live or historical endpoints)."""
    sm = state.get("shared_memory") or {}
    nexus = sm.get("nexus") or {}
    if not isinstance(nexus, dict):
        return ""
    parts: list[str] = []
    endpoints = nexus.get("endpoints") if isinstance(nexus.get("endpoints"), dict) else {}

    as_of = nexus.get("as_of_date")
    if as_of:
        parts.append(f"As-of date: {as_of} (offline historical; do not use later information)")

    mo = _endpoint_data(endpoints, "market_overview") if endpoints else None
    sent = _endpoint_data(endpoints, "sentiment") if endpoints else None
    fng = None
    fng_label = ""
    if isinstance(mo, dict):
        fng = mo.get("fear_greed_index")
        fng_label = str(mo.get("fear_greed_label") or "")
    if fng is None and isinstance(sent, dict):
        fng = sent.get("fear_greed")
        fng_label = str(sent.get("fear_greed_label") or "")
    if fng is not None:
        parts.append(f"Fear & Greed: {fng} {fng_label}".rstrip())

    if isinstance(mo, dict):
        macro_bits: list[str] = []
        if mo.get("vix") is not None:
            macro_bits.append(f"VIX {mo.get('vix')}")
        if mo.get("effective_fed_funds_pct") is not None:
            macro_bits.append(f"fed funds {mo.get('effective_fed_funds_pct')}%")
        if mo.get("us_10y_yield_pct") is not None:
            macro_bits.append(f"US10Y {mo.get('us_10y_yield_pct')}%")
        if mo.get("trade_weighted_usd_index") is not None:
            macro_bits.append(f"DXY {mo.get('trade_weighted_usd_index')}")
        if mo.get("stablecoin_change_7d_pct") is not None:
            macro_bits.append(f"stablecoin 7d {mo.get('stablecoin_change_7d_pct')}%")
        if mo.get("all_chain_tvl_change_7d_pct") is not None:
            macro_bits.append(f"TVL 7d {mo.get('all_chain_tvl_change_7d_pct')}%")
        if macro_bits:
            parts.append("Macro: " + ", ".join(macro_bits))

    for n in _news_items_from_nexus(nexus)[:5]:
        title = str(n.get("title") or "")[:120]
        sentiment = n.get("sentiment", "")
        if title:
            parts.append(f"  - [{sentiment}] {title}")

    funding = nexus.get("funding")
    if funding is None and endpoints:
        oi = _endpoint_data(endpoints, "oi_top_ranking")
        positions = None
        if isinstance(oi, dict):
            inner = oi.get("data") if isinstance(oi.get("data"), dict) else oi
            if isinstance(inner, dict):
                positions = inner.get("positions")
        if isinstance(positions, list) and positions and isinstance(positions[0], dict):
            funding = positions[0].get("funding_rate")
    if funding is not None:
        parts.append(f"Funding rate: {funding}")

    oi_val = nexus.get("open_interest") or nexus.get("oi")
    if oi_val is not None:
        parts.append(f"Open interest: {oi_val}")
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
        "- If Nexus Data includes Fear & Greed, funding, or headlines, treat them as "
        "as-of facts for this bar. Extreme fear (F&G ≤ 25) is a risk-off tilt; "
        "extreme greed (≥ 75) is a risk-on tilt. Do not ignore them for OHLCV alone.\n"
        "- Reply with a single JSON object only. No markdown fences, no preamble, "
        "no <think> blocks.\n"
        "- Required fields (use these types; fill every key):\n"
        f"{schema_json}\n"
        "- Every field is required. If you have no strong opinion, use the neutral default shown above.\n"
        '- Add a "reasoning" field (string, <= 400 chars) explaining your key signal adjustments.\n'
    )

    user = f"## Current Market Data\n{market_context}\n\nProduce your structured signal now."

    return system, user


def _parse_llm_json(text: str | None) -> dict[str, Any]:
    """Robust JSON extraction from LLM output."""
    parsed = parse_json_object(text or "")
    return parsed if parsed is not None else {}


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


def _chat_create(
    client: OpenAI,
    *,
    model_name: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
) -> Any:
    kwargs: dict[str, Any] = {
        "model": model_name,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "timeout": 45,
        "extra_body": {"thinking": {"type": "disabled"}},
    }
    try:
        return client.chat.completions.create(**kwargs)
    except Exception as exc:
        msg = str(exc).lower()
        unknown = "unknown" in msg or "unexpected" in msg or "not supported" in msg
        if unknown and ("thinking" in msg or "extra_body" in msg):
            kwargs.pop("extra_body", None)
            return client.chat.completions.create(**kwargs)
        raise


def _message_content(resp: Any) -> str:
    try:
        return resp.choices[0].message.content or ""
    except (AttributeError, IndexError, TypeError):
        return ""


def complete_json(
    *,
    cache_id: str,
    system: str,
    user: str,
    state: dict[str, Any],
    ticker: str | None = None,
    model: str | None = None,
    temperature: float = 0.1,
    max_tokens: int = 1024,
) -> dict[str, Any]:
    """Cached JSON completion with thinking disabled. Empty dict on failure."""
    try:
        client = _get_client()
    except ValueError as e:
        logger.warning("agent_llm: no API key for %s: %s", cache_id, e)
        return {}

    cache = _get_decision_cache()
    ticker_s = str(ticker or state.get("ticker") or "")
    prompt_hash = _prompt_hash(system + "\n" + user)
    date_tag = _date_tag_from_state(state)
    read_fn = cache.get("read")
    if read_fn:
        hit = read_fn(cache_id, ticker_s, date_tag, prompt_hash)
        if isinstance(hit, dict) and hit:
            logger.info("agent_llm: cache HIT for %s date=%s", cache_id, date_tag)
            out = dict(hit)
            out["cached"] = True
            return out

    model_name = model or get_default_model()
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    try:
        resp = _chat_create(
            client,
            model_name=model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except Exception as e:
        logger.warning("agent_llm: LLM call failed for %s: %s", cache_id, e)
        return {}

    text = _message_content(resp)
    obj = _parse_llm_json(text)
    if not obj:
        logger.warning(
            "agent_llm: unparseable output for %s, retrying once snippet=%r",
            cache_id,
            text[:240],
        )
        retry_msgs = [
            {"role": "system", "content": system + "\nReturn ONLY a JSON object. No markdown."},
            {"role": "user", "content": user},
        ]
        try:
            resp = _chat_create(
                client,
                model_name=model_name,
                messages=retry_msgs,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            text = _message_content(resp)
            obj = _parse_llm_json(text)
        except Exception as e:
            logger.warning("agent_llm: retry failed for %s: %s", cache_id, e)
            obj = {}
    if not obj:
        logger.warning("agent_llm: unparseable output for %s after retry", cache_id)
        return {}

    write_fn = cache.get("write")
    if write_fn:
        try:
            write_fn(cache_id, ticker_s, date_tag, prompt_hash, obj)
        except Exception as e:
            logger.debug("agent_llm: cache write failed: %s", e)
    return obj


def infer_agent(
    agent_id: str,
    state: dict[str, Any],
    *,
    deterministic_contract: dict[str, Any] | None = None,
    ticker: str | None = None,
    model: str | None = None,
    temperature: float = 0.1,
    max_tokens: int = 2048,
) -> dict[str, Any]:
    """Run a single agent's LLM inference.

    **No fallback to deterministic.** If the LLM call fails, an error
    contract with neutral values is returned (source: error).
    """
    try:
        _get_client()
    except ValueError as e:
        raise ValueError(
            f"agent_llm mode requires an LLM API key for agent {agent_id}. "
            "Set DEEPSEEK_API_KEY, OPENAI_API_KEY, or ATLASCLOUD_API_KEY."
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
    obj = complete_json(
        cache_id=agent_id,
        system=system,
        user=user,
        state=state,
        ticker=ticker,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    if not obj:
        return _error_contract(agent_id, "unparseable LLM response")

    cached = bool(obj.pop("cached", False))
    result = _fill_missing_fields(obj, agent_id)
    result["agent"] = agent_id
    result["agent_id"] = agent_id
    result["label"] = _AGENT_INFO.get(agent_id, {}).get("name", agent_id)
    result["source"] = "agent_llm"
    result["llm_enabled"] = True
    result["cached"] = cached
    return result


def infer_arbitrator_decision(
    math_brief: dict[str, Any],
    state: dict[str, Any],
    *,
    ticker: str | None = None,
) -> dict[str, Any]:
    """LLM overlay on the weighted math decision. Empty/invalid → source error."""
    system = (
        "You are the signal arbitrator for an agentic crypto hedge fund.\n"
        "Deterministic math already produced a composite, confidence, and gate result.\n"
        "You may confirm or override the trade decision.\n"
        'Return ONLY JSON: {"action": "BUY"|"SELL"|"HOLD", '
        '"stance": "bullish"|"bearish"|"neutral", '
        '"confidence": number 0-1, "reasons": [string, ...]}.'
    )
    user = json.dumps(
        {
            "ticker": ticker or state.get("ticker"),
            "math": math_brief,
            "desk_scores": _desk_score_brief(state),
        },
        default=str,
    )
    obj = complete_json(
        cache_id="signal_arbitrator",
        system=system,
        user=user,
        state=state,
        ticker=ticker,
        max_tokens=512,
    )
    action = str(obj.get("action") or "").upper()
    stance = str(obj.get("stance") or "").lower()
    if action not in ("BUY", "SELL", "HOLD"):
        return {"source": "error"}
    if stance not in ("bullish", "bearish", "neutral"):
        stance = {"BUY": "bullish", "SELL": "bearish"}.get(action, "neutral")
    try:
        conf = max(0.0, min(0.95, float(obj.get("confidence"))))
    except (TypeError, ValueError):
        conf = 0.5
    reasons = obj.get("reasons")
    if not isinstance(reasons, list):
        reasons = []
    return {
        "source": "agent_llm",
        "action": action,
        "stance": stance,
        "confidence": round(conf, 4),
        "reasons": [str(r) for r in reasons][:8],
        "cached": bool(obj.get("cached")),
    }


def _desk_score_brief(state: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for c in state.get("tier0_contracts") or []:
        if not isinstance(c, dict):
            continue
        aid = str(c.get("agent_id") or c.get("agent") or "")
        if not aid:
            continue
        rows.append(
            {
                "agent": aid,
                "composite": c.get("composite"),
                "stance": c.get("stance"),
                "confidence": c.get("confidence"),
            }
        )
    return rows[:12]


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
    "check_api_key",
    "complete_json",
    "get_default_model",
    "infer_agent",
    "infer_arbitrator_decision",
]
