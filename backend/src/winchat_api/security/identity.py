"""Deciding who a request is, for rate-limiting purposes.

Shared by every endpoint that spends money or writes rows, so the rule is defined once. An
endpoint that derives the caller's identity its own way is an endpoint whose limits can be
bypassed by using a different endpoint.
"""

from fastapi import Request

from winchat_api.config import get_settings
from winchat_api.security.auth import AuthenticatedUser
from winchat_api.security.rate_limit import Subject, anonymous_subject, user_subject


def client_ip(request: Request) -> str:
    """The caller's address, trusting the proxy header only when configured to.

    Render and Vercel sit in front of this service, so the socket address is the proxy's.
    `X-Forwarded-For` is client-supplied and trivially spoofed, which would let anyone mint
    a fresh rate-limit identity per request — so the leftmost entry is used only where a
    proxy is expected, and the direct address otherwise.
    """
    if get_settings().trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def subject_for(request: Request, user: AuthenticatedUser | None) -> Subject:
    return user_subject(user.id) if user else anonymous_subject(client_ip(request))
