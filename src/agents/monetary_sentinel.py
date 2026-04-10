from __future__ import annotations

from typing import Any, Dict

from nexus_data.payload_extract import as_dict, first_float, unwrap_data


def _ohlcv_len(market_data: Any, ticker: str) -> int:
    if not isinstance(market_data, dict):
        return 0
    blob = market_data.get(ticker)
    if not isinstance(blob, dict):
        return 0
    ohlcv = blob.get("ohlcv")
    return len(ohlcv) if isinstance(ohlcv, list) else 0


def _ep(nexus_context: dict[str, Any] | None, name: str) -> dict[str, Any]:
    if not isinstance(nexus_context, dict):
        return {}
    eps = nexus_context.get("endpoints") or {}
    block = eps.get(name)
    return block if isinstance(block, dict) else {}


class MonetarySentinelAgent:
    """Tier-0 AIMM: macro liquidity / systemic beta sentinel."""

    name = "monetary_sentinel"
    role = "macro_economist"

    def analyze(
        self,
        *,
        ticker: str,
        market_data: Dict[str, Any],
        nexus_context: dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        n = _ohlcv_len(market_data, ticker)
        score = 50.0
        if n >= 30:
            score = 60.0
        regime = "neutral"
        mo = _ep(nexus_context, "market_overview")
        nexus_ok = bool(mo.get("ok"))
        raw = mo.get("data") if nexus_ok else None
        overview = as_dict(unwrap_data(raw) if isinstance(raw, dict) else raw)
        # OpenAPI-aligned names first; fallbacks for older payloads.
        if overview:
            fg = first_float(
                overview,
                "systemic_liquidity_score",
                "liquidity_score",
                "fear_greed_index",
                "fearGreedIndex",
                "crypto_fear_greed",
            )
            if fg > 0:
                score = min(95.0, max(score, fg))
                if overview.get("risk_on") is True:
                    regime = "risk_on"
                elif overview.get("risk_off") is True:
                    regime = "risk_off"
                elif score >= 65:
                    regime = "risk_on"
            elif overview.get("risk_on") is True:
                score = min(95.0, score + 15.0)
                regime = "risk_on"
            elif overview.get("risk_off") is True:
                score = max(15.0, score - 15.0)
                regime = "risk_off"
            else:
                score = min(95.0, score + 10.0)
                regime = "risk_on" if score >= 65 else "neutral"
        elif isinstance(raw, dict) and raw.get("success") is not False:
            score = min(95.0, score + 10.0)
            regime = "risk_on" if score >= 65 else "neutral"

        return {
            "status": "success",
            "systemic_beta_score": score,
            "liquidity_regime": regime,
            "inputs": {
                "ohlcv_candles": n,
                "nexus_market_overview": nexus_ok,
                "nexus_overview_keys_sample": list(overview.keys())[:12] if overview else [],
            },
        }
