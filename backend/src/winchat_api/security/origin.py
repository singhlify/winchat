"""Refusing expensive requests that did not come from the app.

**CORS does not do this.** A browser enforces CORS; `curl`, a scraper and a bot do not
send an `Origin` header at all, and the middleware happily lets them through. Measured
against the deployed service before this existed: `POST /api/chat` with no headers
returned 200 and spent real Groq and Cohere tokens.

So this is a separate check, applied to the endpoints that cost money. A browser making a
cross-origin `POST` with a JSON body ALWAYS sends `Origin` — it is not optional and cannot
be suppressed by page script — so requiring it costs a legitimate visitor nothing.

**What this is worth, stated honestly.** `Origin` is client-supplied: anyone who reads this
file can set the header and walk straight through. It stops drive-by scripts, naive
scrapers and the copy-pasted curl command, which is the overwhelming majority of casual
abuse. It is not a defence against someone who is actually trying. The real ceiling is the
global daily circuit breaker in `rate_limit.py`, which bounds spend no matter who is
calling — this layer only keeps the cheap noise off it.

Crawlers are unaffected: indexing reads pages with `GET`, and nothing here touches `GET`.
The pages that matter for search — `/`, `/sources` — are server-rendered and stay open.
"""

import logging

from fastapi import HTTPException, Request

from winchat_api.config import get_settings
from winchat_api.security.identity import is_maintenance_request

logger = logging.getLogger(__name__)


def require_browser_origin(request: Request) -> None:
    """Reject a request whose `Origin` is missing or not in the CORS allowlist.

    Used as a FastAPI dependency on the endpoints that spend money. Deliberately reuses
    `CORS_ALLOW_ORIGINS` rather than introducing a second list: two allowlists that must
    agree eventually disagree, and the one nobody remembers is the one that is wrong.
    """
    settings = get_settings()
    if not settings.require_browser_origin:
        return

    # The maintenance token is for smoke-testing a deployment with curl, which by
    # definition has no browser origin. Checked first so the two features compose.
    if is_maintenance_request(request):
        return

    origin = request.headers.get("origin")
    if origin and origin in settings.cors_origins:
        return

    # Logged at INFO, not WARNING: for a public URL this is background noise, and a log
    # line per scraper request would bury the events that matter.
    logger.info("rejected a request with origin %r", origin)
    raise HTTPException(
        status_code=403,
        detail="This endpoint is for use by the WinChat web app.",
    )
