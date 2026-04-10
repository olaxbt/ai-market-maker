from __future__ import annotations

from typing import Any, Dict

from nexus_data.payload_extract import as_dict, first_float, heatmap_row_for_ticker, unwrap_data
from nexus_data.symbols import base_asset, ccxt_to_nexus_pair_id


def _ep(nexus_context: dict[str, Any] | None, name: str) -> dict[str, Any]:
    if not isinstance(nexus_context, dict):
        return {}
    eps = nexus_context.get("endpoints") or {}
    block = eps.get(name)
    return block if isinstance(block, dict) else {}


class RetailHypeTrackerAgent:
    """Tier-0 AIMM: retail FOMO/panic + hype-price divergence."""

    name = "retail_hype_tracker"
    role = "behavioral_psychologist"

    def analyze(
        self,
        *,
        ticker: str,
        market_data: Dict[str, Any],
        nexus_context: dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        b = base_asset(ticker)
        nid = ccxt_to_nexus_pair_id(ticker)
        sent = _ep(nexus_context, "sentiment")
        st = _ep(nexus_context, "sentiment_trends")
        heat_blk = _ep(nexus_context, "kol_heatmap")
        heat_raw = heat_blk.get("data") if heat_blk.get("ok") else {}
        row = (
            heatmap_row_for_ticker(as_dict(heat_raw), ticker, b, nid)
            if isinstance(heat_raw, dict)
            else None
        )

        mention_z = 0.0
        mention_count = 0
        bullish_ratio = 0.0
        price_momentum = 0.0
        if isinstance(row, dict):
            mention_count = int(
                first_float(row, "mention_count", "mentions", "mentionCount", default=0.0)
            )
            mention_z = first_float(
                row,
                "mention_z_score",
                "mentions_z_score",
                "z_score",
                "zScore",
            )
            bullish_ratio = first_float(row, "bullish_ratio", "bullishRatio", default=0.0)
            price_momentum = first_float(
                row, "price_momentum", "priceMomentum", "momentum", default=0.0
            )

        heat_proxy = (
            first_float(as_dict(row), "score", "heat", "mentions", default=0.0) if row else 0.0
        )

        z = mention_z
        raw = sent.get("data") if sent.get("ok") else {}
        if isinstance(raw, dict) and z == 0.0:
            v = raw.get("zScore") or raw.get("score") or raw.get("sentiment")
            if isinstance(v, (int, float)):
                z = float(v)
            elif isinstance(v, dict):
                z = float(v.get("score") or v.get("value") or 0.0)

        if st.get("ok"):
            std = unwrap_data(st.get("data"))
            if isinstance(std, dict):
                per = std.get(b) or std.get(nid) or std.get("data") or std
                if isinstance(per, dict):
                    z = z or first_float(per, "z_score", "zScore", "sentiment_z_score")

        if not sent.get("ok") and not st.get("ok") and heat_proxy <= 0 and mention_count == 0:
            return {
                "status": "skipped",
                "fomo_level": 50,
                "divergence_warning": False,
                "sentiment_z_score": 0.0,
                "note": "No Nexus sentiment / trends / KOL heatmap in bundle.",
            }

        # AIMM 5.md: divergence if mentions Z > 3 and price momentum < 0
        div = (mention_z > 3.0 and price_momentum < 0) or abs(z) > 1.5 or heat_proxy > 40
        fomo = int(
            min(
                100,
                max(
                    0,
                    50
                    + z * 8
                    + mention_z * 5
                    + min(heat_proxy, 40.0)
                    + (bullish_ratio * 20 if bullish_ratio else 0.0),
                ),
            )
        )

        return {
            "status": "success",
            "fomo_level": fomo,
            "divergence_warning": div,
            "sentiment_z_score": round(z, 2),
            "inputs": {
                "mention_count": mention_count,
                "bullish_ratio": bullish_ratio,
                "price_momentum": price_momentum,
                "mention_z_score": round(mention_z, 2),
                "kol_heat_proxy": heat_proxy,
            },
        }
