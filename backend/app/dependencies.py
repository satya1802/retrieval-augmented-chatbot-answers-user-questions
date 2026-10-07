"""Owner-scoped lookup helper shared by every router that holds owned rows.

A single `get_owned_or_404` here, reused everywhere, means a new router
cannot accidentally serve another user's row by forgetting the owner_id
filter: there is exactly one way to do this lookup, not one per router that
someone could get wrong or skip (see US-003-1's acceptance criteria).
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session


def get_owned_or_404[ModelT](
    db: Session,
    model: type[ModelT],
    resource_id: uuid.UUID,
    owner_id: uuid.UUID,
    detail: str = "not found",
) -> ModelT:
    """Fetch a row of `model` by primary key, filtered by `owner_id` at the
    query level -- not fetched then checked in Python after serialisation.

    A nonexistent id and an id owned by someone else both answer 404 with
    the same generic `detail`; never 403, since a 403 body would confirm the
    resource exists at all.
    """
    obj = db.query(model).filter(model.id == resource_id, model.owner_id == owner_id).first()
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    return obj
