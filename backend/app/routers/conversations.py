"""Conversations and the question-asking endpoint.

`POST /conversations` accepts an optional `scope_document_ids`, validated at
creation time against the caller's own *ready* documents (AC-039): an id
that is not owned, or not yet ready, is rejected with 422 rather than
silently dropped or silently accepted. `POST /{id}/messages` retrieves
context chunks via `retrieve_context` -- scoped to that conversation, or
with no scope set, to all of the caller's ready documents (AC-040) -- and
passes only those chunks to the hosted generation provider (US-014-1,
extended for derived outputs and safety-sensitive requests by US-018-1): a
grounded response with citations, the exact insufficient-context string, a
refusal with no citations, or a 502 error when the provider itself fails.
It never invents an answer and never falls back to documents outside the
scope.

US-020-1 adds a streaming variant of the same endpoint: a client that sends
`Accept: text/event-stream` or `?stream=1` gets Server-Sent Events --
incremental `delta` events as the provider's answer arrives, followed by a
terminal `done` event carrying the persisted message and its citations, or
an `error` event when generation fails part-way. A caller that sends
neither gets the exact same JSON response as before (`AskQuestionResponse`)
-- the streaming branch is additive, not a replacement.

US-022-1 makes the retrieval driving a follow-up question
conversation-aware: before a question is embedded and retrieved on, it is
rewritten into a standalone query from that same conversation's own prior
user/assistant turns (app.services.query_rewrite.build_standalone_query).
A conversation's first question -- no prior turns -- is used verbatim, with
no rewrite call at all; any failure rewriting degrades to the raw question,
never a 500. The rewritten query drives retrieval only -- the persisted
user message, the generation prompt, and every response shape are
unchanged; a client cannot tell this happened except that pronouns and
elided subjects in a follow-up now resolve against the conversation's own
history instead of either being ignored or bleeding in from elsewhere.
"""

import json
import uuid
from collections.abc import Generator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import MONTHLY_QUESTION_CAP
from app.database import get_db
from app.dependencies import get_owned_or_404
from app.models import Conversation, Document, Message, MessageCitation, User
from app.schemas import (
    AskQuestionRequest,
    AskQuestionResponse,
    CitationOut,
    ConversationCreateRequest,
    ConversationCreateResponse,
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationOut,
    MessageOut,
)
from app.security import get_current_user_id
from app.services import usage_service
from app.services.generation_client import REFUSAL_MESSAGE, GenerationError, get_generation_client
from app.services.query_rewrite import build_standalone_query
from app.services.retrieval import READY_STATUS, ContextChunk, retrieve_context

router = APIRouter(prefix="/conversations", tags=["conversations"])

_CurrentUserId = Annotated[uuid.UUID, Depends(get_current_user_id)]
_DbSession = Annotated[Session, Depends(get_db)]

# AC-049: the exact string the Answer section must contain -- and nothing
# else -- whenever the retrieved (or generated-from) context is inadequate
# to answer the question, whether that is because retrieval found nothing
# at all or because the provider itself determined the retrieved chunks
# don't support an answer. Replaces the earlier, non-conforming wording.
INSUFFICIENT_CONTEXT_MESSAGE = (
    "I don't have enough information in the provided context to answer that accurately."
)
EMPTY_LIBRARY_MESSAGE = (
    "Your document library is empty or still processing. "
    "Upload a document -- or wait for it to finish processing -- before asking a question."
)
# AC-048: the 502 surfaced when the hosted provider call fails or times
# out -- never a fabricated answer and never a partial, unmarked one.
_GENERATION_FAILURE_DETAIL = (
    "The answer could not be generated because the AI provider failed. Please try again."
)

_SCOPE_VALIDATION_DETAIL = "scope_document_ids must reference the caller's own ready documents"
_EMPTY_QUESTION_DETAIL = "question must not be empty"

# AC-065: no citations are attached to a refusal (reveal-system-prompt /
# hidden-instructions / chain-of-thought request) any more than to the
# insufficient-context sentence -- both are "the model did not answer from
# the context", so neither carries a citation list.
_UNCITED_ANSWERS = frozenset({INSUFFICIENT_CONTEXT_MESSAGE, REFUSAL_MESSAGE})


