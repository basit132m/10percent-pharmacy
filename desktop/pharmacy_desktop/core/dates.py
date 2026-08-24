"""Date helpers.

Dates are stored as plain ``YYYY-MM-DD`` strings: they sort correctly in SQL,
they read correctly in a backup, and a medicine expires *on a day* — there is
no timezone in that.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta

ISO = "%Y-%m-%d"
DISPLAY = "%d-%b-%Y"


def today() -> date:
    return date.today()


def today_iso() -> str:
    return date.today().strftime(ISO)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def parse_date(value) -> date | None:
    """Read a date the way a data-entry operator might have typed it."""
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in (ISO, "%d-%m-%Y", "%d/%m/%Y", "%d-%b-%Y", "%d %b %Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    # "12/2027" or "2027-12" — an expiry printed as month and year only.
    for fmt in ("%m/%Y", "%m-%Y", "%Y-%m", "%b-%Y", "%b %Y"):
        try:
            parsed = datetime.strptime(text, fmt).date()
        except ValueError:
            continue
        return end_of_month(parsed)
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        return None


def to_iso(value) -> str | None:
    parsed = parse_date(value)
    return parsed.strftime(ISO) if parsed else None


def end_of_month(value: date) -> date:
    last = calendar.monthrange(value.year, value.month)[1]
    return value.replace(day=last)


def fmt_date(value, fallback: str = "") -> str:
    parsed = parse_date(value)
    return parsed.strftime(DISPLAY) if parsed else fallback


def fmt_datetime(value, fallback: str = "") -> str:
    if not value:
        return fallback
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return fmt_date(value, fallback)
    return parsed.strftime("%d-%b-%Y %I:%M %p")


def days_until(value) -> int | None:
    parsed = parse_date(value)
    return (parsed - date.today()).days if parsed else None


def add_days(value: date, days: int) -> date:
    return value + timedelta(days=days)


def month_start(value: date | None = None) -> date:
    value = value or date.today()
    return value.replace(day=1)


def date_range(period: str) -> tuple[str, str]:
    """Named ranges the reports screen offers, as ``(from_iso, to_iso)``."""
    current = date.today()
    if period == "today":
        start = end = current
    elif period == "yesterday":
        start = end = current - timedelta(days=1)
    elif period == "week":
        start, end = current - timedelta(days=current.weekday()), current
    elif period == "last7":
        start, end = current - timedelta(days=6), current
    elif period == "month":
        start, end = month_start(current), current
    elif period == "last_month":
        last_day_prev = month_start(current) - timedelta(days=1)
        start, end = month_start(last_day_prev), last_day_prev
    elif period == "last30":
        start, end = current - timedelta(days=29), current
    elif period == "year":
        start, end = current.replace(month=1, day=1), current
    else:  # "all"
        start, end = date(2000, 1, 1), current
    return start.strftime(ISO), end.strftime(ISO)
