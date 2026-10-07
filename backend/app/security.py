"""JWT bearer authentication.

The architecture names JWT as the auth mechanism and requires every
non-auth route to answer 401 to a missing or invalid token before anything
else runs (AC-010). `get_current_user_id` is the dependency every protected
router below takes; FastAPI resolves it before the handler body runs, so a
missing or bad token never reaches a stub handler, let alone real logic.

Issuing tokens is the `/auth/login` handler's job once it exists -- it will
call `create_access_token` below. Validating what it signs belongs here,
once, rather than copied into every router.
"""

import os
import time
import uuid
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# 32+ bytes so HS256 doesn't warn about an under-length key; set a real,
# random JWT_SECRET before this ever runs anywhere but a laptop.
JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-secret-change-me-before-deploying")
JWT_ALGORITHM = "HS256"
DEFAULT_TOKEN_LIFETIME_SECONDS = 60 * 60 * 24

_bearer_scheme = HTTPBearer(auto_error=False)

_BearerCredentials = Annotated[
    HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)
]


def create_access_token(
    subject: str, expires_in_seconds: int = DEFAULT_TOKEN_LIFETIME_SECONDS
) -> str:
    """Sign a bearer token for `subject` (a user id). Used by `/auth/login`
    once implemented, and by tests that need to call a protected route."""
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
