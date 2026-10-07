"""Unit tests for `app/services/embedding_client.py`.

No acceptance criteria are attached to this ticket, so the tests cover what
the module's own docstrings and type signature promise:

- `EmbeddingClient.embed` batches texts to the provider in order and returns
  vectors in the same order, and short-circuits an empty batch without a
  provider call.
- The real SDK client is constructed lazily (on first `embed`, not on
  `EmbeddingClient()`), so importing/constructing this module never needs an
  API key or network access -- and once built, it is reused rather than
  rebuilt on every call.
- `EmbeddingClient(model=...)` overrides `EMBEDDING_MODEL`; the default picks
  up the configured model.
- `get_embedding_client` is a lazily-created singleton; `set_embedding_client`
  swaps in a fake, and `set_embedding_client(None)` restores a fresh default
  rather than resurrecting the fake.

Assumption: the provider SDK is exercised by monkeypatching `openai.OpenAI`
at the point `EmbeddingClient._client()` imports it, since constructing the
real SDK client requires no I/O (only `.embeddings.create` would), so a fake
substituted there is enough to prove the seam without a live network call.
"""

from __future__ import annotations

import openai
import pytest

from app.services import embedding_client as embedding_client_module
from app.services.embedding_client import (
    EmbeddingClient,
    get_embedding_client,
    set_embedding_client,
)


class _FakeEmbeddingItem:
    def __init__(self, embedding: list[float]) -> None:
        self.embedding = embedding


class _FakeEmbeddingsResponse:
    def __init__(self, vectors: list[list[float]]) -> None:
        self.data = [_FakeEmbeddingItem(v) for v in vectors]


class _FakeEmbeddingsResource:
    def __init__(self, outer: "_FakeOpenAI") -> None:
        self._outer = outer

    def create(self, *, model: str, input: list[str]):  # noqa: A002 -- matches SDK signature
        self._outer.calls.append({"model": model, "input": list(input)})
        # One deterministic, order-preserving vector per input text.
        return _FakeEmbeddingsResponse([[float(len(text)), float(i)] for i, text in enumerate(input)])


class _FakeOpenAI:
    """Stand-in for `openai.OpenAI`, recording construction and calls."""

    instances: list["_FakeOpenAI"] = []

    def __init__(self, *, api_key, base_url):
        self.api_key = api_key
        self.base_url = base_url
        self.calls: list[dict] = []
        self.embeddings = _FakeEmbeddingsResource(self)
        _FakeOpenAI.instances.append(self)


@pytest.fixture(autouse=True)
def _reset_singleton_and_fake_registry():
    """Every test starts from a clean default client and a clean fake registry,
    so one test's singleton swap can't leak into the next."""
    set_embedding_client(None)
    _FakeOpenAI.instances = []
    yield
    set_embedding_client(None)


@pytest.fixture(autouse=True)
def _patch_openai(monkeypatch):
    monkeypatch.setattr(openai, "OpenAI", _FakeOpenAI)


def test_embed_empty_list_returns_empty_without_calling_provider():
    client = EmbeddingClient(model="test-model")

    result = client.embed([])

    assert result == []
    # Never constructed the SDK client at all for an empty batch.
    assert client._sdk_client is None
    assert _FakeOpenAI.instances == []


def test_embed_calls_provider_with_model_and_texts_and_returns_vectors_in_order():
    client = EmbeddingClient(model="test-model")

    vectors = client.embed(["alpha", "bravo-longer"])

    assert len(vectors) == 2
    fake = _FakeOpenAI.instances[0]
    assert fake.calls == [{"model": "test-model", "input": ["alpha", "bravo-longer"]}]
    # Order of returned vectors matches order of input texts.
    assert vectors[0] == [float(len("alpha")), 0.0]
    assert vectors[1] == [float(len("bravo-longer")), 1.0]


def test_sdk_client_constructed_lazily_not_at_instantiation():
    client = EmbeddingClient()

    # Constructing the wrapper must not touch the provider SDK.
    assert client._sdk_client is None
    assert _FakeOpenAI.instances == []

    client.embed(["one"])

    assert client._sdk_client is not None
    assert len(_FakeOpenAI.instances) == 1


def test_sdk_client_is_reused_across_multiple_embed_calls():
    client = EmbeddingClient()

    client.embed(["one"])
    client.embed(["two"])

    # Only one underlying SDK client was ever built, not one per call.
    assert len(_FakeOpenAI.instances) == 1
    fake = _FakeOpenAI.instances[0]
    assert len(fake.calls) == 2


def test_default_model_comes_from_config():
    client = EmbeddingClient()

    assert client.model == embedding_client_module.EMBEDDING_MODEL


def test_explicit_model_overrides_config_default():
    client = EmbeddingClient(model="custom-model")

    assert client.model == "custom-model"


def test_missing_api_key_is_passed_through_as_none_not_empty_string(monkeypatch):
    monkeypatch.setattr(embedding_client_module, "AI_PROVIDER_API_KEY", "")

    client = EmbeddingClient()
    client.embed(["x"])

    fake = _FakeOpenAI.instances[0]
    assert fake.api_key is None


def test_get_embedding_client_returns_same_instance_each_call():
    first = get_embedding_client()
    second = get_embedding_client()

    assert first is second


def test_set_embedding_client_installs_a_fake_in_place_of_the_default():
    fake = EmbeddingClient(model="fake-model")

    set_embedding_client(fake)

    assert get_embedding_client() is fake


def test_set_embedding_client_none_restores_a_fresh_default_not_the_prior_fake():
    original = get_embedding_client()
    fake = EmbeddingClient(model="fake-model")
    set_embedding_client(fake)
    assert get_embedding_client() is fake

    set_embedding_client(None)
    restored = get_embedding_client()

    assert restored is not fake
    assert restored is not original
