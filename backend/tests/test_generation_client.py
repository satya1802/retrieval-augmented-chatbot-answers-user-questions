"""Unit tests for app/services/generation_client.py.

Mirrors the pattern in test_embedding_client.py: the real OpenAI SDK is
never imported by any test that doesn't explicitly want to see how the
SDK client would be constructed -- `generate()`, `generate_stream()` and
`rewrite_query()` are each exercised against a fake SDK client installed
directly as `GenerationClient._sdk_client` (the same seam `_client()`
lazily populates), and construction itself is exercised by monkeypatching
`openai.OpenAI` so no network access or API key is ever required.
"""

from unittest.mock import MagicMock

import pytest

from app.services import generation_client as module
from app.services.generation_client import (
    REFUSAL_MESSAGE,
    REWRITE_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    GenerationClient,
    GenerationError,
    get_generation_client,
    set_generation_client,
)


@pytest.fixture(autouse=True)
def _reset_shared_client():
    """Every test starts and ends with no installed fake, so one test's
    `set_generation_client` can never leak into the next."""
    set_generation_client(None)
    yield
    set_generation_client(None)


def _fake_completion(content) -> MagicMock:
    """A stand-in for the OpenAI SDK's non-streaming chat completion
    response -- a `.choices` list whose items expose `.message.content`."""
    message = MagicMock(content=content)
    choice = MagicMock(message=message)
    response = MagicMock(choices=[choice])
    sdk = MagicMock()
    sdk.chat.completions.create.return_value = response
    return sdk


def _fake_completion_no_choices() -> MagicMock:
    response = MagicMock(choices=[])
    sdk = MagicMock()
    sdk.chat.completions.create.return_value = response
    return sdk


def _fake_chunk(content):
    """A stand-in for one streamed chunk -- `.choices[0].delta.content`."""
    delta = MagicMock(content=content)
    choice = MagicMock(delta=delta)
    return MagicMock(choices=[choice])


def _fake_chunk_no_choices():
    return MagicMock(choices=[])


def _fake_stream_sdk(chunks) -> MagicMock:
    """A stand-in for the SDK when `stream=True`: `.create(...)` returns an
    iterable of chunk-like objects."""
    sdk = MagicMock()
    sdk.chat.completions.create.return_value = iter(chunks)
    return sdk


def _raising_stream_sdk(chunks_then_raise):
    """An iterable that yields `chunks_then_raise` and then raises partway
    through, to simulate a provider failure mid-stream."""

    def _gen():
        for chunk in chunks_then_raise:
            yield chunk
        raise RuntimeError("connection reset mid-stream")

    sdk = MagicMock()
    sdk.chat.completions.create.return_value = _gen()
    return sdk


# -- generate() -----------------------------------------------------------


def test_generate_returns_the_stripped_answer_content():
    client = GenerationClient()
    client._sdk_client = _fake_completion("  The answer is 42.  ")

    result = client.generate("What is the answer?", "[1] Some context.")

    assert result == "The answer is 42."


def test_generate_sends_only_system_prompt_and_context_plus_question():
    client = GenerationClient()
    client._sdk_client = _fake_completion("answer")

    client.generate("What is X?", "[1] X is Y.")

    _, kwargs = client._sdk_client.chat.completions.create.call_args
    messages = kwargs["messages"]
    assert messages[0] == {"role": "system", "content": SYSTEM_PROMPT}
    assert messages[1]["role"] == "user"
    assert "[1] X is Y." in messages[1]["content"]
    assert "What is X?" in messages[1]["content"]


def test_generate_uses_the_configured_model_and_timeout():
    client = GenerationClient(model="my-chat-model", timeout=12.5)
    client._sdk_client = _fake_completion("answer")

    client.generate("question", "context")

    _, kwargs = client._sdk_client.chat.completions.create.call_args
    assert kwargs["model"] == "my-chat-model"
    assert kwargs["timeout"] == 12.5


def test_generate_defaults_to_the_app_configured_chat_model():
    client = GenerationClient()
    assert client.model == module.CHAT_MODEL


def test_generate_sdk_failure_raises_generation_error_not_the_raw_exception():
    client = GenerationClient()
    sdk = MagicMock()
    sdk.chat.completions.create.side_effect = RuntimeError("boom")
    client._sdk_client = sdk

    with pytest.raises(GenerationError):
        client.generate("question", "context")


def test_generate_empty_answer_raises_generation_error():
    client = GenerationClient()
    client._sdk_client = _fake_completion("")

    with pytest.raises(GenerationError):
        client.generate("question", "context")


