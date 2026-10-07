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
