"""Application entrypoint.

Generated from the approved architecture: one router per component that owns
endpoints, one route per endpoint the API spec declares. Every generated route
is a stub that returns a typed placeholder, so the service starts, serves its
OpenAPI document and passes its tests before a single handler is implemented.
"""

import os

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import models  # noqa: F401 -- imported so the tables register before create_all
from app.database import Base, engine
from app.routers import auth, chunks, conversations, documents, me

app = FastAPI(
    title="Retrieval-augmented chatbot answers user questions",
    description=(
        "Create a retrieval-augmented chatbot that answers user questions "
        "using the provided context."
    ),
    version="0.1.0",
)

# The SPA runs on a different origin than the API, so the browser refuses its calls
# unless that origin is allowed here. In development that is the Vite dev server; when
# deployed, the platform injects the frontend's real URL as ALLOWED_ORIGINS (comma
# separated). Point ALLOWED_ORIGINS at the real thing and nothing else has to change.
_dev_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
_allowed_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins or _dev_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def _http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Every 401 anywhere in the app -- missing, expired or tampered JWT,
    from any router -- carries a WWW-Authenticate header (AC-010), without
    every router or app.security having to set it itself."""
    headers = dict(exc.headers) if exc.headers else {}
    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
        headers.setdefault("WWW-Authenticate", "Bearer")
    return JSONResponse(
        status_code=exc.status_code, content={"detail": exc.detail}, headers=headers
    )


# The scaffold ships no migrations, so the tables are created from the models on
# startup. Replace this with Alembic before anything holds data worth keeping.
Base.metadata.create_all(bind=engine)

# Auth is unauthenticated by spec; every other router's routes depend on
# app.security.get_current_user_id and answer 401 before a handler runs
# (AC-010). See each module in app/routers for the endpoints it owns.
app.include_router(auth.router)
app.include_router(me.router)
app.include_router(documents.router)
app.include_router(conversations.router)
app.include_router(chunks.router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe, and the only route here that is not a stub."""
    return {"status": "ok"}
