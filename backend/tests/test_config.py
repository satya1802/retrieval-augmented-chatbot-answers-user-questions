"""Unit tests for backend/app/config.py.

config.py reads every setting once, at import time, with `os.getenv(...,
default)`. That means the only way to observe either half of the contract
(the default applies when nothing is set; the environment wins when it is)
is to control the environment *before* the module is imported and reload it
in between assertions -- a plain `import app.config` only ever runs once
per test process and would just hand every test the same cached module.

Assumption: there is no existing app/config.py test or conftest fixture for
this reload dance, so each test below sets up its own environment with
monkeypatch and reloads the module directly, undoing the per-test env
afterwards via monkeypatch's own teardown (monkeypatch.setenv/delenv are
automatically reverted). The last test in each group restores the module to
its real-environment state for any test collected after it in the same
session.
"""

import importlib

import pytest

from app import config as config_module

ENV_VARS = (
    "DOCUMENTS_CAP",
    "MONTHLY_QUESTION_CAP",
    "STORAGE_ROOT",
    "CHUNK_SIZE",
    "CHUNK_OVERLAP",
    "AI_PROVIDER_EMBEDDING_MODEL",
    "AI_PROVIDER_API_KEY",
    "AI_PROVIDER_BASE_URL",
)


def reload_config(monkeypatch, **env):
    """Clear every setting this module reads, apply `env`, then reload it.

    Returns the freshly-reloaded module so assertions read the values the
    module actually computed, not values recomputed in the test.
    """
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return importlib.reload(config_module)


@pytest.fixture(autouse=True)
def _restore_module(monkeypatch):
    """Leave app.config matching the real environment once a test is done,
    so unrelated tests importing it afterwards see the real settings rather
    than whatever the last config test left behind."""
    yield
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    importlib.reload(config_module)


class TestDefaults:
    def test_defaults_apply_when_nothing_is_set(self, monkeypatch):
        cfg = reload_config(monkeypatch)

        assert cfg.DOCUMENTS_CAP == 50
        assert cfg.MONTHLY_QUESTION_CAP == 200
        assert cfg.STORAGE_ROOT == "./storage"
        assert cfg.CHUNK_SIZE == 1000
        assert cfg.CHUNK_OVERLAP == 200
        assert cfg.EMBEDDING_MODEL == "text-embedding-3-small"
        assert cfg.AI_PROVIDER_API_KEY == ""
        assert cfg.AI_PROVIDER_BASE_URL is None

    def test_default_caps_are_ints_not_strings(self, monkeypatch):
        cfg = reload_config(monkeypatch)

        assert isinstance(cfg.DOCUMENTS_CAP, int)
        assert isinstance(cfg.MONTHLY_QUESTION_CAP, int)
        assert isinstance(cfg.CHUNK_SIZE, int)
        assert isinstance(cfg.CHUNK_OVERLAP, int)


class TestDocumentsCapIsASingleConfigurableSetting:
    """AC-013, referenced directly in config.py's module docstring: the
    document cap must be overridable from one place."""

    def test_documents_cap_overridden_by_env(self, monkeypatch):
        cfg = reload_config(monkeypatch, DOCUMENTS_CAP="5")

        assert cfg.DOCUMENTS_CAP == 5
        assert isinstance(cfg.DOCUMENTS_CAP, int)

    def test_monthly_question_cap_overridden_by_env(self, monkeypatch):
        cfg = reload_config(monkeypatch, MONTHLY_QUESTION_CAP="2")

        assert cfg.MONTHLY_QUESTION_CAP == 2


class TestStorageRoot:
    def test_storage_root_overridden_by_env(self, monkeypatch):
        cfg = reload_config(monkeypatch, STORAGE_ROOT="/var/data/uploads")

        assert cfg.STORAGE_ROOT == "/var/data/uploads"


class TestIngestionPipelineSettings:
    """US-006-1: chunk size, overlap and the embedding model are configured
    the same way as the fair-use caps -- a single env-backed setting each."""

    def test_chunk_size_overridden_by_env(self, monkeypatch):
        cfg = reload_config(monkeypatch, CHUNK_SIZE="500")

        assert cfg.CHUNK_SIZE == 500
        assert isinstance(cfg.CHUNK_SIZE, int)

    def test_chunk_overlap_overridden_by_env(self, monkeypatch):
        cfg = reload_config(monkeypatch, CHUNK_OVERLAP="50")

        assert cfg.CHUNK_OVERLAP == 50
        assert isinstance(cfg.CHUNK_OVERLAP, int)

    def test_chunk_size_and_overlap_are_independent_settings(self, monkeypatch):
        cfg = reload_config(monkeypatch, CHUNK_SIZE="750", CHUNK_OVERLAP="100")

        assert cfg.CHUNK_SIZE == 750
        assert cfg.CHUNK_OVERLAP == 100

    def test_embedding_model_overridden_by_env(self, monkeypatch):
        cfg = reload_config(
            monkeypatch, AI_PROVIDER_EMBEDDING_MODEL="text-embedding-3-large"
        )

        assert cfg.EMBEDDING_MODEL == "text-embedding-3-large"


class TestAiProviderCredentials:
    def test_api_key_overridden_by_env(self, monkeypatch):
        cfg = reload_config(monkeypatch, AI_PROVIDER_API_KEY="sk-test-123")

        assert cfg.AI_PROVIDER_API_KEY == "sk-test-123"

    def test_base_url_set_to_a_value(self, monkeypatch):
        cfg = reload_config(
            monkeypatch, AI_PROVIDER_BASE_URL="https://api.example.com/v1"
        )

        assert cfg.AI_PROVIDER_BASE_URL == "https://api.example.com/v1"

    def test_base_url_unset_is_none_not_missing_attribute(self, monkeypatch):
        cfg = reload_config(monkeypatch)

        assert cfg.AI_PROVIDER_BASE_URL is None

    def test_base_url_set_to_empty_string_is_none(self, monkeypatch):
        """`os.getenv(...) or None` folds a blank override (e.g. an unset
        placeholder left as `AI_PROVIDER_BASE_URL=` in a deployment's env
        file) to None rather than leaving it as the empty string, so callers
        can rely on "falsy means use the provider's default base URL"."""
        cfg = reload_config(monkeypatch, AI_PROVIDER_BASE_URL="")

        assert cfg.AI_PROVIDER_BASE_URL is None