def test_generate_whitespace_only_answer_raises_generation_error():
    client = GenerationClient()
    client._sdk_client = _fake_completion("   \n\t  ")

    with pytest.raises(GenerationError):
        client.generate("question", "context")


def test_generate_no_choices_raises_generation_error():
    client = GenerationClient()
    client._sdk_client = _fake_completion_no_choices()

    with pytest.raises(GenerationError):
        client.generate("question", "context")


# -- generate_stream() -----------------------------------------------------


def test_generate_stream_yields_the_deltas_in_order():
    client = GenerationClient()
    client._sdk_client = _fake_stream_sdk(
        [_fake_chunk("The "), _fake_chunk("answer "), _fake_chunk("is 42.")]
    )

    result = list(client.generate_stream("question", "context"))

    assert result == ["The ", "answer ", "is 42."]


def test_generate_stream_sends_stream_true_and_the_same_system_prompt():
    client = GenerationClient()
    client._sdk_client = _fake_stream_sdk([_fake_chunk("hi")])

    list(client.generate_stream("question", "context"))

    _, kwargs = client._sdk_client.chat.completions.create.call_args
    assert kwargs["stream"] is True
    assert kwargs["messages"][0] == {"role": "system", "content": SYSTEM_PROMPT}


def test_generate_stream_skips_chunks_with_no_choices_or_empty_delta():
    client = GenerationClient()
    client._sdk_client = _fake_stream_sdk(
        [_fake_chunk_no_choices(), _fake_chunk(""), _fake_chunk(None), _fake_chunk("real text")]
    )

    result = list(client.generate_stream("question", "context"))

    assert result == ["real text"]


def test_generate_stream_calling_it_does_not_start_the_call_until_iterated():
    # A generator function's body only runs on first `next()` -- so
    # constructing the generator must never touch the SDK, even if the
    # underlying call would fail.
    client = GenerationClient()
    sdk = MagicMock()
    sdk.chat.completions.create.side_effect = RuntimeError("boom")
    client._sdk_client = sdk

    generator = client.generate_stream("question", "context")  # must not raise

    sdk.chat.completions.create.assert_not_called()
    with pytest.raises(GenerationError):
        next(generator)


def test_generate_stream_failure_to_start_raises_generation_error_on_iteration():
    client = GenerationClient()
    sdk = MagicMock()
    sdk.chat.completions.create.side_effect = RuntimeError("boom")
    client._sdk_client = sdk

    with pytest.raises(GenerationError):
        list(client.generate_stream("question", "context"))


def test_generate_stream_failure_mid_stream_raises_generation_error():
    client = GenerationClient()
    client._sdk_client = _raising_stream_sdk([_fake_chunk("partial ")])

    collected = []
    with pytest.raises(GenerationError):
        for delta in client.generate_stream("question", "context"):
            collected.append(delta)

    # Text emitted before the failure is not lost -- the caller sees it,
    # then sees the error, rather than a silently truncated stream.
    assert collected == ["partial "]


def test_generate_stream_entirely_empty_stream_raises_generation_error():
    client = GenerationClient()
    client._sdk_client = _fake_stream_sdk([])

    with pytest.raises(GenerationError):
        list(client.generate_stream("question", "context"))


def test_generate_stream_stream_of_only_empty_deltas_raises_generation_error():
    client = GenerationClient()
    client._sdk_client = _fake_stream_sdk([_fake_chunk(""), _fake_chunk(None)])

    with pytest.raises(GenerationError):
        list(client.generate_stream("question", "context"))


# -- rewrite_query() -------------------------------------------------------


def test_rewrite_query_returns_the_stripped_rewritten_question():
    client = GenerationClient()
    client._sdk_client = _fake_completion("  What is the capital of France?  ")

    result = client.rewrite_query(
        [("user", "Tell me about France"), ("assistant", "France is a country in Europe.")],
        "What is its capital?",
    )

    assert result == "What is the capital of France?"


def test_rewrite_query_sends_the_rewrite_system_prompt_not_the_answer_prompt():
    client = GenerationClient()
    client._sdk_client = _fake_completion("standalone question")

    client.rewrite_query([("user", "Tell me about France")], "What is its capital?")

    _, kwargs = client._sdk_client.chat.completions.create.call_args
    messages = kwargs["messages"]
    assert messages[0] == {"role": "system", "content": REWRITE_SYSTEM_PROMPT}
    assert messages[0]["content"] != SYSTEM_PROMPT


