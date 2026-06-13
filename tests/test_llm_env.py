"""Tests for LLM env helpers."""

from config.llm_env import llm_arbitrator_mode, llm_key_available
from config.llm_mode import llm_mode_enabled


def test_llm_key_available_false_when_unset():
    assert llm_key_available(env={}) is False


def test_llm_key_available_true_with_openai_key():
    assert llm_key_available(env={"OPENAI_API_KEY": "sk-test"}) is True


def test_llm_key_available_falls_back_to_llm_api_key():
    assert llm_key_available(env={"LLM_API_KEY": "sk-test"}) is True


def test_llm_mode_off_by_default_in_tests():
    assert llm_mode_enabled(env={}) is False


def test_llm_mode_explicit_on_and_off():
    assert llm_mode_enabled(env={"AIMM_LLM_MODE": "1"}) is True
    assert llm_mode_enabled(env={"AIMM_LLM_MODE": "true"}) is True
    assert llm_mode_enabled(env={"AIMM_LLM_MODE": "0"}) is False
    assert llm_mode_enabled(env={"AIMM_LLM_MODE": "off"}) is False


def test_arbitrator_mode_defaults_to_weighted_convergence():
    assert llm_arbitrator_mode(env={}) == "weighted_convergence"


def test_arbitrator_mode_llm():
    assert llm_arbitrator_mode(env={"AIMM_ARBITRATOR_MODE": "llm"}) == "llm"
    assert llm_arbitrator_mode(env={"AIMM_ARBITRATOR_MODE": "LLM"}) == "llm"
