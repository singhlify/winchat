"""Verifying Supabase access tokens.

The frontend signs users in with Supabase and sends the resulting JWT as a bearer token. This
module verifies it, signature, expiry, issuer and audience, and hands back a user id.
"""

import logging
import time
from dataclasses import dataclass

import httpx
import jwt
from fastapi import HTTPException, Request

from winchat_api.config import get_settings

logger = logging.getLogger(__name__)

JWKS_CACHE_TTL_S = 600


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    id: str
    email: str | None = None


class _JwksCache:
    """One cached JWKS per process, refetched on TTL or on an unknown key id."""

    def __init__(self) -> None:
        self._keys: dict[str, jwt.PyJWK] = {}
        self._fetched_at: float = 0.0

    async def get(self, jwks_url: str, kid: str) -> jwt.PyJWK | None:
        fresh = time.monotonic() - self._fetched_at < JWKS_CACHE_TTL_S
        if kid in self._keys and fresh:
            return self._keys[kid]

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(jwks_url)
                response.raise_for_status()
            self._keys = {key.key_id: key for key in jwt.PyJWKSet.from_dict(response.json()).keys}
            self._fetched_at = time.monotonic()
        except Exception as exc:
            logger.warning("could not fetch JWKS from %s: %s", jwks_url, exc)
            return self._keys.get(kid)

        return self._keys.get(kid)


_jwks_cache = _JwksCache()


def _bearer_token(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    return token.strip() if scheme.lower() == "bearer" and token.strip() else None


async def verify_token(token: str) -> AuthenticatedUser:
    """Verify a Supabase access token, or raise 401."""
    settings = get_settings()

    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="malformed token") from exc

    algorithm = header.get("alg", "")
    options = {"verify_aud": True, "require": ["exp", "sub"]}

    try:
        if algorithm.startswith("HS"):
            if not settings.supabase_jwt_secret:
                raise HTTPException(status_code=401, detail="HS256 token but no shared secret")
            claims = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
                options=options,
            )
        else:
            if not settings.supabase_jwks_url:
                raise HTTPException(status_code=401, detail="no JWKS url configured")
            key = await _jwks_cache.get(settings.supabase_jwks_url, header.get("kid", ""))
            if key is None:
                raise HTTPException(status_code=401, detail="unknown signing key")
            claims = jwt.decode(
                token,
                key.key,
                algorithms=[algorithm],
                audience="authenticated",
                options=options,
            )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="token expired") from exc
    except jwt.PyJWTError as exc:
        # Never echo the library's message back. It can describe why verification failed.
        logger.info("token rejected: %s", exc)
        raise HTTPException(status_code=401, detail="invalid token") from exc

    return AuthenticatedUser(id=str(claims["sub"]), email=claims.get("email"))


async def require_user(request: Request) -> AuthenticatedUser:
    """FastAPI dependency: the signed-in user, or 401.

    The counterpart to `optional_user`, for the one thing in this API that is genuinely
    private: a person's own saved conversations. Everything else stays anonymous-friendly on
    purpose, so this is deliberately a separate dependency rather than a flag. A route either
    requires an account or it does not, and that should be visible in its signature.
    """
    token = _bearer_token(request)
    if token is None:
        raise HTTPException(status_code=401, detail="Sign in to view your conversations.")
    # `verify_token` raises 401 itself on a bad signature, expiry, issuer or audience.
    return await verify_token(token)


async def optional_user(request: Request) -> AuthenticatedUser | None:
    """FastAPI dependency: the signed-in user, or None when the request is anonymous."""
    settings = get_settings()
    token = _bearer_token(request)

    if token is None:
        if settings.require_auth:
            raise HTTPException(status_code=401, detail="authentication required")
        return None

    return await verify_token(token)
