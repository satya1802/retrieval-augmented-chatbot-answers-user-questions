"""Standalone-query rewriting for follow-up questions (US-022-1).

A follow-up like "what about its capacity?" means nothing to embedding-based
retrieval on its own -- the pronoun and the elided subject only resolve
against *that conversation's* prior turns. This module rewrites such a
follow-up into a standalone query, using only the target conversation's own
prior user/assistant turns, before it is ever embedded or used to retrieve
context.

The rewrite call itself goes through `get_generation_client()` -- the same
hosted provider seam `POST /conversations/{id}/messages` already uses for
answer generation (US-014-1) -- rather than a second provider path
(constraint: reuse the existing injectable clients). The rewriter *wrapper*
around that call is its own seam, `get_query_rewriter()` /
`set_query_rewriter()`, mirroring `set_generation_client`, so a test can
install a fake rewriter with no network call and assert exactly what
history it was given, independently of faking the generation client itself.

`build_standalone_query` is the only entry point call sites need:

- No prior turns (a conversation's first question) -- the raw question is
  used verbatim; the rewriter is never invoked, so a first question never
  costs an extra provider call.
- Prior turns exist -- the rewriter is called with exactly that
  conversation's own history and the raw follow-up; its result becomes the
  query passed to retrieval.
- Any failure rewriting (provider error, empty/unusable result, or any
  other exception from a fake in tests) degrades to the raw follow-up text
  itself -- never a 500, never blocks the question from being answered.
"""

from __future__ import annotations

from app.services.generation_client import get_generation_client


class QueryRewriter:
    """Thin wrapper over the generation client's rewrite call. Exists as
    its own class -- rather than calling `get_generation_client()` directly
    from `build_standalone_query` -- purely so tests can install a fake via
    `set_query_rewriter` without also having to fake answer generation."""

    def rewrite(self, history: list[tuple[str, str]], follow_up: str) -> str:
        return get_generation_client().rewrite_query(history, follow_up)


_default_rewriter: QueryRewriter | None = None


def get_query_rewriter() -> QueryRewriter:
    """The shared rewriter call sites use by default."""
    global _default_rewriter
    if _default_rewriter is None:
        _default_rewriter = QueryRewriter()
    return _default_rewriter


def set_query_rewriter(rewriter: QueryRewriter | None) -> None:
    """Install a fake (or restore the default with `None`) for tests, in
    the style of `set_generation_client`."""
    global _default_rewriter
    _default_rewriter = rewriter


def build_standalone_query(history: list[tuple[str, str]], follow_up: str) -> str:
    """Return the query retrieval should embed for `follow_up`.

    `history` must already be filtered to exactly the target conversation's
    own prior turns, in order -- this function does not filter or fetch
    anything itself, so the caller's query-level `conversation_id` (and
    hence owner) scoping is the only scoping that ever applies.

    With no prior turns, returns `follow_up` verbatim and never calls the
    rewriter at all. Otherwise calls the rewriter and falls back to
    `follow_up` verbatim on any failure -- a missing/empty result, a
    provider error, or any other exception -- so a rewriting failure never
    surfaces as a 500 and never blocks the question being answered.
    """
    if not history:
        return follow_up

    try:
        rewritten = get_query_rewriter().rewrite(history, follow_up)
    except Exception:  # noqa: BLE001 -- any rewrite failure degrades to the raw question
        return follow_up

    if not rewritten or not rewritten.strip():
        return follow_up
    return rewritten.strip()