def test_rewrite_query_includes_the_history_and_the_follow_up_in_the_user_message():
    client = GenerationClient()
    client._sdk_client = _fake_completion("standalone question")

    client.rewrite_query(
        [("user", "Tell me about France"), ("assistant", "France is in Europe.")],
        "What is its capital?",
    )

    _, kwargs = client._sdk_client.chat.completions.create.call_args
    user_content = kwargs["messages"][1]["content"]
    assert "Tell me about France" in user_content
    assert "France is in Europe." in user_content
    assert "What is its capital?" in user_content


def test_rewrite_query_with_no_history_still_sends_the_follow_up():
    client = GenerationClient()
    client._sdk_client = _fake_completion("standalone question")

    client.rewrite_query([], "What is its capital?")

    _, kwargs = client._sdk_client.chat.completions.create.call_args
    assert "What is its capital?" in kwargs["messages"][1]["content"]


def test_rewrite_query_sdk_failure_raises_generation_error():
    client = GenerationClient()
    sdk = MagicMock()
    sdk.chat.completions.create.side_effect = RuntimeError("boom")
    client._sdk_client = sdk

    with pytest.raises(GenerationError):
        client.rewrite_query([("user", "hi")], "and then?")


def test_rewrite_query_empty_response_raises_generation_error():
    client = GenerationClient()
    client._sdk_client = _fake_completion("")

    with pytest.raises(GenerationError):
        client.rewrite_query([("user", "hi")], "and then?")


def test_rewrite_query_no_choices_raises_generation_error():
    client = GenerationClient()
    client._sdk_client = _fake_completion_no_choices()

    with pytest.raises(GenerationError):
        client.rewrite_query([("user", "hi")], "and then?")


# -- the system prompts and refusal sentence, as literal constants --------


def test_system_prompt_names_the_exact_insufficient_context_sentence():
    assert (
        "I don't have enough information in the provided context to answer "
        'that accurately."' in SYSTEM_PROMPT
    )


def test_system_prompt_embeds_the_exact_refusal_message_for_prompt_disclosure():
    assert REFUSAL_MESSAGE in SYSTEM_PROMPT


def test_rewrite_system_prompt_forbids_answering_and_adding_information():
    assert "Do not answer the question" in REWRITE_SYSTEM_PROMPT
    assert "Do not add any fact" in REWRITE_SYSTEM_PROMPT


# -- lazy SDK construction (mirrors test_embedding_client.py) --------------


def test_constructing_a_client_never_touches_the_sdk(monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("OpenAI SDK constructed before any call")

    monkeypatch.setattr("openai.OpenAI", _boom)

    GenerationClient()  # must not raise -- construction alone needs no SDK, no key


def test_sdk_client_is_constructed_with_configured_credentials(monkeypatch):
    captured = {}

    class _FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("openai.OpenAI", _FakeOpenAI)
    monkeypatch.setattr(module, "AI_PROVIDER_API_KEY", "test-key")
    monkeypatch.setattr(module, "AI_PROVIDER_BASE_URL", "https://example.test/v1")

    sdk = GenerationClient()._client()

    assert isinstance(sdk, _FakeOpenAI)
    assert captured["api_key"] == "test-key"
    assert captured["base_url"] == "https://example.test/v1"


def test_empty_api_key_is_passed_to_the_sdk_as_none(monkeypatch):
    captured = {}

    class _FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("openai.OpenAI", _FakeOpenAI)
    monkeypatch.setattr(module, "AI_PROVIDER_API_KEY", "")

    GenerationClient()._client()

    assert captured["api_key"] is None


def test_sdk_client_is_constructed_once_and_reused(monkeypatch):
    constructions = []

    class _FakeOpenAI:
        def __init__(self, **kwargs):
            constructions.append(kwargs)

    monkeypatch.setattr("openai.OpenAI", _FakeOpenAI)

    client = GenerationClient()
    first = client._client()
    second = client._client()

    assert first is second
    assert len(constructions) == 1


# -- the shared, swappable client seam ------------------------------------


def test_get_generation_client_returns_the_same_instance_every_call():
    first = get_generation_client()
    second = get_generation_client()

    assert first is second


def test_set_generation_client_installs_a_fake_for_call_sites():
    fake = GenerationClient()

    set_generation_client(fake)

    assert get_generation_client() is fake


def test_set_generation_client_none_restores_a_fresh_default():
    fake = GenerationClient()
    set_generation_client(fake)

    set_generation_client(None)
    restored = get_generation_client()

    assert restored is not fake
    assert isinstance(restored, GenerationClient)
