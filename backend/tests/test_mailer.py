"""Unit tests for app.services.mailer.

The ticket deliberately forbids a real SMTP dependency, so `send_email`'s
entire contract is: it never raises, it logs the message, and it appends a
`SentEmail` to `OUTBOX` that a test (or, in dev, a human staring at logs) can
recover the content from -- including whatever secret token a caller baked
into the body. These tests exercise exactly that contract through the public
function; nothing here reaches into `app.services.auth_service` or any other
caller, since those own their own tests for how *they* use the mailer.
"""

import logging

import pytest

from app.services import mailer
from app.services.mailer import OUTBOX, SentEmail, send_email


@pytest.fixture(autouse=True)
def _clean_outbox():
    """OUTBOX is a module-level list, not a per-test fixture, so without this
    a token left over from one test would still be sitting there -- and
    passing -- for the next one to read by accident."""
    OUTBOX.clear()
    yield
    OUTBOX.clear()


def test_send_email_appends_a_sent_email_to_the_outbox():
    send_email(to="alice@example.com", subject="Verify your email", body="token: abc123")

    assert len(OUTBOX) == 1
    sent = OUTBOX[0]
    assert sent == SentEmail(
        to="alice@example.com", subject="Verify your email", body="token: abc123"
    )


def test_send_email_preserves_the_exact_body_a_caller_hands_it():
    # The body is how a caller (e.g. auth_service) delivers a one-time token in
    # an environment with no real mail transport; if this got mangled, a test
    # reading OUTBOX for a verification token would silently read garbage.
    secret_body = "Use this token to reset your password: Tok3n-With_Punct.uation!"

    send_email(to="bob@example.com", subject="Reset your password", body=secret_body)

    assert OUTBOX[-1].body == secret_body


def test_send_email_does_not_lowercase_or_otherwise_mutate_the_recipient():
    send_email(to="Mixed.Case@Example.com", subject="hi", body="hi")

    assert OUTBOX[-1].to == "Mixed.Case@Example.com"


def test_multiple_sends_accumulate_in_order_rather_than_overwriting():
    send_email(to="first@example.com", subject="one", body="1")
    send_email(to="second@example.com", subject="two", body="2")
    send_email(to="third@example.com", subject="three", body="3")

    assert [m.to for m in OUTBOX] == ["first@example.com", "second@example.com", "third@example.com"]
    assert len(OUTBOX) == 3


def test_send_email_returns_none():
    result = send_email(to="x@example.com", subject="s", body="b")

    assert result is None


def test_send_email_logs_the_recipient_subject_and_body(caplog):
    with caplog.at_level(logging.INFO, logger="app.mailer"):
        send_email(to="carol@example.com", subject="Verify your email", body="token: zzz999")

    messages = [record.getMessage() for record in caplog.records]
    assert any(
        "carol@example.com" in message
        and "Verify your email" in message
        and "token: zzz999" in message
        for message in messages
    )


def test_outbox_is_shared_module_state_not_a_copy_per_call():
    # Guards the "callers read this list to recover a token" contract
    # documented on OUTBOX: it must be the same object send_email mutates,
    # not something tests would have to re-import to see.
    send_email(to="dana@example.com", subject="s", body="b")

    assert mailer.OUTBOX is OUTBOX
    assert OUTBOX[-1].to == "dana@example.com"
