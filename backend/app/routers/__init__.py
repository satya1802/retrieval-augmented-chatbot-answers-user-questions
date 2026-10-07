"""One router module per architecture component that owns endpoints.

app.main includes each router below; this package only re-exports them so
`from app.routers import auth, me, documents, conversations, chunks` reads as
one line instead of five.
"""

from app.routers import auth, chunks, conversations, documents, me

__all__ = ["auth", "me", "documents", "conversations", "chunks"]
