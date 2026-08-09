"""Proof that a request came from a browser with a human behind it.

Cloudflare Turnstile, verified server-side. The client solves an invisible challenge and
sends the resulting token; this exchanges it with Cloudflare's `siteverify` endpoint, which
is the only step that actually proves anything — a token the server never checks is
decoration.

**Why this layer exists on top of the ones already here.** The origin check stops a bare
`curl`, but `Origin` is client-supplied and anyone reading the source can set it. Rate
limits bound one address, and an address is cheap to change. Turnstile is the first control
that costs an attacker something per request rather than per identity.

**Why it is not a gate on the whole app.** Requiring a challenge before anyone may read or
ask anything would tax every real visitor to inconvenience a bot that is already capped at
2000 requests a day by the global breaker. Invisible mode challenges only traffic that
looks automated, so the median visitor never sees it.

**Why signed-in users skip it.** They have already proven themselves to GitHub, Google, or
an email round-trip. Asking them to prove it again buys nothing.

Off unless `TURNSTILE_SECRET_KEY` is set, so an unconfigured deployment behaves exactly as
before rather than rejecting everybody.
"""

import logging

import httpx
from fastapi import HTTPException, Request

from winchat_api.config import get_settings
from winchat_api.security.identity import is_maintenance_request

logger = logging.getLogger(__name__)

VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
TOKEN_HEADER = "cf-turnstile-response"


async def verify_turnstile(request: Request, *, client_ip: str | None = None) -> None:
    """Raise 403 unless this request carries a valid, unused Turnstile token.

    A no-op when unconfigured, for a maintenance caller, or for a signed-in user — the
    caller decides which of those apply and simply does not call this.
    """
    settings = get_settings()
    secret = settings.turnstile_secret_key
    if not secret:
        return

    if is_maintenance_request(request):
        return

    token = request.headers.get(TOKEN_HEADER, "")
    if not token:
        raise HTTPException(
            status_code=403,
            detail="This request could not be verified as coming from a browser.",
        )

    payload = {"secret": secret, "response": token}
    # Cloudflare uses the address to bind a token to the client that solved it, which is
    # what stops a solved token being resold. Sent only when we actually trust our view of
    # the address — behind a proxy with TRUST_PROXY_HEADERS off it would be the proxy's.
    if client_ip and settings.trust_proxy_headers:
        payload["remoteip"] = client_ip

    try:
        async with httpx.AsyncClient(timeout=settings.turnstile_timeout_s) as client:
            response = await client.post(VERIFY_URL, data=payload)
            response.raise_for_status()
            result = response.json()
    except httpx.HTTPError as exc:
        # Fail OPEN on an outage, deliberately. Cloudflare being unreachable is our problem,
        # not the visitor's, and the rate limiter plus the global breaker still bound the
        # damage. Failing closed here would let a third party take the app down.
        logger.warning("turnstile verification unavailable, allowing request: %s", exc)
        return

    if not result.get("success"):
        # Error codes are Cloudflare's, e.g. timeout-or-duplicate for a replayed token.
        logger.info("turnstile rejected a request: %s", result.get("error-codes"))
        raise HTTPException(
            status_code=403,
            detail="Verification failed. Reload the page and try again.",
        )
