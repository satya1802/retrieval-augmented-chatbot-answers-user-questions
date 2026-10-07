"""Auth endpoints: registration, verification, login, password reset.

None of these require a token (see the api spec), so no router-level
dependency is attached. Every handler is a stub: it validates the request
shape FastAPI already knows from `app.schemas` and answers 501, so the
development sprint implements account creation, email dispatch, credential
checking and token signing against a route that already exists, already
appears in the OpenAPI document, and already matches the approved
request/response contract -- rather than having to create the route too.
"""

from fastapi import APIRouter, HTTPException, status

from app.schemas import (
    LoginRequest,
    LoginResponse,
    MessageResponse,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RegisterRequest,
    VerifyRequest,
    VerifyResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])

_NOT_IMPLEMENTED = "Not implemented yet -- stub endpoint for the development sprint."


@router.post("/register", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED)
async def register(body: RegisterRequest) -> MessageResponse:
    """AC-001, AC-003: create an unverified account and email a verification
    link; a neutral response either way so existing emails are not leaked."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)


@router.post("/verify", response_model=VerifyResponse)
async def verify(body: VerifyRequest) -> VerifyResponse:
    """AC-002: mark the account verified via the emailed, single-use token."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest) -> LoginResponse:
    """AC-004, AC-005, AC-006: sign in a verified user; a generic error for
    both bad credentials and an unverified account so neither is leaked."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)


@router.post(
    "/password-reset/request",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def password_reset_request(body: PasswordResetRequest) -> MessageResponse:
    """AC-007: send a self-service reset link."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)


@router.post("/password-reset/confirm", response_model=MessageResponse)
async def password_reset_confirm(body: PasswordResetConfirmRequest) -> MessageResponse:
    """AC-007: set a new password via a single-use reset token."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_NOT_IMPLEMENTED)
