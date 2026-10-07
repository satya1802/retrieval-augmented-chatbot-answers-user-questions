"""Unit tests for backend/app/config.py.

`app.config` reads every setting once at import time via `os.getenv`, so the
only way to exercise "an env var overrides the default" is to set the env
var *before* the module is (re-)imported, then reload it. Each test restores
the module to its unmodified state afterwards via `importlib.reload` with no
overrides, so tests don't leak state into each other through the module
cache.
"""

import importlib

import pytest

import app.config as config


def reload_config():
    """Re-execute app.config against the current os.environ."""
    return importlib.reload(config)


@pytest.fixture(autouse=True)
def restore_config_module():
    """Ensure app.config reflects a clean environment again after each test,
    regardless of what env vars an individual test set."""
    yield
    reload_config()


class TestDefaults:
    """With no env vars set, every setting falls back to its documented
    default -- this is what makes the module usable out of the box in dev
    and in the checks, which do not export any of these."""

    def test_documents_cap_default(self, monkeypatch):
        monkeypatch.delenv("DOCUMENTS_CAP", raising=False)
        mod = reload_config()
        assert mod.DOCUMENTS_CAP == 50

    def test_monthly_question_cap_default(self, monkeypatch):
        monkeypatch.delenv("MONTHLY_QUESTION_CAP", raising=False)
        mod = reload_config()
        assert mod.MONTHLY_QUESTION_CAP == 200

    def test_storage_root_default(self, monkeypatch):
        monkeypatch.delenv("STORAGE_ROOT", raising=False)
        mod = reload_config()
        assert mod.STORAGE_ROOT == "./storage"

    def test_chunk_size_default(self, monkeypatch):
        monkeypatch.delenv("CHUNK_SIZE", raising=False)
        mod = reload_config()
        assert mod.CHUNK_SIZE == 1000

    def test_chunk_overlap_default(self, monkeypatch):
        monkeypatch.delenv("CHUNK_OVERLAP", raising=False)
        mod = reload_config()
        assert mod.CHUNK_OVERLAP == 200

    def test_embedding_model_default(self, monkeypatch):
        monkeypatch.delenv("AI_PROVIDER_EMBEDDING_MODEL", raising=False)
        mod = reload_config()
        assert mod.EMBEDDING_MODEL == "text-embedding-3-small"

    def test_ai_provider_api_key_default_is_empty_string(self, monkeypatch):
        monkeypatch.delenv("AI_PROVIDER_API_KEY", raising=False)
        mod = reload_config()
        assert mod.AI_PROVIDER_API_KEY == ""

    def test_ai_provider_base_url_default_is_none(self, monkeypatch):
        monkeypatch.delenv("AI_PROVIDER_BASE_URL", raising=False)
        mod = reload_config()
        assert mod.AI_PROVIDER_BASE_URL is None

    def test_chat_model_default(self, monkeypatch):
        monkeypatch.delenv("AI_PROVIDER_CHAT_MODEL", raising=False)
        mod = reload_config()
        assert mod.CHAT_MODEL == "gpt-4o-mini"

    def test_generation_timeout_seconds_default(self, monkeypatch):
        monkeypatch.delenv("AI_PROVIDER_TIMEOUT_SECONDS", raising=False)
        mod = reload_config()
        assert mod.GENERATION_TIMEOUT_SECONDS == 30.0

    def test_retrieval_top_k_default(self, monkeypatch):
        monkeypatch.delenv("RETRIEVAL_TOP_K", raising=False)
        mod = reload_config()
        assert mod.RETRIEVAL_TOP_K == 5


class TestEnvOverrides:
    """Every setting is a single, configurable value (per the module's own
    docstring, referencing AC-013), so each one must actually change when
    its env var is set -- not just have a default."""

    def test_documents_cap_overridden(self, monkeypatch):
        monkeypatch.setenv("DOCUMENTS_CAP", "75")
        mod = reload_config()
        assert mod.DOCUMENTS_CAP == 75
        assert isinstance(mod.DOCUMENTS_CAP, int)

    def test_monthly_question_cap_overridden(self, monkeypatch):
        monkeypatch.setenv("MONTHLY_QUESTION_CAP", "999")
        mod = reload_config()
        assert mod.MONTHLY_QUESTION_CAP == 999
        assert isinstance(mod.MONTHLY_QUESTION_CAP, int)

    def test_storage_root_overridden(self, monkeypatch):
        monkeypatch.setenv("STORAGE_ROOT", "/mnt/uploads")
        mod = reload_config()
        assert mod.STORAGE_ROOT == "/mnt/uploads"

    def test_chunk_size_overridden(self, monkeypatch):
        monkeypatch.setenv("CHUNK_SIZE", "500")
        mod = reload_config()
        assert mod.CHUNK_SIZE == 500
        assert isinstance(mod.CHUNK_SIZE, int)

    def test_chunk_overlap_overridden(self, monkeypatch):
        monkeypatch.setenv("CHUNK_OVERLAP", "50")
        mod = reload_config()
        assert mod.CHUNK_OVERLAP == 50
        assert isinstance(mod.CHUNK_OVERLAP, int)

    def test_embedding_model_overridden(self, monkeypatch):
        monkeypatch.setenv("AI_PROVIDER_EMBEDDING_MODEL", "text-embedding-3-large")
        mod = reload_config()
        assert mod.EMBEDDING_MODEL == "text-embedding-3-large"

    def test_ai_provider_api_key_overridden(self, monkeypatch):
        monkeypatch.setenv("AI_PROVIDER_API_KEY", "sk-test-key")
        mod = reload_config()
        assert mod.AI_PROVIDER_API_KEY == "sk-test-key"

    def test_ai_provider_base_url_overridden(self, monkeypatch):
        monkeypatch.setenv("AI_PROVIDER_BASE_URL", "https://example.test/v1")
        mod = reload_config()
        assert mod.AI_PROVIDER_BASE_URL == "https://example.test/v1"

    def test_ai_provider_base_url_empty_string_treated_as_unset(self, monkeypatch):
        """`os.getenv("AI_PROVIDER_BASE_URL") or None` means an empty-string
        override (e.g. an unset-but-exported var in some deploy tooling)
        falls back to None rather than becoming an empty base URL, which
        would break the OpenAI-compatible client's default endpoint."""
        monkeypatch.setenv("AI_PROVIDER_BASE_URL", "")
        mod = reload_config()
        assert mod.AI_PROVIDER_BASE_URL is None

    def test_chat_model_overridden(self, monkeypatch):
        monkeypatch.setenv("AI_PROVIDER_CHAT_MODEL", "gpt-4o")
        mod = reload_config()
        assert mod.CHAT_MODEL == "gpt-4o"

    def test_generation_timeout_seconds_overridden(self, monkeypatch):
        monkeypatch.setenv("AI_PROVIDER_TIMEOUT_SECONDS", "10.5")
        mod = reload_config()
        assert mod.GENERATION_TIMEOUT_SECONDS == 10.5
        assert isinstance(mod.GENERATION_TIMEOUT_SECONDS, float)

    def test_retrieval_top_k_overridden(self, monkeypatch):
        monkeypatch.setenv("RETRIEVAL_TOP_K", "10")
        mod = reload_config()
        assert mod.RETRIEVAL_TOP_K == 10
        assert isinstance(mod.RETRIEVAL_TOP_K, int)
