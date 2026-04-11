"""Tier-0 canonical JSON contract for Tier-1 consumers."""

from schemas.tier0_contract import (
    CONTRACT_SCHEMA_VERSION,
    build_tier0_contract_json,
    tier0_contracts_by_agent,
)


def test_each_agent_emits_schema_version_and_id():
    m = build_tier0_contract_json(
        "monetary_sentinel",
        {"status": "success", "systemic_beta_score": 85, "liquidity_regime": "risk_on"},
        "BTC/USDT",
    )
    assert m["agent"] == "1.1"
    assert m["schema_version"] == CONTRACT_SCHEMA_VERSION
    assert m["Liquidity_Score"] == 85
    assert m["macro_regime_state"] == 2

    n = build_tier0_contract_json(
        "news_narrative_miner",
        {"status": "success", "breaker_score": 90, "breaker_state": "active"},
        "BTC/USDT",
    )
    assert n["agent"] == "1.2"
    assert n["News_Impact_Score"] == 90
    assert n["Event_Type"] == "Black Swan"

    ta = build_tier0_contract_json(
        "technical_ta_engine",
        {
            "status": "success",
            "ta_period": 14,
            "bars": 120,
            "ta_indicators": {"rsi": 55.2, "macd_hist": 0.01},
            "indicator_catalog_version": "ta_bundle/v1",
        },
        "BTC/USDT",
    )
    assert ta["agent"] == "2.3"
    assert ta["ta_indicators"]["rsi"] == 55.2


def test_tier0_contracts_by_agent_last_wins():
    state = {
        "tier0_contracts": [
            {"agent": "1.1", "Liquidity_Score": 10},
            {"agent": "1.2", "News_Impact_Score": 20},
        ]
    }
    idx = tier0_contracts_by_agent(state)
    assert idx["1.1"]["Liquidity_Score"] == 10
    assert idx["1.2"]["News_Impact_Score"] == 20