@router.get("", response_model=ConversationListResponse)
async def list_conversations(user_id: _CurrentUserId, db: _DbSession) -> ConversationListResponse:
    """AC-073, AC-075: only the caller's own conversations, filtered by
    owner_id at the query level, not after serialisation."""
    conversations = (
        db.query(Conversation)
        .filter(Conversation.owner_id == user_id)
        .order_by(Conversation.created_at.desc())
        .all()
    )
    return ConversationListResponse(
        conversations=[ConversationOut.model_validate(c) for c in conversations]
    )


@router.post("", response_model=ConversationCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    body: ConversationCreateRequest, user_id: _CurrentUserId, db: _DbSession
) -> ConversationCreateResponse:
    """AC-039, AC-076: an optional document scope at creation time, which
    must be the caller's own, ready documents -- anything else (unowned,
    unknown, or still processing/failed) is rejected with 422 rather than
    silently stored or silently dropped, since a scope that silently
    narrowed to less than the caller asked for would be worse than an
    error."""
    if body.scope_document_ids:
        requested_ids = list(dict.fromkeys(body.scope_document_ids))  # de-dup, preserve order
        owned_ready = (
            db.query(Document)
            .filter(Document.id.in_(requested_ids), Document.owner_id == user_id)
            .all()
        )
        owned_ready_by_id = {doc.id: doc for doc in owned_ready}
        for doc_id in requested_ids:
            doc = owned_ready_by_id.get(doc_id)
            if doc is None or doc.status != READY_STATUS:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=_SCOPE_VALIDATION_DETAIL,
                )
        scope_ids = [str(doc_id) for doc_id in requested_ids]
    else:
        scope_ids = []

    conversation = Conversation(owner_id=user_id, title=body.title, scope_document_ids=scope_ids)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return ConversationCreateResponse(conversation=ConversationOut.model_validate(conversation))


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: uuid.UUID, user_id: _CurrentUserId, db: _DbSession
) -> ConversationDetailResponse:
    """AC-073, AC-008: owned conversation with its messages; 404 on a
    mismatch via the single owner-scoped lookup helper."""
    conversation = get_owned_or_404(
        db, Conversation, conversation_id, user_id, detail="conversation not found"
    )
    messages = [MessageOut.model_validate(message) for message in conversation.messages]
    return ConversationDetailResponse(
        conversation=ConversationOut.model_validate(conversation), messages=messages
    )


def _build_context_text(chunks: list[ContextChunk]) -> str:
    """The only content passed to the generation provider besides the
    system prompt (AC-045) -- each retrieved chunk, numbered and
    attributed to its source document, so the model's answer can be
    checked against exactly these passages and nothing else."""
    sections = [
        f'[{idx}] (from "{chunk.document_title}"): {chunk.text}'
        for idx, chunk in enumerate(chunks, start=1)
    ]
    return "\n\n".join(sections)


def _prior_turns(db: Session, conversation_id: uuid.UUID) -> list[tuple[str, str]]:
    """The target conversation's own prior user/assistant turns, in order,
    and nothing else (US-022-1) -- filtered by `conversation_id` at the
    query level, so a rewrite can never draw on another conversation's (or
    another user's) history. Called before the new user turn is persisted,
    so it never includes the question currently being asked."""
    rows = (
        db.query(Message.role, Message.content)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
        .all()
    )
    return [(role, content) for role, content in rows]


def _wants_stream(request: Request) -> bool:
    """A client opts into Server-Sent Events via `?stream=1` or
    `Accept: text/event-stream` (US-020-1); anyone who sends neither gets
    the original, byte-compatible JSON response."""
    if request.query_params.get("stream") == "1":
        return True
    accept = request.headers.get("accept", "")
    return "text/event-stream" in accept


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _persist_simple_answer(db: Session, conversation: Conversation, content: str) -> Message:
    """Persist a fixed, non-generated answer (empty-library or
    insufficient-context) with no citations, identically to the
    non-streaming path."""
    assistant_message = Message(
        conversation_id=conversation.id, role="assistant", content=content, is_incomplete=False
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)
    return assistant_message


def _stream_simple_answer(
    db: Session, conversation: Conversation, content: str
) -> Generator[str, None, None]:
    assistant_message = _persist_simple_answer(db, conversation, content)
    yield _sse_event("delta", {"text": content})
    yield _sse_event(
        "done",
        {
            "message": MessageOut.model_validate(assistant_message).model_dump(mode="json"),
            "citations": [],
        },
    )


