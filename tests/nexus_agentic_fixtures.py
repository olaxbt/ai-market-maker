"""Deterministic Nexus bundle shapes for agentic workflow tests (no HTTP)."""

from __future__ import annotations

from typing import Any


def ohlcv_window_btc(*, bars: int = 96) -> list[list[float]]:
    """Rising close so momentum / pattern agents have signal."""
    out: list[list[float]] = []
    for i in range(bars):
        t = float(i * 3_600_000)
        c = 100.0 + i * 0.15
        out.append([t, c - 0.5, c + 0.3, c - 0.8, c, 1.0])
    return out


def nexus_bundle_bullish_btc() -> dict[str, Any]:
    """Rich enough for Tier-0 perception agents (incl. 2.3 TA) to return ``success``."""
    return {
        "fetched_at_epoch": 0.0,
        "integration_contract_version": "test-fixture",
        "endpoints": {
            "oi_top_ranking": {
                "ok": True,
                "data": {
                    "success": True,
                    "data": {
                        "positions": [
                            {
                                "symbol": "BTCUSDT",
                                "rank": 2,
                                "score": 88.0,
                                "oi_delta_percent": 12.0,
                                "oi_flow_z": 1.2,
                            }
                        ]
                    },
                },
            },
            "news": {
                "ok": True,
                "data": {
                    "success": True,
                    "news": [
                        {
                            "title": "Bitcoin steady as crypto markets trade higher",
                            "impact_score": 15,
                        }
                    ],
                },
            },
            "news_analytics_sentiment": {
                "ok": True,
                "data": {"success": True, "data": {"news_impact_score": 22, "decay_factor": 0.9}},
            },
            "sentiment": {"ok": True, "data": {"success": True, "zScore": 1.1}},
            "sentiment_trends": {"ok": True, "data": {"success": True, "data": {}}},
            "divergences": {"ok": True, "data": {"success": True, "data": []}},
            "smart_money_tokens": {
                "ok": True,
                "data": {"success": True, "items": [{"symbol": "BTCUSDT", "score": 68}]},
            },
            "market_overview": {
                "ok": True,
                "data": {
                    "success": True,
                    "data": {"systemic_liquidity_score": 78, "risk_on": True},
                },
            },
            "kol_heatmap": {
                "ok": True,
                "data": {
                    "success": True,
                    "data": [
                        {
                            "symbol": "BTCUSDT",
                            "mention_count": 120,
                            "bullish_ratio": 0.62,
                            "price_momentum": 0.02,
                            "mention_z_score": 1.1,
                        }
                    ],
                },
            },
            "etf_metrics": {
                "ok": True,
                "data": {
                    "success": True,
                    "data": {"nav_premium_pct": 0.05, "net_flow_velocity": 0.02},
                },
            },
        },
        "per_symbol": {
            "by_symbol": {
                "BTC/USDT": {
                    "coin": {
                        "ok": True,
                        "data": {
                            "success": True,
                            "data": {
                                "oi_delta_percent": 6.0,
                                "price_delta_percent": 0.8,
                                "raw_telemetry": {
                                    "pump_probability": 0.35,
                                    "dump_probability": 0.15,
                                    "predicted_price_impact_pct": 0.4,
                                },
                            },
                        },
                    },
                    "technical_analysis": {
                        "ok": True,
                        "data": {
                            "success": True,
                            "analysis": {
                                "mood": "bullish",
                                "pattern": "Ascending Triangle",
                                "setup_confidence_score": 78.0,
                                "kalman_support": 99_500.0,
                            },
                        },
                    },
                    "quant_summary": {
                        "ok": True,
                        "data": {
                            "success": True,
                            "order_imbalance": 0.15,
                            "slippage_10_bps_capacity_usdt": 8_000_000.0,
                            "poc_price": 100_250.0,
                        },
                    },
                }
            }
        },
    }


def nexus_bundle_risk_off_btc() -> dict[str, Any]:
    """Macro + news shock + high dump probability → bear tilt."""
    b = nexus_bundle_bullish_btc()
    mo = b["endpoints"]["market_overview"]["data"]["data"]
    mo["risk_on"] = False
    mo["risk_off"] = True
    mo["systemic_liquidity_score"] = 25.0
    b["endpoints"]["news_analytics_sentiment"] = {
        "ok": True,
        "data": {"success": True, "data": {"news_impact_score": 88}},
    }
    b["endpoints"]["news"]["data"]["news"] = [
        {"title": "Major exchange outage reported", "impact_score": 90}
    ]
    pos = b["endpoints"]["oi_top_ranking"]["data"]["data"]["positions"][0]
    pos["oi_delta_percent"] = -15.0
    coin = b["per_symbol"]["by_symbol"]["BTC/USDT"]["coin"]["data"]["data"]
    coin["raw_telemetry"] = {"pump_probability": 0.1, "dump_probability": 0.82}
    b["per_symbol"]["by_symbol"]["BTC/USDT"]["technical_analysis"]["data"]["analysis"][
        "setup_confidence_score"
    ] = 35.0
    b["endpoints"]["etf_metrics"]["data"]["data"]["net_flow_velocity"] = -0.05
    return b
