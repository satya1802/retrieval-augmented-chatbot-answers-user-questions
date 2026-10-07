"""Hosted chat/generation provider client, behind one injectable, mockable
seam (US-014-1).

Mirrors app/services/embedding_client.py: every call site asks
`get_generation_client()` for the shared instance rather than constructing
its own SDK client, so tests (and `set_generation_client`) swap in a fake
with no network and no API key, and a provider failure surfaces as a single
`GenerationError` type rather than a raw SDK exception leaking out at the
call site (constraint: "All provider access goes through the single
injectable client; no direct SDK calls at a call site").
"""

from __future__ import annotations

from app.config import (
    AI_PROVIDER_API_KEY,
    AI_PROVIDER_BASE_URL,
    CHAT_MODEL,
    GENERATION_TIMEOUT_SECONDS,
)

# AC-045, AC-046, AC-047, AC-049, AC-050, AC-051: the only instructions the
# provider receives besides the retrieved context itself. Forbids outside
# knowledge outright, names the exact insufficient-context sentence AC-049
# requires verbatim, and requires a partially-supported question to be
# split into its supported and explicitly-unsupported parts rather than
# answered in full from guesswork.
SYSTEM_PROMPT = (
    "You are a careful assistant that answers questions using ONLY the "
    "context passages supplied in the user message below. Never use "
    "outside knowledge, never guess, and never state an entity, figure, "
    "date or claim that is not present in the supplied context passages.\n\n"
    "- If the context passages fully support an answer, answer the "
    "question, drawing only on what the passages state.\n"
    "- If the context passages only partially support an answer, answer "
    "the supported part from the context and then explicitly state which "
    "part of the question is not covered by the provided context.\n"
    "- If the context passages do not support any part of an answer, "
    "respond with exactly this sentence and nothing else: "
    "\"I don't have enough information in the provided context to answer "
    'that accurately."'
)


class GenerationError(Exception):
    """Raised when the hosted provider call fails or times out, or returns
    no usable content. Call sites must surface this as an error response --
    never fall back to a fabricated or partial answer (AC-048)."""


class GenerationClient:
    """Thin wrapper over the OpenAI-compatible chat completions endpoint.

    The real SDK client is constructed lazily, on first use, so importing
    this module -- or constructing one to later replace with a fake --
    never requires an API key or network access.
    """

    def __init__(self, model: str | None = None, timeout: float | None = None) -> None:
        self.model = model or CHAT_MODEL
        self.timeout = GENERATION_TIMEOUT_SECONDS if timeout is None else timeout
        self._sdk_client = None

    def _client(self):
        if self._sdk_client is None:
            from openai import OpenAI

            self._sdk_client = OpenAI(
                api_key=AI_PROVIDER_API_KEY or None,
                base_url=AI_PROVIDER_BASE_URL,
                timeout=self.timeout,
            )
        return self._sdk_client

    def generate(self, question: str, context: str) -> str:
        """Synthesise an answer to `question` from `context` alone -- the
        only content passed to the provider besides `SYSTEM_PROMPT`
        (AC-045). Any SDK failure, timeout, or empty response is raised as
        `GenerationError`, never swallowed into a fabricated answer."""
        user_prompt = (
            f"Context passages:\n{context}\n\n"
            f"Question: {question}\n\n"
            "Answer using only the context passages above."
        )
        try:
            response = self._client().chat.completions.create(
                model=self.model,
                timeout=self.timeout,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except Exception as exc:  # noqa: BLE001 -- any provider/SDK failure is one error type
            raise GenerationError("the hosted provider call failed") from exc

        choice = response.choices[0] if response.choices else None
        content = choice.message.content if choice is not None and choice.message else None
        if not content or not content.strip():
            raise GenerationError("the hosted provider returned an empty answer")
        return content.strip()


_default_client: GenerationClient | None = None


def get_generation_client() -> GenerationClient:
    """The shared client call sites use by default."""
    global _default_client
    if _default_client is None:
        _default_client = GenerationClient()
    return _default_client


def set_generation_client(client: GenerationClient | None) -> None:
    """Install a fake (or restore the default with `None`) for tests."""
    global _default_client
    _default_client = client
