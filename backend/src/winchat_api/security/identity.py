"""Deciding who a request is, for rate-limiting purposes. Defined once so a caller cannot
get a fresh budget by switching endpoints.
"""

import hmac

from fastapi import Request

from winchat_api.config import get_settings
from winchat_api.security.auth import AuthenticatedUser
from winchat_api.security.rate_limit import Subject, anonymous_subject, user_subject


def client_ip(request: Request) -> str:
    """The caller's address. `X-Forwarded-For` is client-supplied, so its leftmost entry is used
    only where a proxy is expected, and the socket address otherwise.
    """
    if get_settings().trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def subject_for(request: Request, user: AuthenticatedUser | None) -> Subject:
    return user_subject(user.id) if user else anonymous_subject(client_ip(request))


MAINTENANCE_HEADER = "x-maintenance-token"


def is_maintenance_request(request: Request) -> bool:
    """Whether the request carries the maintenance token. It waives only the per-subject rate
    limits: the caller is still subject to the global ceiling, to Row Level Security, and to usage
    recording.
    """
    expected = get_settings().maintenance_token
    if not expected:
        return False

    supplied = request.headers.get(MAINTENANCE_HEADER, "")
    if not supplied:
        return False

    return hmac.compare_digest(supplied, expected)
