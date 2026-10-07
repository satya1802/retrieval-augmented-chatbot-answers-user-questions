"""Pydantic request/response schemas for the approved API spec.

One class per shape the spec names, named after it, so a router module reads
as a direct translation of the ticket's endpoint table.
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field

# ---------------------------------------------------------------- auth ----


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class VerifyRequest(BaseModel):
    token: str


class VerifyResponse(BaseModel):
    verified: bool


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    token: str
    new_password: str


class MessageResponse(BaseModel):
    message: str


# ------------------------------------------------------------- usage ------


class UsageResponse(BaseModel):
    document_count: int
    documents_cap: int
    remaining_questions: int
    reset_date: date


# ---------------------------------------------------------- documents -----


class DocumentOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    title: str
    file_type: str
    status: str
    failure_reason: str | None = None
    uploaded_at: datetime


class RejectedFileOut(BaseModel):
    """A file submitted alongside others in the same upload that was not
    stored or turned into a Document row (AC-015, AC-017)."""

    filename: str
    reason: str


class DocumentCreateResponse(BaseModel):
    documents: list[DocumentOut]
    rejected: list[RejectedFileOut] = []


class DocumentListResponse(BaseModel):
    documents: list[DocumentOut]


class DocumentRenameRequest(BaseModel):
    # max_length matches `documents.title varchar(300)` (app.models.Document)
    # -- without it, a title near that bound round-trips fine on SQLite
    # (which does not enforce VARCHAR length) but raises an unhandled error
    # on Postgres, where the column actually enforces it.
    title: str = Field(min_length=1, max_length=300)


# ------------------------------------------------------- conversations ----


class ConversationOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    title: str | None = None
    scope_document_ids: list[uuid.UUID] = []
    created_at: datetime


class ConversationListResponse(BaseModel):
    conversations: list[ConversationOut]


class ConversationCreateRequest(BaseModel):
    # max_length matches `conversations.title varchar(300)` (same reasoning
    # as DocumentRenameRequest.title above).
    title: str | None = Field(default=None, max_length=300)
    scope_document_ids: list[uuid.UUID] | None = None


class ConversationCreateResponse(BaseModel):
    conversation: ConversationOut


class CitationOut(BaseModel):
    model_config = {"from_attributes": True}

    chunk_id: uuid.UUID | None = None
    document_title_snapshot: str
    chunk_position: int


class MessageOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    role: str
    content: str
    is_incomplete: bool
    created_at: datetime
    citations: list[CitationOut] = []


class ConversationDetailResponse(BaseModel):
    conversation: ConversationOut
    messages: list[MessageOut]


class AskQuestionRequest(BaseModel):
    question: str = Field(min_length=1)


class AskQuestionResponse(BaseModel):
    message: MessageOut
    citations: list[CitationOut]


# ------------------------------------------------------------- chunks -----


class ChunkDetailResponse(BaseModel):
    text: str
    document_title: str
    position: int
