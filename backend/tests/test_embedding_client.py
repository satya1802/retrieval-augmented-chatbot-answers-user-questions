"""Unit tests for app/services/embedding_client.py.

The real OpenAI SDK is never imported by any test here that doesn't
explicitly want to see how the SDK client would be constructed: `embed()`
is exercised against a fake SDK client installed directly as
`EmbeddingClient._sdk_client` (the same seam `_client()` lazily populates),
and construction itself is exercised by monkeypatching `openai.OpenAI`
so no network access or API key is ever required.
"""

from unittest.mock import MagicMock

import pytest

from app.services import embedding_client as module
from app.services.embedding_client import (
    EmbeddingClient,
    get_embedding_client,
    set_embedding_client,
)


@pytest.fixture(autouse=True)
def _reset_shared_client():
    """Every test starts and ends with no installed fake, so one test's
    `set_embedding_client` can never leak into the next."""
    set_embedding_client(None)
    yield
    set_embedding_client(None)


def _fake_sdk_client(vectors: list[list[float]]) -> MagicMock:
    """A stand-in for the OpenAI SDK client: `.embeddings.create(...)`
    returns an object shaped like the real response -- a `.data` list
    whose items each expose `.embedding`."""
    response = MagicMock()
    response.data = [MagicMock(embedding=vector) for vector in vectors]
    sdk = MagicMock()
    sdk.embeddings.create.return_value = response
    return sdk


# -- embed() ------------------------------------------------------------


def test_embed_empty_input_returns_empty_list_without_calling_provider():
    client = EmbeddingClient()
    client._sdk_client = _fake_sdk_client([])

    assert client.embed([]) == []
    client._sdk_client.embeddings.create.assert_not_called()


def test_embed_returns_one_vector_per_text_in_order():
    client = EmbeddingClient()
    vectors = [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]
    client._sdk_client = _fake_sdk_client(vectors)

    result = client.embed(["first chunk", "second chunk", "third chunk"])

    assert result == vectors


def test_embed_sends_the_texts_and_configured_model_to_the_provider():
    client = EmbeddingClient(model="my-embedding-model")
    client._sdk_client = _fake_sdk_client([[1.0, 2.0]])

    client.embed(["only chunk"])

    client._sdk_client.embeddings.create.assert_called_once_with(
        model="my-embedding-model", input=["only chunk"]
    )


def test_embed_defaults_to_the_app_configured_embedding_model():
    client = EmbeddingClient()
    assert client.model == module.EMBEDDING_MODEL


def test_embed_mismatched_vector_count_is_surfaced_not_silently_truncated():
    # The provider returning fewer vectors than texts is a caller-visible
    # bug (ingestion_service checks len(vectors) != len(pieces)); embed()
    # must hand back exactly what the provider gave it rather than padding
    # or truncating to make the counts line up.
    client = EmbeddingClient()
    client._sdk_client = _fake_sdk_client([[1.0]])

    result = client.embed(["one", "two"])

    assert result == [[1.0]]


# -- lazy SDK construction ------------------------------------------------


def test_constructing_a_client_never_touches_the_sdk(monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("OpenAI SDK constructed before any embed() call")

    monkeypatch.setattr("openai.OpenAI", _boom)

    EmbeddingClient()  # must not raise -- construction alone needs no SDK, no key


def test_sdk_client_is_constructed_with_configured_credentials(monkeypatch):
    captured = {}

    class _FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("openai.OpenAI", _FakeOpenAI)
    monkeypatch.setattr(module, "AI_PROVIDER_API_KEY", "test-key")
    monkeypatch.setattr(module, "AI_PROVIDER_BASE_URL", "https://example.test/v1")

    sdk = EmbeddingClient()._client()

    assert isinstance(sdk, _FakeOpenAI)
    assert captured == {"api_key": "test-key", "base_url": "https://example.test/v1"}


def test_empty_api_key_is_passed_to_the_sdk_as_none(monkeypatch):
    captured = {}

    class _FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("openai.OpenAI", _FakeOpenAI)
    monkeypatch.setattr(module, "AI_PROVIDER_API_KEY", "")

    EmbeddingClient()._client()

    assert captured["api_key"] is None


def test_sdk_client_is_constructed_once_and_reused(monkeypatch):
    constructions = []

    class _FakeOpenAI:
        def __init__(self, **kwargs):
            constructions.append(kwargs)

    monkeypatch.setattr("openai.OpenAI", _FakeOpenAI)

    client = EmbeddingClient()
    first = client._client()
    second = client._client()

    assert first is second
    assert len(constructions) == 1


# -- the shared, swappable client seam ------------------------------------


def test_get_embedding_client_returns_the_same_instance_every_call():
    first = get_embedding_client()
    second = get_embedding_client()

    assert first is second


def test_set_embedding_client_installs_a_fake_for_call_sites():
    fake = EmbeddingClient()

    set_embedding_client(fake)

    assert get_embedding_client() is fake


def test_set_embedding_client_none_restores_a_fresh_default():
    fake = EmbeddingClient()
    set_embedding_client(fake)

    set_embedding_client(None)
    restored = get_embedding_client()

    assert restored is not fake
    assert isinstance(restored, EmbeddingClient)
