from __future__ import annotations

import pytest

from config.llm_mode import llm_mode_enabled, llm_required


def test_llm_mode_env_override_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIMM_LLM_MODE", "1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert llm_mode_enabled() is True


def test_llm_mode_env_override_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIMM_LLM_MODE", "0")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-xxx")
    assert llm_mode_enabled() is False


def test_llm_mode_auto_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AIMM_LLM_MODE", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert llm_mode_enabled() is False
    monkeypatch.setenv("OPENAI_API_KEY", "sk-xxx")
    # llm_mode auto-enable is intentionally disabled under pytest for safety.
    assert llm_mode_enabled() is False


def test_llm_required_defaults_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AIMM_LLM_REQUIRED", raising=False)
    assert llm_required() is False


def test_llm_required_on(monkeypatch: pytest.MonkeyPatch) -> None:
    for val in ("1", "true", "yes", "y", "on"):
        monkeypatch.setenv("AIMM_LLM_REQUIRED", val)
        assert llm_required() is True, f"{val=} should be truthy"


def test_llm_required_off(monkeypatch: pytest.MonkeyPatch) -> None:
    for val in ("0", "false", "no", "n", "off"):
        monkeypatch.setenv("AIMM_LLM_REQUIRED", val)
        assert llm_required() is False, f"{val=} should be falsy"
