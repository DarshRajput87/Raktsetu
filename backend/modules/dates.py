"""Date helpers shared by the modules."""

from datetime import date, datetime, timezone
from typing import Any


def to_date(value: Any) -> date | None:
    """MongoDB datetime or ISO string -> date."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def utcnow() -> datetime:
    """Current UTC time without tzinfo, which is how MongoDB hands datetimes back."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
