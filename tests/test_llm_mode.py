from __future__ import annotations

import pytest

from config.llm_env import llm_key_available, require_llm_key


def test_llm_key_available_false_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    assert llm_key_available() is False


def test_llm_key_available_true_with_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert llm_key_available() is True


def test_require_llm_key_skips_under_pytest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "tests/test_llm_mode.py::test")
    require_llm_key()  # must not exit
