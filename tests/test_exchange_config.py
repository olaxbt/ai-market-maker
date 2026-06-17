from __future__ import annotations

import pytest

from config.exchange_env import (
    EXCHANGE_ENV,
    HL_API_BASE_ENV,
    HL_API_KEY_ENV,
    HL_DRY_RUN_ENV,
    HL_SECRET_ENV,
    HL_TESTNET_ENV,
    load_exchange_config,
)


def test_default_exchange_config_is_paper(monkeypatch):
    monkeypatch.delenv(EXCHANGE_ENV, raising=False)
    monkeypatch.delenv("AI_MARKET_MAKER_ALLOW_LIVE", raising=False)
    monkeypatch.delenv(HL_DRY_RUN_ENV, raising=False)
    cfg = load_exchange_config()
    assert cfg.exchange_name == "paper"
    assert cfg.testnet is True
    assert cfg.dry_run is False
    assert cfg.hyperliquid_api_key is None
    assert cfg.hyperliquid_secret is None


def test_paper_mode_ignores_hyperliquid_dry_run(monkeypatch):
    """EXCHANGE=paper must ignore HYPERLIQUID_DRY_RUN (paper uses no HL adapter)."""
    monkeypatch.delenv(EXCHANGE_ENV, raising=False)
    monkeypatch.delenv("AI_MARKET_MAKER_ALLOW_LIVE", raising=False)
    monkeypatch.setenv(HL_DRY_RUN_ENV, "1")
    cfg = load_exchange_config()
    assert cfg.exchange_name == "paper"
    assert cfg.dry_run is False


def test_hyperliquid_without_live_flag_raises(monkeypatch):
    monkeypatch.setenv(EXCHANGE_ENV, "hyperliquid")
    monkeypatch.delenv("AI_MARKET_MAKER_ALLOW_LIVE", raising=False)
    with pytest.raises(ValueError, match="AI_MARKET_MAKER_ALLOW_LIVE"):
        load_exchange_config()


def test_hyperliquid_with_live_flag(monkeypatch):
    monkeypatch.setenv(EXCHANGE_ENV, "hyperliquid")
    monkeypatch.setenv("AI_MARKET_MAKER_ALLOW_LIVE", "1")
    monkeypatch.setenv(HL_API_KEY_ENV, "wallet-addr")
    monkeypatch.setenv(HL_SECRET_ENV, "private-key")
    monkeypatch.setenv(HL_TESTNET_ENV, "1")
    cfg = load_exchange_config()
    assert cfg.exchange_name == "hyperliquid"
    assert cfg.testnet is True
    assert cfg.hyperliquid_api_key == "wallet-addr"
    assert cfg.hyperliquid_secret == "private-key"


def test_hyperliquid_dry_run(monkeypatch):
    monkeypatch.setenv(EXCHANGE_ENV, "hyperliquid")
    monkeypatch.setenv("AI_MARKET_MAKER_ALLOW_LIVE", "1")
    monkeypatch.setenv(HL_DRY_RUN_ENV, "1")
    cfg = load_exchange_config()
    assert cfg.dry_run is True


def test_unknown_exchange_also_requires_live_flag(monkeypatch):
    monkeypatch.setenv(EXCHANGE_ENV, "binance")
    monkeypatch.delenv("AI_MARKET_MAKER_ALLOW_LIVE", raising=False)
    with pytest.raises(ValueError, match="AI_MARKET_MAKER_ALLOW_LIVE"):
        load_exchange_config()


def test_secret_not_in_repr(monkeypatch):
    monkeypatch.setenv(EXCHANGE_ENV, "hyperliquid")
    monkeypatch.setenv("AI_MARKET_MAKER_ALLOW_LIVE", "1")
    monkeypatch.setenv(HL_SECRET_ENV, "super-secret-key-12345")
    cfg = load_exchange_config()
    r = repr(cfg)
    assert "super-secret-key-12345" not in r


def test_paper_mode_ignores_live_flag(monkeypatch):
    monkeypatch.delenv(EXCHANGE_ENV, raising=False)
    monkeypatch.delenv("AI_MARKET_MAKER_ALLOW_LIVE", raising=False)
    cfg = load_exchange_config()
    assert cfg.exchange_name == "paper"


def test_truthy_variants(monkeypatch):
    for val in ("1", "true", "yes", "True", "YES"):
        monkeypatch.setenv(EXCHANGE_ENV, "hyperliquid")
        monkeypatch.setenv("AI_MARKET_MAKER_ALLOW_LIVE", val)
        cfg = load_exchange_config()
        assert cfg.exchange_name == "hyperliquid"


def test_testnet_defaults_true_for_non_paper_mode(monkeypatch):
    """HYPERLIQUID_TESTNET unset must still yield testnet=True (safe default)."""
    monkeypatch.setenv(EXCHANGE_ENV, "hyperliquid")
    monkeypatch.setenv("AI_MARKET_MAKER_ALLOW_LIVE", "1")
    monkeypatch.delenv(HL_TESTNET_ENV, raising=False)
    cfg = load_exchange_config()
    assert cfg.testnet is True


def test_hl_api_base_env_constant_is_exported(monkeypatch):
    """HL_API_BASE_ENV must be importable and used to override the API base URL."""
    monkeypatch.setenv(EXCHANGE_ENV, "hyperliquid")
    monkeypatch.setenv("AI_MARKET_MAKER_ALLOW_LIVE", "1")
    monkeypatch.setenv(HL_API_BASE_ENV, "https://my-custom-hl-base.example.com")
    cfg = load_exchange_config()
    assert cfg.hyperliquid_api_base == "https://my-custom-hl-base.example.com"
