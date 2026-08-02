"""Rate-limiting and auth tests. No database, no network."""

import jwt
import pytest
from fastapi import HTTPException

from winchat_api.config import get_settings
from winchat_api.security.auth import optional_user, verify_token
from winchat_api.security.rate_limit import (
    anonymous_subject,
    check_limits,
    user_subject,
)

# Long enough to keep PyJWT from warning about HMAC key length in test output.
SECRET = "test-secret-long-enough-for-hs256-abcdefgh"


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class _FakePool:
    """Returns one canned counts row, standing in for the usage_events query."""

    def __init__(self, *, subject_hour=0, subject_day=0, global_day=0):
        self.row = {
            "subject_hour": subject_hour,
            "subject_day": subject_day,
            "global_day": global_day,
        }

    async def fetchrow(self, *args, **kwargs):
        return self.row


# ----------------------------------------------------------------- subjects


def test_an_anonymous_subject_never_stores_the_raw_address():
    """Rate limiting must distinguish clients without identifying people."""
    subject = anonymous_subject("203.0.113.7")

    assert "203.0.113.7" not in subject.key
    assert subject.kind == "anonymous"


def test_the_same_address_maps_to_the_same_subject():
    assert anonymous_subject("203.0.113.7") == anonymous_subject("203.0.113.7")


def test_different_addresses_map_to_different_subjects():
    assert anonymous_subject("203.0.113.7") != anonymous_subject("203.0.113.8")


def test_rotating_the_salt_changes_every_anonymous_subject(monkeypatch):
    before = anonymous_subject("203.0.113.7")
    monkeypatch.setenv("RATE_LIMIT_SALT", "a-different-salt")
    get_settings.cache_clear()

    assert anonymous_subject("203.0.113.7") != before


def test_a_signed_in_subject_is_scoped_by_user_id():
    subject = user_subject("f0a1")

    assert subject.kind == "user"
    assert subject.key == "user:f0a1"


# ----------------------------------------------------------------- limits


async def test_a_fresh_caller_is_allowed():
    decision = await check_limits(_FakePool(), user_subject("u1"))

    assert decision.allowed is True


async def test_the_hourly_limit_blocks(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_HOUR", "5")
    get_settings.cache_clear()

    decision = await check_limits(_FakePool(subject_hour=5), user_subject("u1"))

    assert decision.allowed is False
    assert decision.scope == "subject_hour"
    assert decision.retry_after_s > 0


async def test_the_daily_limit_blocks_even_within_the_hourly_one(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_HOUR", "100")
    monkeypatch.setenv("RATE_LIMIT_PER_DAY", "10")
    get_settings.cache_clear()

    decision = await check_limits(_FakePool(subject_hour=1, subject_day=10), user_subject("u1"))

    assert decision.allowed is False
    assert decision.scope == "subject_day"


async def test_the_global_breaker_outranks_a_well_behaved_user(monkeypatch):
    """Per-user limits do not bound total spend, because users are not bounded."""
    monkeypatch.setenv("RATE_LIMIT_GLOBAL_PER_DAY", "1000")
    get_settings.cache_clear()

    decision = await check_limits(
        _FakePool(subject_hour=0, subject_day=0, global_day=1000), user_subject("u1")
    )

    assert decision.allowed is False
    assert decision.scope == "global_day"


async def test_the_breaker_message_does_not_leak_the_threshold(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_GLOBAL_PER_DAY", "1000")
    get_settings.cache_clear()

    decision = await check_limits(_FakePool(global_day=1000), user_subject("u1"))

    assert "1000" not in decision.reason


# ----------------------------------------------------------------- auth


async def test_garbage_is_not_a_token():
    with pytest.raises(HTTPException) as raised:
        await verify_token("not-a-jwt")

    assert raised.value.status_code == 401


async def test_an_unsigned_token_is_rejected(monkeypatch):
    """The classic JWT attack: alg=none with whatever claims the attacker likes."""
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
    get_settings.cache_clear()
    forged = jwt.encode({"sub": "admin", "aud": "authenticated"}, key="", algorithm="none")

    with pytest.raises(HTTPException) as raised:
        await verify_token(forged)

    assert raised.value.status_code == 401


async def test_a_token_signed_with_the_wrong_secret_is_rejected(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
    get_settings.cache_clear()
    forged = jwt.encode(
        {"sub": "u1", "aud": "authenticated", "exp": 4102444800},
        "a-different-secret-of-sufficient-length",
        algorithm="HS256",
    )

    with pytest.raises(HTTPException):
        await verify_token(forged)


async def test_an_expired_token_is_rejected(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
    get_settings.cache_clear()
    expired = jwt.encode(
        {"sub": "u1", "aud": "authenticated", "exp": 1000000},
        SECRET,
        algorithm="HS256",
    )

    with pytest.raises(HTTPException) as raised:
        await verify_token(expired)

    assert raised.value.detail == "token expired"


async def test_a_token_for_another_audience_is_rejected(monkeypatch):
    """Supabase issues tokens for several audiences; only 'authenticated' is ours."""
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
    get_settings.cache_clear()
    other = jwt.encode(
        {"sub": "u1", "aud": "some-other-service", "exp": 4102444800},
        SECRET,
        algorithm="HS256",
    )

    with pytest.raises(HTTPException):
        await verify_token(other)


async def test_a_valid_token_yields_the_user(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
    get_settings.cache_clear()
    token = jwt.encode(
        {"sub": "u1", "aud": "authenticated", "exp": 4102444800, "email": "a@b.test"},
        SECRET,
        algorithm="HS256",
    )

    user = await verify_token(token)

    assert user.id == "u1"
    assert user.email == "a@b.test"


class _Request:
    def __init__(self, headers: dict[str, str] | None = None):
        self.headers = headers or {}


async def test_an_anonymous_request_is_allowed_by_default():
    """The FAQ is public; gating a public question behind a login is theatre."""
    assert await optional_user(_Request()) is None


async def test_anonymous_is_refused_when_auth_is_required(monkeypatch):
    monkeypatch.setenv("REQUIRE_AUTH", "true")
    get_settings.cache_clear()

    with pytest.raises(HTTPException) as raised:
        await optional_user(_Request())

    assert raised.value.status_code == 401


async def test_a_non_bearer_authorization_header_is_treated_as_anonymous():
    assert await optional_user(_Request({"authorization": "Basic abc"})) is None
