from __future__ import annotations

from typing import Any, Dict

from nexus_data.payload_extract import as_dict, coin_inner_payload, first_float
from nexus_data.symbols import base_asset, ccxt_to_nexus_pair_id


def _ep(nexus_context: dict[str, Any] | None, name: str) -> dict[str, Any]:
    if not isinstance(nexus_context, dict):
        return {}
    eps = nexus_context.get("endpoints") or {}
    block = eps.get(name)
    return block if isinstance(block, dict) else {}


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


class WhaleBehaviorAnalystAgent:
    """Tier-0 AIMM: on-chain whale behavior and supply-shock risk."""

    name = "whale_behavior_analyst"
    role = "onchain_defense_sentinel"

    def analyze(
        self,
        *,
        ticker: str,
        market_data: Dict[str, Any],
        nexus_context: dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        div = _ep(nexus_context, "divergences")
        coin_b = _coin_block(nexus_context, ticker)
        coin_ok = bool(coin_b and coin_b.get("ok"))
        raw_coin = coin_b.get("data") if coin_ok else None
        inner = coin_inner_payload(as_dict(raw_coin)) if isinstance(raw_coin, dict) else {}
        telem = inner.get("raw_telemetry")
        if not isinstance(telem, dict):
            telem = inner.get("telemetry") if isinstance(inner.get("telemetry"), dict) else {}

        b = base_asset(ticker)
        nid = ccxt_to_nexus_pair_id(ticker)
        div_hits = 0
        if div.get("ok"):
            d = div.get("data")
            rows = d.get("data") if isinstance(d, dict) else d
            if isinstance(rows, list):
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    sym = str(
                        row.get("symbol")
                        or row.get("pair")
                        or row.get("ticker")
                        or row.get("asset")
                        or ""
                    ).upper()
                    if b in sym or nid in sym or sym.endswith(b):
                        div_hits += 1

        oi_d = inner.get("oi_delta_percent") or inner.get("oiDeltaPercent")
        price_d = inner.get("price_delta_percent") or inner.get("priceDeltaPercent")

        pump = first_float(telem, "pump_probability", "Pump_Probability", default=0.0)
        dump = first_float(telem, "dump_probability", "Dump_Probability", default=0.0)
        if pump == 0.0 and dump == 0.0:
            try:
                if isinstance(oi_d, (int, float)) and float(oi_d) > 8:
                    pump = min(1.0, float(oi_d) / 50.0)
                if isinstance(oi_d, (int, float)) and float(oi_d) < -8:
                    dump = min(1.0, abs(float(oi_d)) / 50.0)
            except (TypeError, ValueError):
                pass

        inflow = first_float(telem, "total_inflow_usd", "totalInflowUsd")
        outflow = first_float(telem, "total_outflow_usd", "totalOutflowUsd")
        if inflow > outflow * 1.25:
            dump = max(dump, 0.35)
        if outflow > inflow * 1.25:
            pump = max(pump, 0.35)

        impact = first_float(
            telem,
            "predicted_price_impact_pct",
            "Predicted_Price_Impact_Pct",
            default=0.0,
        )
        if impact == 0.0 and isinstance(price_d, (int, float)):
            impact = float(price_d)

        dry = str(telem.get("dry_powder_alert") or telem.get("Dry_Powder_Alert") or "").lower()
        if not dry:
            dry_usdt = first_float(telem, "current_exchange_usdt_balance", "exchange_usdt_balance")
            dry = "high" if dry_usdt > 1e8 else "low" if dry_usdt > 0 else ""

        if not coin_ok and div_hits == 0 and not telem:
            return {
                "status": "skipped",
                "pump_probability": 0.0,
                "dump_probability": 0.0,
                "predicted_price_impact_pct": 0.0,
                "net_whale_bias": "neutral",
                "dry_powder_alert": "unknown",
                "note": "No per-symbol coin, telemetry, or divergence hits in Nexus bundle.",
            }

        net_bias = str(telem.get("net_whale_bias") or telem.get("Net_Whale_Bias") or "").lower()
        if not net_bias:
            bias = (
                "long_liquidity" if pump > dump else "short_liquidity" if dump > pump else "neutral"
            )
        else:
            bias = (
                "bullish_accumulation"
                if "bull" in net_bias
                else "bearish_distribution"
                if "bear" in net_bias
                else net_bias
            )

        dpa = "elevated"
        if dry in ("high", "deep"):
            dpa = "high"
        elif dry in ("low", "thin"):
            dpa = "low"
        elif div_hits >= 2:
            dpa = "elevated"
        else:
            dpa = "normal"

        return {
            "status": "success",
            "pump_probability": round(pump, 3),
            "dump_probability": round(dump, 3),
            "predicted_price_impact_pct": round(impact, 4),
            "net_whale_bias": bias,
            "dry_powder_alert": dpa,
            "raw_telemetry": telem if telem else None,
            "inputs": {"divergence_hits": div_hits},
        }
