from __future__ import annotations

from typing import Any, Dict

from nexus_data.payload_extract import as_dict, first_float, unwrap_data


def _ep(nexus_context: dict[str, Any] | None, name: str) -> dict[str, Any]:
    if not isinstance(nexus_context, dict):
        return {}
    eps = nexus_context.get("endpoints") or {}
    block = eps.get(name)
    return block if isinstance(block, dict) else {}


def _news_items(nexus_context: dict[str, Any] | None) -> list[dict[str, Any]]:
    blk = _ep(nexus_context, "news")
    if not blk.get("ok"):
        return []
    raw = blk.get("data")
    if not isinstance(raw, dict):
        return []
    items = raw.get("news")
    return [x for x in items if isinstance(x, dict)] if isinstance(items, list) else []


class NewsNarrativeMinerAgent:
    """Tier-0 AIMM: event-driven systemic shock detector (circuit breaker input)."""

    name = "news_narrative_miner"
    role = "event_driven_analyst"

    def analyze(
        self,
        *,
        ticker: str,
        market_data: Dict[str, Any],
        nexus_context: dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        base = ticker.split("/")[0].upper() if "/" in ticker else ticker.upper()
        items = _news_items(nexus_context)
        na = _ep(nexus_context, "news_analytics_sentiment")
        agg_breaker = 0.0
        decay_factor = None
        if na.get("ok"):
            nad = as_dict(unwrap_data(na.get("data")))
            agg_breaker = first_float(
                nad,
                "News_Impact_Score",
                "news_impact_score",
                "impact_score",
                "systemic_shock_score",
            )
            decay_factor = nad.get("decay_factor")
            if decay_factor is None:
                decay_factor = (
                    first_float(nad, "decayFactor", "half_life_hours", default=0.0) or None
                )

        if not items and agg_breaker <= 0:
            return {
                "status": "skipped",
                "breaker_score": 0.0,
                "breaker_state": "inactive",
                "filtered_catalyst_log": [],
                "decay_factor": decay_factor,
                "note": "No Nexus news payload (disabled, auth, or endpoint error).",
            }

        hits: list[dict[str, Any]] = []
        stress = ("hack", "sec", "lawsuit", "ban", "default", "collapse", "halt", "exploit")
        api_impact_sum = 0.0
        api_decay_vals: list[float] = []

        for row in items[:40]:
            title = str(row.get("title") or row.get("headline") or "")
            imp = first_float(
                as_dict(row),
                "impact_score",
                "Impact_Score",
                "importance",
                "severity",
            )
            if imp > 0:
                api_impact_sum += imp
            df = row.get("decay_factor")
            if df is not None:
                try:
                    api_decay_vals.append(float(df))
                except (TypeError, ValueError):
                    pass
            if base.lower() in title.lower() or any(
                k in title.lower() for k in ("crypto", "bitcoin", "ethereum", "market")
            ):
                hits.append(
                    {
                        "title": title[:200],
                        "source": row.get("source"),
                        "impact_score": imp or None,
                    }
                )

        neg = sum(1 for h in hits for k in stress if k in h.get("title", "").lower())
        heuristic = min(100.0, float(neg * 15 + min(len(hits), 10) * 2))
        breaker = max(agg_breaker, heuristic, min(100.0, api_impact_sum / max(1, len(items)) * 2))
        if agg_breaker > 0:
            breaker = max(breaker, agg_breaker)

        if decay_factor is None and api_decay_vals:
            decay_factor = sum(api_decay_vals) / len(api_decay_vals)
        state = "active" if breaker >= 35 else "watch" if breaker >= 15 else "inactive"
        return {
            "status": "success",
            "breaker_score": breaker,
            "breaker_state": state,
            "filtered_catalyst_log": hits[:12],
            "decay_factor": decay_factor,
            "inputs": {"news_rows_considered": len(items), "symbol_focus": base},
        }
