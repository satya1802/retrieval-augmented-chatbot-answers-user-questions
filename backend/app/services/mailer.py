"""A tiny mailer abstraction with a console/dev backend.

The ticket forbids adding a third-party SMTP dependency, so this is the
entire mailer: log the message and remember it. Swapping in a real
provider (SES, Postgres-backed queue, whatever) later means replacing the
body of `send_email` -- callers only ever import that one function.
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger("app.mailer")


@dataclass
class SentEmail:
    to: str
    subject: str
    body: str


# Dev/test backend: every "send" lands here instead of going over the wire.
# Tests read this list to recover a token that would otherwise only exist in
# an email nobody delivers in this environment.
OUTBOX: list[SentEmail] = []


def send_email(to: str, subject: str, body: str) -> None:
    message = SentEmail(to=to, subject=subject, body=body)
    OUTBOX.append(message)
    logger.info("EMAIL to=%s subject=%s\n%s", to, subject, body)
