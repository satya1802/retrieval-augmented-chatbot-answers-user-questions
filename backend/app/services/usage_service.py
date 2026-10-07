"""Fair-use cap enforcement and usage counters.

Both the document-upload cap (app.routers.documents) and the monthly
question cap (app.routers.conversations) read their limits from
app.config and do their arithmetic here, once, so neither router repeats
"count rows, compare to a config constant, raise 409" in its own words.
"""

from datetime import date, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import DOCUMENTS_CAP, MONTHLY_QUESTION_CAP
from app.models import Document, User

# Length of the rolling monthly question window. Not itself one of the two
# "fair-use caps" the ticket calls out as configurable settings, but kept
# alongside them so the rollover math and the caps live in one module.
QUESTION_WINDOW_DAYS = 30


def check_document_capacity(
    db: Session, owner_id, additional: int = 1, cap: int = DOCUMENTS_CAP
) -> None:
    """Refuse with 409 if storing `additional` more documents would push the
    caller over `cap` (AC-011, defaults to the single configurable
    DOCUMENTS_CAP). The message states the cap and that deleting a document
    frees capacity, so the refusal is actionable, not just a dead end.
    """
    current_count = db.query(Document).filter(Document.owner_id == owner_id).count()
    if current_count + additional > cap:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Document cap of {cap} reached. Delete a document to free up capacity."
            ),
        )


def question_reset_date(user: User) -> date:
    """The date the caller's monthly question window next rolls over."""
    return user.question_window_start + timedelta(days=QUESTION_WINDOW_DAYS)


def _roll_window_if_expired(user: User) -> bool:
    """Reset the window (and the count with it) if the current window is
    older than QUESTION_WINDOW_DAYS. Returns whether it rolled over."""
    if date.today() - user.question_window_start >= timedelta(days=QUESTION_WINDOW_DAYS):
        user.question_window_start = date.today()
        user.monthly_question_count = 0
        return True
    return False


def enforce_question_capacity(
    db: Session, user: User, cap: int = MONTHLY_QUESTION_CAP
) -> None:
    """Roll the monthly window over if it has expired, then refuse the
    question with 409 -- naming the monthly limit and the date it resets --
    if the caller has already used the window up (AC-012, defaults to the
    single configurable MONTHLY_QUESTION_CAP).

    Called, and must complete, before retrieval or any embedding/LLM
    provider call runs.
    """
    rolled_over = _roll_window_if_expired(user)
    if user.monthly_question_count >= cap:
        db.add(user)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Monthly question limit of {cap} reached. "
                f"Resets on {question_reset_date(user).isoformat()}."
            ),
        )
    if rolled_over:
        db.add(user)
        db.commit()


def increment_question_count(db: Session, user: User) -> None:
    """Record a successful question against the caller's monthly count."""
    user.monthly_question_count += 1
    db.add(user)
    db.commit()
