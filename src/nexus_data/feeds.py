"""Batch Nexus Skills API fetches for market_scan and Tier-0 agents.

Failures are isolated per endpoint so production runs degrade gracefully.
"""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from nexus_data.client import NexusDataClient
from nexus_data.symbols import base_asset, ccxt_to_nexus_pair_id, nexus_pair_id_to_ccxt


def nexus_credentials_configured() -> bool:
    return bool(
        (os.getenv("NEXUS_API_KEY") or "").strip() or (os.getenv("NEXUS_JWT") or "").strip()
    )


def nexus_feeds_enabled() -> bool:
    if (os.getenv("NEXUS_DISABLE") or "").lower() in ("1", "true", "yes"):
        return False
    return nexus_credentials_configured()


def _oi_timeout_s() -> float:
    return float(os.getenv("NEXUS_OI_TIMEOUT_S") or "90")


def _safe_get(
    client: NexusDataClient,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    timeout_s: float | None = None,
) -> dict[str, Any]:
    try:
        return {"ok": True, "data": client.get(path, params=params, timeout_s=timeout_s)}
    except Exception as e:
        return {"ok": False, "error": str(e), "data": None}


def fetch_nexus_global_bundle(client: NexusDataClient) -> dict[str, Any]:
    """Parallel global feeds (no per-symbol coin calls)."""
    oi_limit = max(15, int(os.getenv("NEXUS_OI_TOP_LIMIT") or "40"))
    duration = (os.getenv("NEXUS_OI_DURATION") or "24h").strip() or "24h"
    rank_by = (os.getenv("NEXUS_OI_RANK_BY") or "score").strip().lower()
    if rank_by not in ("score", "value"):
        rank_by = "score"

    news_hours = int(os.getenv("NEXUS_NEWS_ANALYTICS_HOURS") or "24")
    tasks: dict[str, tuple[str, dict[str, Any] | None, float | None]] = {
        "oi_top_ranking": (
            "/oi/top-ranking",
            {"limit": oi_limit, "duration": duration, "rankBy": rank_by},
            _oi_timeout_s(),
        ),
        "news": ("/news", {"limit": int(os.getenv("NEXUS_NEWS_LIMIT") or "25")}, None),
        "news_analytics_sentiment": (
            "/news/analytics/sentiment",
            {"hours": news_hours},
            None,
        ),
        "sentiment": ("/sentiment", None, None),
        "sentiment_trends": ("/sentiment/trends", None, None),
        "divergences": ("/divergences", None, None),
        "smart_money_tokens": (
            "/smart-money/tokens",
            {"page": 1, "pageSize": min(50, max(10, oi_limit))},
            None,
        ),
        "market_overview": ("/market/overview", None, None),
        "kol_heatmap": ("/kol/analytics/symbols/heatmap", {"days": 3}, None),
        "etf_metrics": ("/etf/metrics", None, None),
    }

    out: dict[str, Any] = {
        "fetched_at_epoch": time.time(),
        "integration_contract_version": "2026-04-04",
        "endpoints": {},
        "errors": [],
    }

    def _run(name: str) -> tuple[str, dict[str, Any]]:
        path, params, to = tasks[name]
        return name, _safe_get(client, path, params=params, timeout_s=to)

    with ThreadPoolExecutor(max_workers=12) as ex:
        futures = {ex.submit(_run, name): name for name in tasks}
        for fut in as_completed(futures):
            name, result = fut.result()
            out["endpoints"][name] = result
            if not result.get("ok"):
                err = result.get("error") or "unknown"
                out["errors"].append(f"{name}: {err}")

    return out


def oi_ccxt_candidates(bundle: dict[str, Any]) -> list[str]:
    """Extract ccxt symbols from OI top-ranking response."""
    ep = bundle.get("endpoints") or {}
    block = ep.get("oi_top_ranking") or {}
    if not block.get("ok"):
        return []
    resp = block.get("data")
    if not isinstance(resp, dict):
        return []
    bucket = resp.get("data")
    if not isinstance(bucket, dict):
        return []
    positions = bucket.get("positions")
    if not isinstance(positions, list):
        return []
    out: list[str] = []
    for row in positions:
        if not isinstance(row, dict):
            continue
        sym = row.get("symbol")
        if not isinstance(sym, str):
            continue
        ccxt_sym = nexus_pair_id_to_ccxt(sym)
        if ccxt_sym:
            out.append(ccxt_sym)
    return out


def fetch_nexus_per_symbol(
    client: NexusDataClient,
    universe: list[str],
    *,
    max_workers: int = 4,
) -> dict[str, Any]:
    """Coin + technical analysis cache per symbol (bounded parallelism)."""
    max_sym = max(1, int(os.getenv("NEXUS_PER_SYMBOL_MAX") or "8"))
    symbols = [s for s in universe if isinstance(s, str)][:max_sym]

    interval = (os.getenv("NEXUS_QUANT_SUMMARY_INTERVAL") or "1h").strip() or "1h"
    qlimit = int(os.getenv("NEXUS_QUANT_SUMMARY_LIMIT") or "48")

    def one(sym: str) -> tuple[str, dict[str, Any]]:
        nid = ccxt_to_nexus_pair_id(sym)
        base = base_asset(sym)
        coin = _safe_get(client, f"/coin/{nid}", params=None, timeout_s=45.0)
        tech = _safe_get(
            client,
            f"/technical-indicators/analysis/{base}",
            params=None,
            timeout_s=45.0,
        )
        quant = _safe_get(
            client,
            "/market/quant-summary",
            params={"symbol": nid, "interval": interval, "limit": qlimit},
            timeout_s=45.0,
        )
        return sym, {"coin": coin, "technical_analysis": tech, "quant_summary": quant}

    out: dict[str, Any] = {"by_symbol": {}, "errors": []}
    if not symbols:
        return out

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(one, s): s for s in symbols}
        for fut in as_completed(futs):
            sym = futs[fut]
            try:
                k, payload = fut.result()
                out["by_symbol"][k] = payload
                for part in ("coin", "technical_analysis", "quant_summary"):
                    block = payload.get(part) or {}
                    if not block.get("ok"):
                        err = block.get("error") or "unknown"
                        out["errors"].append(f"{k}.{part}: {err}")
            except Exception as e:
                out["errors"].append(f"{sym}: {e}")

    return out


def merge_bundle_with_per_symbol(
    global_bundle: dict[str, Any], per: dict[str, Any]
) -> dict[str, Any]:
    merged = dict(global_bundle)
    merged["per_symbol"] = per
    merged["errors"] = list(merged.get("errors") or []) + list(per.get("errors") or [])
    return merged
