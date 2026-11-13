"""One-time passwords, the SMS interface and the donor-contact rate limit.

All in memory, with the clock passed in so the rules can be tested.
"""

import hashlib
import hmac
import logging
import secrets
from datetime import date, datetime, timedelta
from typing import Protocol

log = logging.getLogger("raktsetu")


class SmsSender(Protocol):
    """Anything that can deliver a text message. Plug a real provider in here."""

    def send(self, phone: str, message: str) -> None: ...


class LogSmsSender:
    """Development sender: writes the message to the log instead of sending it."""

    def send(self, phone: str, message: str) -> None:
        log.info("SMS to %s: %s", phone, message)


class OtpStore:
    """6-digit login codes, stored hashed, valid for a few minutes, single use.

    A dict keyed by phone: issue and verify are O(1).
    """

    OK, WRONG, EXPIRED, MISSING, LOCKED = "ok", "wrong", "expired", "missing", "locked"

    def __init__(self, secret: str, ttl_seconds: int = 300, max_attempts: int = 5) -> None:
        self._secret = secret.encode()
        self._ttl = timedelta(seconds=ttl_seconds)
        self._max_attempts = max_attempts
        self._codes: dict[str, tuple[str, datetime, int]] = {}  # phone -> (hash, expires, attempts)

    def _hash(self, phone: str, otp: str) -> str:
        return hmac.new(self._secret, f"{phone}:{otp}".encode(), hashlib.sha256).hexdigest()

    def issue(self, phone: str, now: datetime) -> str:
        """Create a new code for the phone (replacing any earlier one) and return it."""
        otp = f"{secrets.randbelow(1_000_000):06d}"
        self._codes[phone] = (self._hash(phone, otp), now + self._ttl, 0)
        return otp

    def verify(self, phone: str, otp: str, now: datetime) -> str:
        """OK, WRONG, EXPIRED, MISSING (no code requested) or LOCKED (too many wrong tries)."""
        entry = self._codes.get(phone)
        if entry is None:
            return self.MISSING
        digest, expires, attempts = entry
        if now > expires:
            del self._codes[phone]
            return self.EXPIRED
        if attempts >= self._max_attempts:
            return self.LOCKED
        if not hmac.compare_digest(digest, self._hash(phone, otp)):
            self._codes[phone] = (digest, expires, attempts + 1)
            return self.WRONG
        del self._codes[phone]
        return self.OK


class ContactLimiter:
    """At most `limit` donor-contact views per user per day.

    A dict user -> (day, count); the count starts again when the day changes. O(1).
    """

    def __init__(self, limit: int = 20) -> None:
        self.limit = limit
        self._views: dict[str, tuple[date, int]] = {}

    def allow(self, user_id: str, today: date) -> bool:
        """Count one view. False (and nothing counted) once the daily limit is reached."""
        day, count = self._views.get(user_id, (today, 0))
        if day != today:
            count = 0
        if count >= self.limit:
            return False
        self._views[user_id] = (today, count + 1)
        return True

    def remaining(self, user_id: str, today: date) -> int:
        day, count = self._views.get(user_id, (today, 0))
        return self.limit if day != today else max(0, self.limit - count)
