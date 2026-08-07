from __future__ import annotations

import time
from datetime import date
from typing import Any

import httpx

from agents.retail_hype_tracker import RetailHypeTrackerAgent
from nexus_data.adanos import (
    AdanosSentimentConfig,
    adanos_feeds_enabled,
    fetch_adanos_crypto_sentiment_bundle,
)


def test_adanos_feed_disabled_without_api_key(monkeypatch):
    monkeypatch.delenv("ADANOS_API_KEY", raising=False)
    monkeypatch.setenv("ADANOS_DISABLE", "0")

    assert adanos_feeds_enabled() is False
    assert fetch_adanos_crypto_sentiment_bundle(["BTC/USDT"]) == {
        "ok": False,
        "error": "ADANOS_API_KEY is not configured",
        "data": None,
    }


def test_adanos_feed_fetches_unique_base_assets(monkeypatch):
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        symbol = request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(
            200,
            json={
                "data": {
                    "found": True,
                    "mentions": 42 if symbol == "BTC" else 7,
                    "sentiment_score": 0.35,
                    "buzz_score": 24.5,
                    "bullish_pct": 63.0,
                    "bearish_pct": 12.0,
                    "trend": "rising",
                }
            },
        )

    real_client = httpx.Client
    transport = httpx.MockTransport(handler)

    def client_factory(*args: Any, **kwargs: Any) -> httpx.Client:
        return real_client(*args, transport=transport, **kwargs)

    monkeypatch.setattr("nexus_data.adanos.httpx.Client", client_factory)

    out = fetch_adanos_crypto_sentiment_bundle(
        ["BTC/USDT", "BTC/USDC", "ETH/USDT"],
        cfg=AdanosSentimentConfig(
            api_base="https://api.example.test/reddit/crypto/v1",
            api_key="sk_test",
            timeout_s=3.0,
            lookback_days=3,
            max_symbols=2,
        ),
        today=date(2026, 6, 27),
    )

    assert out["ok"] is True
    assert out["data"]["window"] == {"from": "2026-06-25", "to": "2026-06-27"}
    assert [row["symbol"] for row in out["data"]["rows"]] == ["BTC", "ETH"]
    assert out["data"]["rows"][0]["mention_count"] == 42
    assert out["data"]["rows"][0]["bullish_ratio"] == 0.63
    assert len(calls) == 2
    assert calls[0].headers["X-API-Key"] == "sk_test"
    assert calls[0].url.params["from"] == "2026-06-25"


def test_adanos_feed_treats_404_as_missing_symbol(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "not found"})

    real_client = httpx.Client
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        "nexus_data.adanos.httpx.Client",
        lambda *args, **kwargs: real_client(*args, transport=transport, **kwargs),
    )

    out = fetch_adanos_crypto_sentiment_bundle(
        ["DOGE/USDT"],
        cfg=AdanosSentimentConfig(api_key="sk_test"),
        today=date(2026, 6, 27),
    )

    assert out["ok"] is True
    assert out["data"]["rows"] == [{"symbol": "DOGE", "found": False, "mention_count": 0}]


def test_adanos_feed_enforces_total_timeout(monkeypatch):
    def slow_fetch(*args: Any, **kwargs: Any) -> dict[str, Any]:
        time.sleep(0.1)
        return {"symbol": "BTC", "found": True, "mention_count": 1}

    monkeypatch.setattr("nexus_data.adanos._fetch_symbol_row", slow_fetch)

    out = fetch_adanos_crypto_sentiment_bundle(
        ["BTC/USDT"],
        cfg=AdanosSentimentConfig(
            api_key="sk_test",
            timeout_s=0.1,
            total_timeout_s=0.01,
            max_workers=1,
        ),
        today=date(2026, 6, 27),
    )

    assert out["ok"] is False
    assert out["data"]["rows"] == []
    assert "BTC: timed out after 0.0s total budget" in out["error"]


def test_retail_hype_tracker_uses_adanos_sentiment_when_nexus_is_absent():
    analysis = RetailHypeTrackerAgent().analyze(
        ticker="BTC/USDT",
        market_data={},
        nexus_context={
            "endpoints": {
                "adanos_crypto_sentiment": {
                    "ok": True,
                    "data": {
                        "success": True,
                        "rows": [
                            {
                                "symbol": "BTC",
                                "found": True,
                                "mention_count": 120,
                                "sentiment_score": 0.4,
                                "buzz_score": 32.0,
                                "bullish_ratio": 0.66,
                            }
                        ],
                    },
                }
            }
        },
    )

    assert analysis["status"] == "success"
    assert analysis["sentiment_z_score"] == 0.8
    assert analysis["fomo_level"] > 80
    assert analysis["inputs"]["mention_count"] == 120
    assert analysis["inputs"]["sentiment_source"] == "adanos"


def test_retail_hype_tracker_skips_empty_adanos_context():
    analysis = RetailHypeTrackerAgent().analyze(
        ticker="BTC/USDT",
        market_data={},
        nexus_context={
            "endpoints": {
                "adanos_crypto_sentiment": {
                    "ok": True,
                    "data": {"success": True, "rows": []},
                }
            }
        },
    )

    assert analysis["status"] == "skipped"
