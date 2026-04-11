"""Unit tests for Tier-0 → arbitrator consensus helper."""

from schemas.tier0_contract import tier0_consensus_for_arbitrator


def test_consensus_empty_state():
    c = tier0_consensus_for_arbitrator({})
    assert c["bull_tilt"] == 0
    assert c["bear_tilt"] == 0
    assert c["summary"] == "tier0_skipped"


def test_consensus_news_shock_blocks():
    state = {
        "tier0_contracts": [
            {"agent": "1.2", "News_Impact_Score": 85, "Event_Type": "Major Catalyst"},
        ]
    }
    c = tier0_consensus_for_arbitrator(state)
    assert c["block_aggressive_long"] is True
    assert c["bear_tilt"] >= 2
