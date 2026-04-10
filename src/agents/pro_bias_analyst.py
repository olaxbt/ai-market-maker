from __future__ import annotations

from typing import Any, Dict

from nexus_data.payload_extract import as_dict, first_float, unwrap_data
from nexus_data.symbols import ccxt_to_nexus_pair_id


def _ep(nexus_context: dict[str, Any] | None, name: str) -> dict[str, Any]:
    if not isinstance(nexus_context, dict):
        return {}
    eps = nexus_context.get("endpoints") or {}
    block = eps.get(name)
    return block if isinstance(block, dict) else {}


def _token_match(nexus_context: dict[str, Any] | None, ticker: str) -> dict[str, Any] | None:
    blk = _ep(nexus_context, "smart_money_tokens")
    if not blk.get("ok"):
        return None
    raw = blk.get("data")
    if not isinstance(raw, dict):
        return None
    items = raw.get("data") or raw.get("tokens") or raw.get("list") or raw.get("items")
    if not isinstance(items, list):
        return None
    nid = ccxt_to_nexus_pair_id(ticker)
    base = ticker.split("/")[0].upper() if "/" in ticker else ticker.upper()
    for row in items:
        if not isinstance(row, dict):
            continue
        sym = str(row.get("symbol") or row.get("ticker") or row.get("name") or "").upper()
        if nid in sym or base in sym or sym.endswith(base):
            return row
    return None


class ProBiasAnalystAgent:
    """Tier-0 AIMM: institutional / smart-money flow confirmation."""

    name = "pro_bias_analyst"
    role = "smart_money_flow_tracker"

    def analyze(
        self,
        *,
        ticker: str,
        market_data: Dict[str, Any],
        nexus_context: dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        tok = _token_match(nexus_context, ticker)
        etf = _ep(nexus_context, "etf_metrics")
        if tok is None and not etf.get("ok"):
            return {
                "status": "skipped",
                "pro_bias_score": 50.0,
                "regime": "passive_rotation",
                "tradfi_etf_metrics": None,
                "native_smart_money_metrics": None,
                "note": "No smart-money token row or ETF metrics in Nexus bundle.",
            }

        score = 50.0
        ema_slope = None
        if isinstance(tok, dict):
            for k in (
                "score",
                "bias",
                "smartMoneyScore",
                "nexusScore",
                "pro_bias_score",
                "Pro_Bias",
            ):
                v = tok.get(k)
                if isinstance(v, (int, float)):
                    score = float(v)
                    break
            delta = first_float(
                tok,
                "top_trader_net_delta_pct",
                "topTraderNetDeltaPct",
                "net_delta_pct",
                "long_short_bias",
            )
            if delta != 0.0:
                score = min(100.0, max(0.0, 50.0 + delta * 0.5))
            ema_slope = tok.get("ema_slope")
            if ema_slope is None:
                ema_slope = first_float(tok, "velocity", "acceleration", default=0.0) or None
            score = min(100.0, max(0.0, score))

        etf_payload = etf.get("data") if etf.get("ok") else None
        etf_d = as_dict(unwrap_data(etf_payload) if isinstance(etf_payload, dict) else etf_payload)
        nav_prem = first_float(etf_d, "nav_premium_pct", "navPremiumPct", "premium_pct")
        flow_vel = first_float(etf_d, "net_flow_velocity", "velocity", "etf_flow_velocity")

        if score <= 40 or flow_vel < 0:
            regime = "distribution"
        elif score >= 60 or flow_vel > 0 or nav_prem > 0:
            regime = "accumulation"
        else:
            regime = "passive_rotation"

        return {
            "status": "success",
            "pro_bias_score": score,
            "regime": regime,
            "ema_slope": ema_slope
            if ema_slope is not None
            else (round(flow_vel, 4) if flow_vel else None),
            "tradfi_etf_metrics": etf_payload if isinstance(etf_payload, dict) else etf_d or None,
            "native_smart_money_metrics": tok,
        }
