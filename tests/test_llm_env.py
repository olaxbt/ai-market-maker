"""``AI_MARKET_MAKER_USE_LLM`` semantics (single source of truth in ``config.llm_env``)."""

from config.llm_env import use_llm_arbitrator


def test_llm_off_by_default_and_zero():
    assert use_llm_arbitrator(env={}) is False
    assert use_llm_arbitrator(env={"AI_MARKET_MAKER_USE_LLM": ""}) is False
    assert use_llm_arbitrator(env={"AI_MARKET_MAKER_USE_LLM": "0"}) is False
    assert use_llm_arbitrator(env={"AI_MARKET_MAKER_USE_LLM": "false"}) is False
    assert use_llm_arbitrator(env={"AI_MARKET_MAKER_USE_LLM": "no"}) is False


def test_llm_on_truthy_values():
    assert use_llm_arbitrator(env={"AI_MARKET_MAKER_USE_LLM": "1"}) is True
    assert use_llm_arbitrator(env={"AI_MARKET_MAKER_USE_LLM": "true"}) is True
    assert use_llm_arbitrator(env={"AI_MARKET_MAKER_USE_LLM": "YES"}) is True
    assert use_llm_arbitrator(env={"AI_MARKET_MAKER_USE_LLM": "y"}) is True
    assert use_llm_arbitrator(env={"AI_MARKET_MAKER_USE_LLM": "On"}) is True
