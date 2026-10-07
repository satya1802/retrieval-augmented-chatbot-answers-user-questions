"""JWT bearer authentication and password hashing.

The architecture names JWT as the auth mechanism and requires every
non-auth route to answer 401 to a missing or invalid token before anything
else runs (AC-010). `get_current_user_id` is the dependency every protected
router below takes; FastAPI resolves it before the handler body runs, so a
missing or bad token never reaches a stub handler, let alone real logic.

Issuing tokens is the `/auth/login` handler's job -- it calls
`create_access_token` below. Validating what it signs belongs here, once,
rather than copied into every router, so US-003-1 can reuse both without
touching app/routers/auth.py.

Password hashing lives here too: it is the other half of "how a credential
is checked", and `PASSWORD_MIN_LENGTH`/`PASSWORD_RULE` are the single
constants a frontend mirrors rather than guessing the server's rule.
"""

import os
import time
import uuid
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext

# 32+ bytes so HS256 doesn't warn about an under-length key; set a real,
# random JWT_SECRET before this ever runs anywhere but a laptop.
JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-secret-change-me-before-deploying")
JWT_ALGORITHM = "HS256"
DEFAULT_TOKEN_LIFETIME_SECONDS = 60 * 60 * 24

_bearer_scheme = HTTPBearer(auto_error=False)

_BearerCredentials = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)]


def create_access_token(
    subject: str, expires_in_seconds: int = DEFAULT_TOKEN_LIFETIME_SECONDS
) -> str:
    """Sign a bearer token for `subject` (a user id). Used by `/auth/login`,
    and by tests that need to call a protected route."""
    payload = {"sub": str(subject), "exp": int(time.time()) + expires_in_seconds}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_user_id(credentials: _BearerCredentials) -> uuid.UUID:
    """Decode the bearer token and return the caller's user id, or raise 401.

    Every owned-resource lookup downstream still has to filter by this id and
    return 404 on mismatch (see the architecture note) -- this dependency
    only establishes who is asking, not what they may see.
    """
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return uuid.UUID(str(payload["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        ) from exc


# ------------------------------------------------------- password rules ---

# The single source of truth for password strength -- the frontend mirrors
# this message/length so it can validate before submitting, but the server
# is what actually enforces it (register and password-reset/confirm).
PASSWORD_MIN_LENGTH = 8
PASSWORD_RULE = (
    f"Password must be at least {PASSWORD_MIN_LENGTH} characters long and include "
    "at least one letter and at least one number."
)


def validate_password_strength(password: str) -> None:
    """Raise ValueError (with PASSWORD_RULE as the message) if `password`
    does not meet the rule above."""
    if (
        len(password) < PASSWORD_MIN_LENGTH
        or not any(c.isalpha() for c in password)
        or not any(c.isdigit() for c in password)
    ):
        raise ValueError(PASSWORD_RULE)


_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Never store or log plaintext -- this is the only form that persists."""
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _pwd_context.verify(password, password_hash)


# A fixed hash, tied to no real account, computed once at import. The
# /auth/login handler verifies against this when no user row matches the
# submitted email, so that lookup still spends roughly the same
# bcrypt-bound time a real check would -- rather than returning
# near-instantly and letting response latency (not just the generic error
# body) distinguish "no such account" from "wrong password" for an
# otherwise-identical 401 (AC-005, AC-006).
UNKNOWN_USER_PASSWORD_HASH = hash_password("no-such-account-placeholder-password")
