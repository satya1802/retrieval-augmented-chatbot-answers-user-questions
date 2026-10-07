"""Unit tests for backend/app/security.py: JWT issuance/validation and
password hashing.

Behavioural coverage of the password-strength rule and the full
register/verify/login flow already lives in test_auth.py (which imports
PASSWORD_MIN_LENGTH, PASSWORD_RULE and validate_password_strength straight
from this module), and "no token at all" is already covered as
"endpoints require auth" in test_documents.py / test_chunks.py. This file
is the rest: hashing itself, token issuance and its expiry, every way
get_current_user_id can refuse a token, and -- through a real protected
route -- that a *present but invalid* token (expired or tampered, not just
missing) is rejected end to end with the same 401 + WWW-Authenticate
contract AC-010 requires.
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
    create_access_token,
    get_current_user_id,
    hash_password,
    verify_password,
)


def _bearer(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


# --------------------------------------------------------- password hash ---


def test_hash_password_never_returns_the_plaintext_and_verifies_it():
    hashed = hash_password("Password1")

    assert hashed != "Password1"
    assert verify_password("Password1", hashed) is True


def test_hash_password_salts_so_two_hashes_of_the_same_password_differ():
    first = hash_password("Password1")
    second = hash_password("Password1")

    assert first != second
    # Both independently-salted hashes must still verify the same plaintext.
    assert verify_password("Password1", first) is True
    assert verify_password("Password1", second) is True


def test_verify_password_rejects_the_wrong_password():
    hashed = hash_password("Password1")

    assert verify_password("WrongPassword1", hashed) is False


# ------------------------------------------------------ token issuance -----


def test_create_access_token_round_trips_subject_and_sets_a_future_expiry():
    user_id = str(uuid.uuid4())

    token = create_access_token(subject=user_id)
    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

    assert payload["sub"] == user_id
    assert payload["exp"] > time.time()


def test_create_access_token_honours_a_custom_lifetime():
    before = int(time.time())

    token = create_access_token(subject=str(uuid.uuid4()), expires_in_seconds=10)
    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

    assert before < payload["exp"] <= before + 10


# -------------------------------------------------- get_current_user_id ----


def test_get_current_user_id_returns_the_subject_of_a_valid_token():
    user_id = uuid.uuid4()
    token = create_access_token(subject=str(user_id))

    resolved = get_current_user_id(_bearer(token))

    assert resolved == user_id


def test_get_current_user_id_rejects_missing_credentials():
    with pytest.raises(HTTPException) as exc_info:
        get_current_user_id(None)

    assert exc_info.value.status_code == 401


def test_get_current_user_id_rejects_a_token_signed_with_the_wrong_secret():
    tampered = jwt.encode(
        {"sub": str(uuid.uuid4()), "exp": int(time.time()) + 60},
        "not-the-real-secret",
        algorithm=JWT_ALGORITHM,
    )

    with pytest.raises(HTTPException) as exc_info:
        get_current_user_id(_bearer(tampered))

    assert exc_info.value.status_code == 401


def test_get_current_user_id_rejects_an_expired_token():
    expired = jwt.encode(
        {"sub": str(uuid.uuid4()), "exp": int(time.time()) - 1},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )

    with pytest.raises(HTTPException) as exc_info:
        get_current_user_id(_bearer(expired))

    assert exc_info.value.status_code == 401


def test_get_current_user_id_rejects_a_token_whose_subject_is_not_a_uuid():
    bad_subject = jwt.encode(
        {"sub": "not-a-uuid", "exp": int(time.time()) + 60},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )

    with pytest.raises(HTTPException) as exc_info:
        get_current_user_id(_bearer(bad_subject))

    assert exc_info.value.status_code == 401


def test_get_current_user_id_rejects_garbage_that_is_not_a_jwt_at_all():
    with pytest.raises(HTTPException) as exc_info:
        get_current_user_id(_bearer("not-a-jwt"))

    assert exc_info.value.status_code == 401


# ------------------------------------------------------------ integration --
# A present-but-bad token must be refused by a real protected route, not
# just by calling the dependency function directly -- this is the
# "every non-auth route answers 401 before anything else runs" guarantee
# (AC-010) for the cases that are not simply "no header at all".


def test_protected_endpoint_rejects_an_expired_bearer_token_end_to_end(client):
    expired = create_access_token(subject=str(uuid.uuid4()), expires_in_seconds=-1)

    resp = client.get("/me/usage", headers={"Authorization": f"Bearer {expired}"})

    assert resp.status_code == 401
    assert resp.headers.get("www-authenticate") == "Bearer"


def test_protected_endpoint_rejects_a_tampered_bearer_token_end_to_end(client):
    tampered = jwt.encode(
        {"sub": str(uuid.uuid4()), "exp": int(time.time()) + 60},
        "wrong-secret",
        algorithm=JWT_ALGORITHM,
    )

    resp = client.get("/me/usage", headers={"Authorization": f"Bearer {tampered}"})

    assert resp.status_code == 401
    assert resp.headers.get("www-authenticate") == "Bearer"
