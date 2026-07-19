"""Time helpers.

`datetime.utcnow()` is deprecated (Python 3.12+). We keep the database columns
naive (`DateTime` = timestamp *without* time zone) and compare naive datetimes
throughout, so we deliberately return a *naive* UTC value here — same semantics
as the old `datetime.utcnow()`, just without the deprecation. Introducing
timezone-aware datetimes would require making the columns `DateTime(timezone=True)`
and is a separate, larger change (see IMPLEMENTATION-PLAN).
"""

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Current UTC time as a naive datetime (no tzinfo)."""
    return datetime.now(UTC).replace(tzinfo=None)
