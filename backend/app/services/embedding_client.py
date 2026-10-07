"""Hosted embedding provider client, behind one injectable, mockable seam.

Every call site asks `get_embedding_client()` for the shared instance rather
than constructing its own; tests (and `set_embedding_client`) swap that
instance for a fake so the ingestion pipeline runs with no network and no
real API key (constraint: "Embedding provider calls must go through one
injectable/mockable client").
"""

from __future__ import annotations

from app.config import AI_PROVIDER_API_KEY, AI_PROVIDER_BASE_URL, EMBEDDING_MODEL


class EmbeddingClient:
    """Thin wrapper over the OpenAI-compatible embeddings endpoint.

    The real SDK client is constructed lazily, on first use, so importing
    this module (and constructing a client to later replace with a fake)
    never requires an API key or network access.
    """

    def __init__(self, model: str | None = None) -> None:
        self.model = model or EMBEDDING_MODEL
        self._sdk_client = None

    def _client(self):
        if self._sdk_client is None:
            from openai import OpenAI

            self._sdk_client = OpenAI(
                api_key=AI_PROVIDER_API_KEY or None,
                base_url=AI_PROVIDER_BASE_URL,
            )
        return self._sdk_client

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of chunk texts, in order. Empty input embeds to
        an empty list rather than making a zero-item provider call."""
        if not texts:
            return []
        response = self._client().embeddings.create(model=self.model, input=texts)
        return [item.embedding for item in response.data]


_default_client: EmbeddingClient | None = None


def get_embedding_client() -> EmbeddingClient:
    """The shared client call sites use by default."""
    global _default_client
    if _default_client is None:
        _default_client = EmbeddingClient()
    return _default_client


def set_embedding_client(client: EmbeddingClient | None) -> None:
    """Install a fake (or restore the default with `None`) for tests."""
    global _default_client
    _default_client = client
