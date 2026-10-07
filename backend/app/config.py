"""Fair-use caps and storage location as single, configurable settings.

Read once here rather than scattered `os.getenv` calls across routers, so
AC-013's "the document cap is a single configurable setting" has one place
that is actually true.
"""

import os

DOCUMENTS_CAP = int(os.getenv("DOCUMENTS_CAP", "50"))
MONTHLY_QUESTION_CAP = int(os.getenv("MONTHLY_QUESTION_CAP", "200"))

# Local-filesystem storage root for original uploads (see app/services/storage.py).
# No cloud SDK dependency this sprint -- point this at a real volume in deployment.
STORAGE_ROOT = os.getenv("STORAGE_ROOT", "./storage")