def _stream_generated_answer(
    db: Session,
    conversation: Conversation,
    question: str,
    retrieved: list[ContextChunk],
) -> Generator[str, None, None]:
    """AC-070 (backend half): stream the provider's answer token by token.
    On a mid-stream failure, whatever text was already emitted is persisted
    verbatim (never completed or fabricated) with `is_incomplete=True` and
    no citations, and a terminal `error` event names that message's id so
    the client can render it as incomplete; re-asking creates a brand new
    assistant message, since nothing here mutates or reuses this one."""
    context_text = _build_context_text(retrieved)
    accumulated = ""
    try:
        for delta_text in get_generation_client().generate_stream(question, context_text):
            accumulated += delta_text
            yield _sse_event("delta", {"text": delta_text})
    except GenerationError:
        assistant_message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=accumulated,
            is_incomplete=True,
        )
        db.add(assistant_message)
        db.commit()
        db.refresh(assistant_message)
        yield _sse_event(
            "error",
            {
                "detail": _GENERATION_FAILURE_DETAIL,
                "message_id": str(assistant_message.id),
                "is_incomplete": True,
            },
        )
        return

    content = accumulated
    assistant_message = Message(
        conversation_id=conversation.id, role="assistant", content=content, is_incomplete=False
    )
    db.add(assistant_message)
    db.flush()

    # AC-050, AC-065: no citations on a response that is exactly the
    # insufficient-context sentence or the system-prompt-disclosure refusal.
    citation_chunks = retrieved if content.strip() not in _UNCITED_ANSWERS else []
    citation_rows = [
        MessageCitation(
            message_id=assistant_message.id,
            chunk_id=chunk.chunk_id,
            document_title_snapshot=chunk.document_title,
            chunk_position=chunk.position,
        )
        for chunk in citation_chunks
    ]
    db.add_all(citation_rows)
    db.commit()
    db.refresh(assistant_message)

    yield _sse_event(
        "done",
        {
            "message": MessageOut.model_validate(assistant_message).model_dump(mode="json"),
            "citations": [
                CitationOut.model_validate(c).model_dump(mode="json") for c in citation_rows
            ],
        },
    )


