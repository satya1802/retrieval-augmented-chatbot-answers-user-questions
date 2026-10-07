"""Fair-use caps, storage location and ingestion pipeline settings as single,
configurable settings.

Read once here rather than scattered `os.getenv` calls across routers or
services, so AC-013's "the document cap is a single configurable setting"
has one place that is actually true -- and so chunk size, overlap and the
embedding model are configured the same way (see US-006-1).
"""

import os

DOCUMENTS_CAP = int(os.getenv("DOCUMENTS_CAP", "50"))
MONTHLY_QUESTION_CAP = int(os.getenv("MONTHLY_QUESTION_CAP", "200"))

# Local-filesystem storage root for original uploads (see app/services/storage.py).
# No cloud SDK dependency this sprint -- point this at a real volume in deployment.
STORAGE_ROOT = os.getenv("STORAGE_ROOT", "./storage")

# Ingestion pipeline (see app/services/ingestion_service.py). Characters per
# chunk and how many trailing characters of one chunk repeat at the start of
# the next, so a sentence split across a chunk boundary is still wholly
# readable in at least one chunk.
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))

# ai_provider -- hosted commercial embedding model, OpenAI-compatible.
EMBEDDING_MODEL = os.getenv("AI_PROVIDER_EMBEDDING_MODEL", "text-embedding-3-small")
AI_PROVIDER_API_KEY = os.getenv("AI_PROVIDER_API_KEY", "")
AI_PROVIDER_BASE_URL = os.getenv("AI_PROVIDER_BASE_URL") or None

# ai_provider -- hosted commercial chat/generation model, OpenAI-compatible
# (see app/services/generation_client.py, US-014-1). Timeout bounds how long
# the answer-generation call site waits before a hung provider surfaces as
# a failure (AC-048) rather than hanging the request indefinitely.
CHAT_MODEL = os.getenv("AI_PROVIDER_CHAT_MODEL", "gpt-4o-mini")
GENERATION_TIMEOUT_SECONDS = float(os.getenv("AI_PROVIDER_TIMEOUT_SECONDS", "30"))

# Retrieval (see app/services/retrieval.py): the fixed number of the
# caller's highest-scoring ready chunks returned as answer context per
# question (AC-035, AC-037). One constant so a test or deployment overrides
# a single value rather than a limit baked into each call site.
RETRIEVAL_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "5"))
