"""Tests for strategy loop cadence (interval between full graph runs)."""

import pytest

from config.cadence import (
    DEFAULT_STRATEGY_INTERVAL_SEC,
    STRATEGY_INTERVAL_ENV,
    load_strategy_interval_sec,
    warn_if_aggressive_cadence,
)


def test_default_interval_matches_product_default():
    assert load_strategy_interval_sec(env={}) == DEFAULT_STRATEGY_INTERVAL_SEC


def test_explicit_env_override():
    n = load_strategy_interval_sec(env={STRATEGY_INTERVAL_ENV: "1800"})
    assert n == 1800


def test_clamp_too_short():
    with pytest.warns(UserWarning, match="outside"):
        n = load_strategy_interval_sec(env={STRATEGY_INTERVAL_ENV: "60"})
    assert n == 300


def test_invalid_env_falls_back_with_warning():
    with pytest.warns(UserWarning, match="not a valid integer"):
        n = load_strategy_interval_sec(env={STRATEGY_INTERVAL_ENV: "not-a-number"})
    assert n == DEFAULT_STRATEGY_INTERVAL_SEC


def test_clamp_too_large():
    with pytest.warns(UserWarning, match="outside"):
        n = load_strategy_interval_sec(env={STRATEGY_INTERVAL_ENV: "999999"})
    assert n == 86400


_LLM_ENV = {"OPENAI_API_KEY": "sk-test-456"}


def test_warn_if_aggressive_cadence_emits_stderr_when_llm_and_fast_tick(capsys):
    warn_if_aggressive_cadence(30, env=_LLM_ENV)
    err = capsys.readouterr().err
    assert "LLM key configured" in err
    assert "30" in err


def test_warn_if_aggressive_cadence_silent_when_slow_or_no_key(capsys):
    warn_if_aggressive_cadence(900, env=_LLM_ENV)
    assert capsys.readouterr().err == ""
    warn_if_aggressive_cadence(30, env={})
    assert capsys.readouterr().err == ""
