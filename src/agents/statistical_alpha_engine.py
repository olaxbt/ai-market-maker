from __future__ import annotations

from typing import Any, Dict

from nexus_data.payload_extract import as_dict, first_float
from nexus_data.symbols import ccxt_to_nexus_pair_id


def _oi_positions(nexus_context: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(nexus_context, dict):
        return []
    eps = nexus_context.get("endpoints") or {}
    blk = eps.get("oi_top_ranking")
    if not isinstance(blk, dict) or not blk.get("ok"):
        return []
    resp = blk.get("data")
    if not isinstance(resp, dict):
        return []
    bucket = resp.get("data")
    if not isinstance(bucket, dict):
        return []
    pos = bucket.get("positions")
    return [p for p in pos if isinstance(p, dict)] if isinstance(pos, list) else []


class StatisticalAlphaEngineAgent:
    """Tier-0 AIMM: cross-sectional alpha + factor engine (OI ranks vs universe)."""

    name = "statistical_alpha_engine"
    role = "multi_factor_actuary"

    def analyze(
        self,
        *,
        ticker: str,
        market_data: Dict[str, Any],
        nexus_context: dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        nid = ccxt_to_nexus_pair_id(ticker)
        positions = _oi_positions(nexus_context)
        if not positions:
            return {
                "status": "skipped",
                "universe": [],
                "cross_sectional_rank": None,
                "alpha_signal": "hold",
                "note": "No OI top-ranking data in Nexus bundle.",
            }

        rank_map: dict[str, int] = {}
        score_map: dict[str, float] = {}
        funding_map: dict[str, float] = {}
        oi_z_map: dict[str, float] = {}

        for row in positions:
            sym = row.get("symbol")
            rk = row.get("rank")
            sc = row.get("score")
            if isinstance(sym, str):
                if isinstance(rk, int):
                    rank_map[sym] = rk
                elif isinstance(rk, float):
                    rank_map[sym] = int(rk)
                score_map[sym] = first_float(
                    as_dict(row), "score", "oi_score", default=float(sc or 0)
                )
                funding_map[sym] = first_float(
                    as_dict(row),
                    "funding_premium_z",
                    "funding_rate_z",
                    "funding_z_score",
                )
                oi_z_map[sym] = first_float(
                    as_dict(row),
                    "oi_flow_z",
                    "oi_z_score",
                    "oi_delta_z",
                )

        my_rank = rank_map.get(nid)
        row = next((p for p in positions if p.get("symbol") == nid), None)
        rdict = as_dict(row)
        pct = rdict.get("oi_delta_percent") or rdict.get("oiDeltaPercent")
        try:
            pct_f = float(pct) if pct is not None else None
        except (TypeError, ValueError):
            pct_f = None

        cs_z = oi_z_map.get(nid) or funding_map.get(nid)
        alpha = "hold"
        if my_rank is not None:
            if my_rank <= 5 and pct_f is not None and pct_f > 5:
                alpha = "long_bias"
            elif my_rank <= 5 and pct_f is not None and pct_f < -5:
                alpha = "short_bias"
            elif cs_z is not None and cs_z > 1.0 and (pct_f or 0) > 0:
                alpha = "long_bias"
            elif cs_z is not None and cs_z < -1.0:
                alpha = "short_bias"

        factor_hints = {
            "funding_premium_z": funding_map.get(nid),
            "oi_flow_z": oi_z_map.get(nid),
        }

        return {
            "status": "success",
            "universe": list(rank_map.keys())[:20],
            "cross_sectional_rank": my_rank,
            "cross_sectional_z_score": round(cs_z, 3) if cs_z is not None else None,
            "alpha_signal": alpha,
            "inputs": {
                "oi_score": score_map.get(nid),
                "oi_delta_percent": pct_f,
                "factor_hints": factor_hints,
            },
        }
