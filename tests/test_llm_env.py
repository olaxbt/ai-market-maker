"""``AI_MARKET_MAKER_USE_LLM`` semantics (single source of truth in ``config.llm_env``).

The system is agentic — ``use_llm_arbitrator()`` returns True when a provider
key is configured.  The ``AI_MARKET_MAKER_USE_LLM`` env var is a legacy toggle
that can force off but cannot conjure a key out of thin air.
"""

from config.llm_env import use_llm_arbitrator

_KEY = {"OPENAI_API_KEY": "sk-test-123"}
_EMPTY = {}


def test_use_llm_returns_false_when_no_key():
    """No key in env dict → False regardless of legacy flag."""
    assert use_llm_arbitrator(env=_EMPTY) is False
    assert use_llm_arbitrator(env={"AI_MARKET_MAKER_USE_LLM": ""}) is False
    assert use_llm_arbitrator(env={"AI_MARKET_MAKER_USE_LLM": "1"}) is False


def test_use_llm_returns_false_when_explicitly_disabled():
    """Legacy ``0`` / ``false`` / ``no`` / ``off`` forces off, even with a key."""
    for val in ("0", "false", "no", "off"):
        env = {"AI_MARKET_MAKER_USE_LLM": val, **_KEY}
        assert use_llm_arbitrator(env=env) is False, f"{val=} should force off"


def test_use_llm_returns_true_when_key_present():
    """Key present + no explicit disable → True (agentic default)."""
    assert use_llm_arbitrator(env=_KEY) is True


def test_use_llm_legacy_flag_honoured_as_additional_hint():
    """``AI_MARKET_MAKER_USE_LLM=1`` works when a key is present."""
    env = {"AI_MARKET_MAKER_USE_LLM": "1", **_KEY}
    assert use_llm_arbitrator(env=env) is True

    for val in ("true", "YES", "y", "On"):
        env = {"AI_MARKET_MAKER_USE_LLM": val, **_KEY}
        assert use_llm_arbitrator(env=env) is True, f"{val=} should work with key"
