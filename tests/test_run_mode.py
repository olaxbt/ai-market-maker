"""Tests for run mode resolution and live gate."""

import pytest

from config.run_mode import LIVE_CONFIRM_ENV, MODE_ENV, RunMode, load_run_mode


def test_default_is_paper_when_mode_unset(monkeypatch):
    monkeypatch.delenv(MODE_ENV, raising=False)
    assert load_run_mode() is RunMode.PAPER


def test_mode_from_env(monkeypatch):
    monkeypatch.setenv(MODE_ENV, "backtest")
    assert load_run_mode() is RunMode.BACKTEST


def test_override_beats_env(monkeypatch):
    monkeypatch.setenv(MODE_ENV, "paper")
    assert load_run_mode(override="backtest") is RunMode.BACKTEST


def test_invalid_mode_raises():
    with pytest.raises(ValueError, match="Invalid run mode"):
        load_run_mode(override="invalid")


def test_live_requires_confirmation(monkeypatch):
    monkeypatch.setenv(MODE_ENV, "live")
    monkeypatch.delenv(LIVE_CONFIRM_ENV, raising=False)
    with pytest.raises(ValueError, match="AI_MARKET_MAKER_ALLOW_LIVE"):
        load_run_mode()


@pytest.mark.parametrize("flag", ["1", "true", "yes"])
def test_live_allowed_with_confirmation(monkeypatch, flag):
    monkeypatch.setenv(MODE_ENV, "live")
    monkeypatch.setenv(LIVE_CONFIRM_ENV, flag)
    assert load_run_mode() is RunMode.LIVE


def test_live_override_with_confirmation(monkeypatch):
    monkeypatch.setenv(MODE_ENV, "paper")
    monkeypatch.setenv(LIVE_CONFIRM_ENV, "1")
    assert load_run_mode(override="live") is RunMode.LIVE
