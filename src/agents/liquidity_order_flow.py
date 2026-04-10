from __future__ import annotations

from typing import Any, Dict

from nexus_data.payload_extract import as_dict, first_float, quant_summary_core, unwrap_data


def _pair_blob(market_data: Any, ticker: str) -> dict[str, Any]:
    if not isinstance(market_data, dict):
        return {}
    blob = market_data.get(ticker)
    return blob if isinstance(blob, dict) else {}


def _coin_block(nexus_context: dict[str, Any] | None, ticker: str) -> dict[str, Any] | None:
    if not isinstance(nexus_context, dict):
        return None
    ps = nexus_context.get("per_symbol") or {}
    bys = ps.get("by_symbol") if isinstance(ps, dict) else None
    if not isinstance(bys, dict):
        return None
    sym_payload = bys.get(ticker)
    if not isinstance(sym_payload, dict):
        return None
    c = sym_payload.get("coin")
    return c if isinstance(c, dict) else None


def _quant_block(nexus_context: dict[str, Any] | None, ticker: str) -> dict[str, Any] | None:
    if not isinstance(nexus_context, dict):
        return None
    ps = nexus_context.get("per_symbol") or {}
    bys = ps.get("by_symbol") if isinstance(ps, dict) else None
    if not isinstance(bys, dict):
        return None
    sym_payload = bys.get(ticker)
    if not isinstance(sym_payload, dict):
        return None
    q = sym_payload.get("quant_summary")
    return q if isinstance(q, dict) else None


class LiquidityOrderFlowAgent:
    """Tier-0 AIMM: L2 depth + microstructure execution bounds."""

    name = "liquidity_order_flow"
    role = "market_microstructure_analyst"

    def analyze(
        self,
        *,
        ticker: str,
        market_data: Dict[str, Any],
        nexus_context: dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        blob = _pair_blob(market_data, ticker)
        depth = blob.get("nexus_depth") if isinstance(blob, dict) else None
        coin_b = _coin_block(nexus_context, ticker)
        coin_ok = bool(coin_b and coin_b.get("ok"))
        raw = coin_b.get("data") if coin_ok else None
        inner = as_dict(unwrap_data(raw) if isinstance(raw, dict) else raw)
        netflow = inner.get("netflow") or inner.get("netFlow")

        qb = _quant_block(nexus_context, ticker)
        q_ok = bool(qb and qb.get("ok"))
        qraw = qb.get("data") if q_ok else None
        qd = quant_summary_core(as_dict(qraw) if isinstance(qraw, dict) else {})

        imbalance = first_float(
            qd,
            "order_imbalance",
            "Order_Imbalance",
            "taker_buy_sell_imbalance",
            "buy_sell_imbalance",
        )
        poc = qd.get("poc_price") or qd.get("POC_Price") or qd.get("point_of_control")
        if poc is None and isinstance(qd.get("vpvr"), dict):
            poc = qd["vpvr"].get("poc") or qd["vpvr"].get("POC")

        slip_10 = first_float(
            qd,
            "slippage_10_bps_capacity_usdt",
            "slippage_10_bps",
            "safe_10_bps",
        )
        slip_25 = first_float(qd, "slippage_25_bps_capacity_usdt", "slippage_25_bps")
        slip_50 = first_float(qd, "slippage_50_bps_capacity_usdt", "slippage_50_bps")

        # Without quant/depth, do not assume extreme execution risk (avoids systematic
        # bearish skew in offline backtests when Nexus is disabled).
        slip_risk = 55
        if q_ok and qd:
            slip_risk = int(
                max(10.0, min(100.0, 100.0 - min(slip_10, slip_25, slip_50 or 1e12) / 1e6))
            )
        has_depth = bool(depth) and not (isinstance(depth, dict) and depth.get("status") == "error")
        if has_depth:
            slip_risk = min(slip_risk, 55)

        status = "success" if (has_depth or coin_ok or q_ok) else "skipped"
        return {
            "status": status,
            "magnet_price": qd.get("magnet_price") if isinstance(qd, dict) else None,
            "slippage_bounds_bps": {
                "10": slip_10 if slip_10 else None,
                "25": slip_25 if slip_25 else None,
                "50": slip_50 if slip_50 else None,
            },
            "nexus_depth_attached": has_depth,
            "nexus_coin_netflow": netflow,
            "order_imbalance": imbalance if imbalance != 0.0 else None,
            "poc_price": float(poc) if isinstance(poc, (int, float)) else poc,
            "slippage_risk_score": slip_risk,
            "note": "Depth via NexusAdapter; coin + /market/quant-summary when present.",
        }
