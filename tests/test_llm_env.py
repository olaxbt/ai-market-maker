"""Agentic LLM key semantics (``config.llm_env``)."""

from config.llm_env import llm_key_available, use_llm_arbitrator

_KEY = {"OPENAI_API_KEY": "sk-test-123"}
_EMPTY = {}


def test_use_llm_returns_false_when_no_key():
    assert use_llm_arbitrator(env=_EMPTY) is False


def test_use_llm_returns_true_when_key_present():
    assert use_llm_arbitrator(env=_KEY) is True
    assert llm_key_available(env=_KEY) is True
