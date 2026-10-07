"""Business logic behind the /auth routes: token issuance and consumption,
and the verification/reset emails. Kept out of the router so the router
stays a thin HTTP translation of the approved contract.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import AuthToken, User
from app.services.mailer import send_email

VERIFY_TOKEN_TTL_SECONDS = 24 * 60 * 60
RESET_TOKEN_TTL_SECONDS = 60 * 60

_VERIFY_PURPOSE = "verify"
_RESET_PURPOSE = "password_reset"


class TokenError(Exception):
    """Raised when a submitted token is unknown, expired, or already used."""


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _issue_token(db: Session, user: User, purpose: str, ttl_seconds: int) -> str:
    # Invalidate any earlier, still-unused token for the same purpose so a
    # resend (AC-004) can't leave a still-valid token floating around.
    now = datetime.now(timezone.utc)
    (
        db.query(AuthToken)
        .filter(
            AuthToken.user_id == user.id,
            AuthToken.purpose == purpose,
            AuthToken.used_at.is_(None),
        )
        .update({"used_at": now})
    )
    raw_token = secrets.token_urlsafe(32)
    db.add(
        AuthToken(
            user_id=user.id,
            purpose=purpose,
            token_hash=_hash_token(raw_token),
            expires_at=now + timedelta(seconds=ttl_seconds),
        )
    )
    db.commit()
    return raw_token


def issue_verification_token(db: Session, user: User) -> str:
    return _issue_token(db, user, _VERIFY_PURPOSE, VERIFY_TOKEN_TTL_SECONDS)


def issue_password_reset_token(db: Session, user: User) -> str:
    return _issue_token(db, user, _RESET_PURPOSE, RESET_TOKEN_TTL_SECONDS)


def consume_token(db: Session, raw_token: str, purpose: str) -> User:
    """Mark a single-use token spent and return the user it belongs to.

    Raises TokenError for an unknown token, a token already used, or one
    past its expiry -- the router maps all three to 400/401 as the AC
    requires without distinguishing which.
    """
    token = (
        db.query(AuthToken)
        .filter(AuthToken.token_hash == _hash_token(raw_token), AuthToken.purpose == purpose)
        .first()
    )
    if token is None:
        raise TokenError("invalid token")
    if token.used_at is not None:
        raise TokenError("token already used")

    expires_at = token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise TokenError("token expired")

    token.used_at = datetime.now(timezone.utc)
    db.add(token)
    db.commit()

    user = db.get(User, token.user_id)
    if user is None:
        raise TokenError("invalid token")
    return user


def send_verification_email(user: User, raw_token: str) -> None:
    send_email(
        to=user.email,
        subject="Verify your email",
        body=f"Use this token to verify your account: {raw_token}",
    )


def send_password_reset_email(user: User, raw_token: str) -> None:
    send_email(
        to=user.email,
        subject="Reset your password",
        body=f"Use this token to reset your password: {raw_token}",
    )
