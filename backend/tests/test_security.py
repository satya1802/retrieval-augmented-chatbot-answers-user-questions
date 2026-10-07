"""Unit tests for app/security.py: JWT issuing/validation and password hashing.

Behavioural coverage of the endpoints that call these functions already
lives in test_auth.py (register/login/verify), test_documents.py and
test_me.py (missing/garbage bearer token -> 401 on a protected route).
This file exercises app.security's own public functions directly, for the
paths those end-to-end flows never happen to hit: an expired or
signature-tampered JWT, a token signed with the wrong secret, a token whose
`sub` isn't a UUID or is missing entirely, the password-hashing contract
(salted, verifiable, never the plaintext), and the fixed placeholder hash
`/auth/login` verifies against for an unknown email so that lookup takes
the same bcrypt-bound time as a real one.

No ticket-supplied acceptance criteria accompany this ticket (title and
description only); coverage below follows the module's own docstring and
the behaviour app/routers/auth.py and the protected routers depend on it
for.
"""

import time
import uuid

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.security import (
    JWT_ALGORITHM,
    JWT_SECRET,
    PASSWORD_MIN_LENGTH,
    PASSWORD_RULE,
    UNKNOWN_USER_PASSWORD_HASH,
    create_access_token,
    get_current_user_id,
    hash_password,
    validate_password_strength,
    verify_password,
)


def _bearer(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


# ------------------------------------------------- create/decode tokens ---


def test_create_access_token_round_trips_through_get_current_user_id():
    user_id = uuid.uuid4()
    token = create_access_token(subject=str(user_id))

    resolved = get_current_user_id(_bearer(token))

    assert resolved == user_id


def test_get_current_user_id_rejects_missing_credentials():
    with pytest.raises(HTTPException) as exc_info:
        get_current_user_id(None)
    assert exc_info.value.status_code == 401


def test_get_current_user_id_rejects_a_tampered_signature():
    token = create_access_token(subject=str(uuid.uuid4()))
    last = token[-1]
    tampered = token[:-1] + ("a" if last != "a" else "b")

    with pytest.raises(HTTPException) as exc_info:
        get_current_user_id(_bearer(tampered))
    assert exc_info.value.status_code == 401


def test_get_current_user_id_rejects_an_expired_token():
    token = create_access_token(subject=str(uuid.uuid4()), expires_in_seconds=-1)

    with pytest.raises(HTTPException) as exc_info:
        get_current_user_id(_bearer(token))
    assert exc_info.value.status_code == 401


def test_get_current_user_id_rejects_a_token_signed_with_a_different_secret():
    payload = {"sub": str(uuid.uuid4()), "exp": int(time.time()) + 3600}
    foreign_token = jwt.encode(payload, "a-completely-different-secret", algorithm=JWT_ALGORITHM)

    with pytest.raises(HTTPException) as exc_info:
        get_current_user_id(_bearer(foreign_token))
    assert exc_info.value.status_code == 401


def test_get_current_user_id_rejects_a_non_uuid_subject():
    payload = {"sub": "not-a-uuid", "exp": int(time.time()) + 3600}
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    with pytest.raises(HTTPException) as exc_info:
        get_current_user_id(_bearer(token))
    assert exc_info.value.status_code == 401


def test_get_current_user_id_rejects_a_token_missing_the_subject_claim():
    payload = {"exp": int(time.time()) + 3600}
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    with pytest.raises(HTTPException) as exc_info:
        get_current_user_id(_bearer(token))
    assert exc_info.value.status_code == 401


# ------------------------------------------------------- password rules ---


def test_validate_password_strength_accepts_a_password_at_the_minimum_length():
    password = "a1" + "a" * (PASSWORD_MIN_LENGTH - 2)
    assert len(password) == PASSWORD_MIN_LENGTH
    validate_password_strength(password)  # does not raise


def test_validate_password_strength_error_message_is_the_shared_rule():
    with pytest.raises(ValueError) as exc_info:
        validate_password_strength("short")
    assert str(exc_info.value) == PASSWORD_RULE


def test_validate_password_strength_rejects_empty_password():
    with pytest.raises(ValueError):
        validate_password_strength("")


# ------------------------------------------------------- password hashing -


def test_hash_password_never_returns_the_plaintext():
    hashed = hash_password("Password1")
    assert hashed != "Password1"


def test_hash_password_is_salted_so_the_same_password_hashes_differently():
    first = hash_password("Password1")
    second = hash_password("Password1")

    assert first != second
    assert verify_password("Password1", first)
    assert verify_password("Password1", second)


def test_verify_password_accepts_the_correct_password():
    hashed = hash_password("Password1")
    assert verify_password("Password1", hashed) is True


def test_verify_password_rejects_the_wrong_password():
    hashed = hash_password("Password1")
    assert verify_password("WrongPassword1", hashed) is False


# --------------------------------------------- unknown-user placeholder hash


def test_unknown_user_password_hash_never_verifies_an_unrelated_guess():
    """This is what `/auth/login` checks an unknown email's password
    against (AC-005/AC-006 in app/security.py's own docstring); it must
    never accidentally authenticate anyone."""
    assert verify_password("Password1", UNKNOWN_USER_PASSWORD_HASH) is False
    assert verify_password("", UNKNOWN_USER_PASSWORD_HASH) is False


def test_unknown_user_password_hash_does_verify_its_own_fixed_placeholder():
    assert (
        verify_password("no-such-account-placeholder-password", UNKNOWN_USER_PASSWORD_HASH)
        is True
    )


def test_unknown_user_password_hash_is_a_bcrypt_hash_not_the_plaintext():
    assert UNKNOWN_USER_PASSWORD_HASH != "no-such-account-placeholder-password"
    assert UNKNOWN_USER_PASSWORD_HASH.startswith("$2")
