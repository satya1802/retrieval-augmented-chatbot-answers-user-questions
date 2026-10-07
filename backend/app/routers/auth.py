"""Auth endpoints: registration, verification, login, password reset.

None of these require a token (see the api spec), so no router-level
dependency is attached.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
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
from app.security import (
    create_access_token,
    hash_password,
    validate_password_strength,
    verify_password,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

_DbSession = Annotated[Session, Depends(get_db)]

# Identical regardless of whether the email was already registered (AC-003) --
# the whole point is that this response leaks nothing about account existence.
_REGISTER_MESSAGE = "If that email is not already registered, we've sent a verification link."
_RESET_REQUEST_MESSAGE = "If that email is registered, we've sent a password reset link."
_INVALID_CREDENTIALS_MESSAGE = "invalid email or password"


def _password_or_422(password: str) -> None:
    try:
        validate_password_strength(password)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.post("/register", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED)
async def register(body: RegisterRequest, db: _DbSession) -> MessageResponse:
    """AC-001, AC-003: create an unverified account and email a verification
    link; a neutral response either way so existing emails are not leaked.

    An existing, still-unverified account is also the "resend" path AC-004
    expects: calling this again re-issues a verification token and
    invalidates the earlier one, with no second route and no new signal.
    """
    _password_or_422(body.password)
    email = body.email.lower()
    existing = db.query(User).filter(User.email == email).first()

    if existing is None:
        user = User(email=email, password_hash=hash_password(body.password), is_verified=False)
        db.add(user)
        db.commit()
        db.refresh(user)
        raw_token = auth_service.issue_verification_token(db, user)
        auth_service.send_verification_email(user, raw_token)
    elif not existing.is_verified:
        raw_token = auth_service.issue_verification_token(db, existing)
        auth_service.send_verification_email(existing, raw_token)
    # else: already registered and verified -- do nothing, same response.

    return MessageResponse(message=_REGISTER_MESSAGE)


@router.post("/verify", response_model=VerifyResponse)
async def verify(body: VerifyRequest, db: _DbSession) -> VerifyResponse:
    """AC-002: mark the account verified via the emailed, single-use token."""
    try:
        user = auth_service.consume_token(db, body.token, "verify")
    except auth_service.TokenError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    user.is_verified = True
    db.add(user)
    db.commit()
    return VerifyResponse(verified=True)


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, db: _DbSession) -> LoginResponse:
    """AC-004, AC-005, AC-006: sign in a verified user; a generic error for
    bad credentials that never distinguishes unknown-email from
    wrong-password, and a distinct, actionable error for an unverified
    account."""
    email = body.email.lower()
    user = db.query(User).filter(User.email == email).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID_CREDENTIALS_MESSAGE
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "Please verify your email before logging in.",
                "verification_required": True,
                "resend_path": "/auth/register",
            },
        )

    token = create_access_token(subject=str(user.id))
    return LoginResponse(access_token=token)


@router.post(
    "/password-reset/request",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def password_reset_request(body: PasswordResetRequest, db: _DbSession) -> MessageResponse:
    """AC-007: always 202, regardless of whether the email exists."""
    email = body.email.lower()
    user = db.query(User).filter(User.email == email).first()
    if user is not None:
        raw_token = auth_service.issue_password_reset_token(db, user)
        auth_service.send_password_reset_email(user, raw_token)
    return MessageResponse(message=_RESET_REQUEST_MESSAGE)


@router.post("/password-reset/confirm", response_model=MessageResponse)
async def password_reset_confirm(
    body: PasswordResetConfirmRequest, db: _DbSession
) -> MessageResponse:
    """AC-007: set a new password via a single-use reset token; a second use
    of the same token is rejected."""
    _password_or_422(body.new_password)
    try:
        user = auth_service.consume_token(db, body.token, "password_reset")
    except auth_service.TokenError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    user.password_hash = hash_password(body.new_password)
    db.add(user)
    db.commit()
    return MessageResponse(message="Password updated.")
