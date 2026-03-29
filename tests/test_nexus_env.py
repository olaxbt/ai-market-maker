"""Tests for OLAXBT Nexus-oriented environment helpers."""

from config.nexus_env import NEXUS_DATA_BASE_URL_ENV, load_nexus_data_base_url


def test_load_nexus_data_base_url_unset():
    assert load_nexus_data_base_url(env={}) is None


def test_load_nexus_data_base_url_set():
    url = "https://nexus.example.invalid/v1"
    assert load_nexus_data_base_url(env={NEXUS_DATA_BASE_URL_ENV: f"  {url}  "}) == url
