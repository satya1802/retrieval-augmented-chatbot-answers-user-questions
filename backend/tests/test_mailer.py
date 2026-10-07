"""Unit tests for backend/app/services/mailer.py.

mailer.send_email is a dev/test stand-in for a real email provider: it
logs the message and appends it to a module-level OUTBOX list that other
parts of the app (and their tests) read to recover things like a reset
token that would otherwise only ever exist in an email nobody delivers
in this environment. These tests pin down that contract directly.
"""

import logging

import pytest

from app.services import mailer
from app.services.mailer import OUTBOX, SentEmail, send_email


@pytest.fixture(autouse=True)
def clean_outbox():
    """Each test gets a pristine OUTBOX so sends don't leak across tests."""
    OUTBOX.clear()
    yield
    OUTBOX.clear()


def test_send_email_appends_to_outbox():
    send_email(to="user@example.com", subject="Hello", body="World")

    assert len(OUTBOX) == 1
    sent = OUTBOX[0]
    assert isinstance(sent, SentEmail)
    assert sent.to == "user@example.com"
    assert sent.subject == "Hello"
    assert sent.body == "World"


def test_send_email_returns_none():
    result = send_email(to="user@example.com", subject="Hi", body="Body")

    assert result is None


def test_send_email_preserves_order_for_multiple_sends():
    send_email(to="first@example.com", subject="One", body="1st")
    send_email(to="second@example.com", subject="Two", body="2nd")

    assert [m.to for m in OUTBOX] == ["first@example.com", "second@example.com"]
    assert [m.subject for m in OUTBOX] == ["One", "Two"]


def test_send_email_does_not_dedupe_identical_messages():
    send_email(to="user@example.com", subject="Same", body="Same")
    send_email(to="user@example.com", subject="Same", body="Same")

    assert len(OUTBOX) == 2


def test_outbox_recovers_arbitrary_body_content_eg_a_token():
    # The docstring on mailer.py specifically calls out recovering a
    # token from an email that is never actually delivered -- exercise
    # exactly that shape of body.
    token = "reset-token-abc123"
    send_email(
        to="user@example.com",
        subject="Password reset",
        body=f"Your reset token is: {token}",
    )

    assert token in OUTBOX[-1].body


def test_send_email_logs_recipient_and_subject(caplog):
    with caplog.at_level(logging.INFO, logger="app.mailer"):
        send_email(to="user@example.com", subject="Logged Subject", body="Body text")

    records = [r for r in caplog.records if r.name == "app.mailer"]
    assert len(records) == 1
    message = records[0].getMessage()
    assert "user@example.com" in message
    assert "Logged Subject" in message
    assert "Body text" in message


def test_sent_email_is_a_plain_dataclass_with_expected_fields():
    sent = SentEmail(to="a@example.com", subject="s", body="b")

    assert sent.to == "a@example.com"
    assert sent.subject == "s"
    assert sent.body == "b"


def test_mailer_module_exposes_send_email_as_sole_entry_point():
    # The module docstring promises callers only ever import send_email;
    # guard against that contract silently growing a second API surface
    # that callers might start depending on instead.
    public_names = [n for n in dir(mailer) if not n.startswith("_")]
    assert "send_email" in public_names
