"""Network time expiry for the distributed Windows GUI only.

The owner's source CLI and owner_entry are unaffected. The shared executable
fails closed when an HTTPS time source cannot be reached, without deleting files.
"""
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import secrets
from threading import Lock
import time

import requests

HONG_KONG = timezone(timedelta(hours=8), name="Asia/Hong_Kong")
# Valid through 2026-11-20 23:59:59 in UTC+08:00.
EXPIRES_AT = datetime(2026, 11, 21, tzinfo=HONG_KONG)
# Use monotonic only for a short-lived offset from the last online time check.
REFRESH_SECONDS = 30
FAILURE_RETRY_SECONDS = 15
TIME_ENDPOINTS = (
    "https://www.baidu.com/",
    "https://www.qq.com/",
    "https://www.cloudflare.com/cdn-cgi/trace",
)
_anchor = None  # (HTTPS-verified UTC timestamp, monotonic timestamp)
_failed_at = None
_lock = Lock()


class ShareExpiredError(Exception):
    """Shared edition is expired or its network time could not be verified."""


def _fetch_network_time():
    """Parse an HTTPS origin's RFC 7231 Date header, never the local clock."""
    headers = {"Cache-Control": "no-store, no-cache", "Pragma": "no-cache"}
    for url in TIME_ENDPOINTS:
        try:
            # A random query avoids stale cached Date headers; TLS stays enabled.
            with requests.get(
                url,
                params={"time_check": secrets.token_hex(12)},
                headers=headers,
                timeout=(2, 3),
                stream=True,
                allow_redirects=False,
            ) as response:
                if not 200 <= response.status_code < 400:
                    continue
                stamp = parsedate_to_datetime(response.headers.get("Date", ""))
                if stamp.tzinfo is not None:
                    return stamp.astimezone(timezone.utc)
        except (requests.RequestException, TypeError, ValueError, OverflowError, IndexError):
            continue
    raise ShareExpiredError("HTTPS time verification unavailable")


def _verified_now():
    """Online-verifiable UTC time, anchored to monotonic for <=30 seconds."""
    global _anchor, _failed_at
    with _lock:
        current = time.monotonic()
        if _anchor is not None:
            verified, checked_at = _anchor
            elapsed = current - checked_at
            if 0 <= elapsed < REFRESH_SECONDS:
                return verified + timedelta(seconds=elapsed)
        if _failed_at is not None and 0 <= current - _failed_at < FAILURE_RETRY_SECONDS:
            raise ShareExpiredError("HTTPS time verification unavailable")
        # A failed refresh must not fall back to an old value or local clock.
        _anchor = None
        try:
            remote_now = _fetch_network_time()
        except ShareExpiredError:
            _failed_at = time.monotonic()
            raise
        _failed_at = None
        _anchor = (remote_now, time.monotonic())
        return remote_now


def access_allowed(now=None):
    """Check expiry; a provided aware time is for deterministic unit tests."""
    if now is None:
        try:
            now = _verified_now()
        except ShareExpiredError:
            return False
    if now.tzinfo is None:
        raise ValueError("An aware timestamp is required")
    return now.astimezone(HONG_KONG) < EXPIRES_AT


def require_access():
    if not access_allowed():
        raise ShareExpiredError()
