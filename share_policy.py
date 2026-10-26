"""Expiry applies to the distributed GUI only, never the owner's main.py CLI."""
from datetime import datetime, timedelta, timezone

HONG_KONG = timezone(timedelta(hours=8), name="Asia/Hong_Kong")
EXPIRES_AT = datetime(2026, 11, 6, tzinfo=HONG_KONG)


class ShareExpiredError(Exception):
    pass


def access_allowed(now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("An aware timestamp is required")
    return now.astimezone(HONG_KONG) < EXPIRES_AT


def require_access():
    if not access_allowed():
        raise ShareExpiredError()
