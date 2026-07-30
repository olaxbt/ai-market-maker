"""``AI_MARKET_MAKER_USE_LLM`` semantics (single source of truth in ``config.llm_env``).

The system is agentic — ``use_llm_arbitrator()`` returns True when a provider
key is configured.  The ``AI_MARKET_MAKER_USE_LLM`` env var is a legacy toggle
that can force off but cannot conjure a key out of thin air.
"""

from config.llm_env import (
    ATLAS_CLOUD_BASE_URL,
    ATLAS_CLOUD_MODEL,
    resolve_llm_config,
    use_llm_arbitrator,
)

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


def test_atlas_cloud_key_enables_llm_with_provider_defaults():
    for key_name in ("ATLASCLOUD_API_KEY", "ATLAS_CLOUD_API_KEY"):
        config = resolve_llm_config({key_name: "atlas-test-key"})

        assert use_llm_arbitrator(env={key_name: "atlas-test-key"}) is True
        assert config.api_key == "atlas-test-key"
        assert config.base_url == ATLAS_CLOUD_BASE_URL
        assert config.model == ATLAS_CLOUD_MODEL


def test_atlas_cloud_aliases_support_endpoint_and_model_overrides():
    config = resolve_llm_config(
        {
            "ATLASCLOUD_API_KEY": "atlas-test-key",
            "ATLAS_CLOUD_BASE_URL": "https://atlas.example/v1",
            "ATLASCLOUD_MODEL": "qwen/qwen3.5-flash",
        }
    )

    assert config.base_url == "https://atlas.example/v1"
    assert config.model == "qwen/qwen3.5-flash"

    api_base_config = resolve_llm_config(
        {
            "ATLAS_CLOUD_API_KEY": "atlas-test-key",
            "ATLASCLOUD_API_BASE": "https://api-base.example/v1",
        }
    )
    assert api_base_config.base_url == "https://api-base.example/v1"


def test_existing_openai_configuration_keeps_priority_over_atlas_cloud():
    config = resolve_llm_config(
        {
            "OPENAI_API_KEY": "openai-test-key",
            "OPENAI_BASE_URL": "https://openai.example/v1",
            "OPENAI_MODEL": "existing-model",
            "ATLASCLOUD_API_KEY": "atlas-test-key",
        }
    )

    assert config.api_key == "openai-test-key"
    assert config.base_url == "https://openai.example/v1"
    assert config.model == "existing-model"