@router.post("/{conversation_id}/messages", response_model=AskQuestionResponse)
async def ask_question(
    conversation_id: uuid.UUID,
    body: AskQuestionRequest,
    request: Request,
    user_id: _CurrentUserId,
    db: _DbSession,
) -> AskQuestionResponse | StreamingResponse:
    """AC-039, AC-040, AC-041, AC-038, AC-032, AC-012, AC-009, AC-045
    through AC-051, AC-059 through AC-066, AC-070, AC-073 through AC-076:
    ownership and the monthly question cap are both enforced before
    anything else runs, including before any embedding/retrieval/generation
    call (AC-012), and an empty or whitespace-only question is rejected
    with 422 before any of that too. Retrieval is then scoped to exactly
    `conversation.scope_document_ids` when a scope is set (AC-039) -- so
    chunks from an unselected document are never in the context set -- or
    to all of the caller's ready documents when no scope is set (AC-040).

    US-022-1: the query retrieval runs against is not the raw question
    verbatim once the conversation already has prior turns -- it is that
    question rewritten into a standalone query from exactly this
    conversation's own prior user/assistant turns
    (`app.services.query_rewrite.build_standalone_query`), so a follow-up's
    pronouns and elided subjects resolve against its own conversation's
    history and never another conversation's or user's. A conversation's
    first question has no prior turns, so it is used verbatim with no
    rewrite call at all; a rewrite failure degrades to the raw question
    rather than failing the request. Only the query driving retrieval
    changes -- the persisted user message is always the raw question, and
    the generation prompt is built from the retrieved chunks exactly as
    before.

    A caller with no ready documents at all in the relevant scope never
    reaches retrieval -- let alone an embedding or generation provider call
    -- and instead gets a response stating the library is empty or still
    processing (AC-038). When retrieval returns chunks, those chunks --
    and only those chunks -- are passed to the hosted generation provider
    (AC-045), whose instructions (`SYSTEM_PROMPT`) also cover derived
    outputs -- summaries, steps, recommendations, comparisons -- and
    safety-sensitive requests -- ambiguity, verbatim quoting, system-prompt
    disclosure, out-of-scope questions -- with the same context-only
    grounding and traceability as a direct answer.

    A caller that sends `Accept: text/event-stream` or `?stream=1` gets the
    same decision (empty-library / insufficient-context / generated
    answer) delivered as Server-Sent Events instead of a single JSON body
    (US-020-1); anyone else gets the original `AskQuestionResponse`
    byte-compatibly. The assistant message and its citations are only
    persisted after a successful generation call in the non-streaming
    path -- a provider failure or timeout raises a 502 instead, with no
    assistant message, partial or otherwise, stored (AC-048), and the
    question already counted against the caller's monthly cap below is
    refunded, since no answer was ever produced for it. In the streaming
    path a provider failure mid-answer instead persists the partial text
    already emitted, flagged `is_incomplete=True`, and terminates the
    stream with an `error` event (AC-070) -- that turn did produce and
    store something, so its question is not refunded.
    """
    conversation = get_owned_or_404(
        db, Conversation, conversation_id, user_id, detail="conversation not found"
    )

    if not body.question.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=_EMPTY_QUESTION_DETAIL
        )

    user = db.get(User, user_id)
    usage_service.enforce_question_capacity(db, user, cap=MONTHLY_QUESTION_CAP)

    # US-022-1: captured before the new user turn is persisted below, and
    # filtered to this conversation_id alone, so a rewrite can only ever
    # see this conversation's own prior turns.
    prior_turns = _prior_turns(db, conversation.id)

    scope_ids = (
        [uuid.UUID(doc_id) for doc_id in conversation.scope_document_ids]
        if conversation.scope_document_ids
        else None
    )

    ready_documents_query = db.query(Document).filter(
        Document.owner_id == user_id, Document.status == READY_STATUS
    )
    if scope_ids:
        ready_documents_query = ready_documents_query.filter(Document.id.in_(scope_ids))
    has_ready_documents = db.query(ready_documents_query.exists()).scalar()

    usage_service.increment_question_count(db, user)

    user_message = Message(conversation_id=conversation.id, role="user", content=body.question)
    db.add(user_message)
    db.commit()

    retrieval_query = build_standalone_query(prior_turns, body.question)

    retrieved: list[ContextChunk] = []
    if has_ready_documents:
        retrieved = retrieve_context(db, user_id, retrieval_query, document_ids=scope_ids)

    if _wants_stream(request):
        if not has_ready_documents:
            generator = _stream_simple_answer(db, conversation, EMPTY_LIBRARY_MESSAGE)
        elif not retrieved:
            generator = _stream_simple_answer(db, conversation, INSUFFICIENT_CONTEXT_MESSAGE)
        else:
            generator = _stream_generated_answer(db, conversation, body.question, retrieved)
        return StreamingResponse(generator, media_type="text/event-stream")

    citation_chunks: list[ContextChunk] = []
    if not has_ready_documents:
        content = EMPTY_LIBRARY_MESSAGE
    elif not retrieved:
        content = INSUFFICIENT_CONTEXT_MESSAGE
    else:
        context_text = _build_context_text(retrieved)
        try:
            content = get_generation_client().generate(body.question, context_text)
        except GenerationError as exc:
            # AC-012, AC-048: no answer was produced and no assistant
            # message will be stored for this turn -- refund the question
            # `usage_service.increment_question_count` already counted
            # above, so a transient provider failure does not silently
            # cost the caller a real question.
            usage_service.decrement_question_count(db, user)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=_GENERATION_FAILURE_DETAIL,
            ) from exc
        # AC-050, AC-065: no sources attached to a response the
        # provider itself judged unsupported by the retrieved context,
        # nor to a refusal to disclose the system prompt / hidden
        # instructions / chain-of-thought.
        if content.strip() not in _UNCITED_ANSWERS:
            citation_chunks = retrieved

    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=content,
        is_incomplete=False,
    )
    db.add(assistant_message)
    db.flush()

    citation_rows = [
        MessageCitation(
            message_id=assistant_message.id,
            chunk_id=chunk.chunk_id,
            document_title_snapshot=chunk.document_title,
            chunk_position=chunk.position,
        )
        for chunk in citation_chunks
    ]
    db.add_all(citation_rows)
    db.commit()
    db.refresh(assistant_message)

    return AskQuestionResponse(
        message=MessageOut.model_validate(assistant_message),
        citations=[CitationOut.model_validate(c) for c in citation_rows],
    )
