"""Refusing expensive requests that did not come from the app. CORS does not cover this:
non-browser clients send no Origin header at all.
"""

import logging

from fastapi import HTTPException, Request

from winchat_api.config import get_settings
from winchat_api.security.identity import is_maintenance_request

logger = logging.getLogger(__name__)


def require_browser_origin(request: Request) -> None:
    """Reject a request whose `Origin` is missing or not in the CORS allowlist. Reuses
    `CORS_ALLOW_ORIGINS` rather than keeping a second list that has to agree with it.
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
