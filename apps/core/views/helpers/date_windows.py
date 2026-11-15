"""
# // ==============================================================================
# // KCC CLASSSTAMP - TIMEZONE-SAFE DATE WINDOWS
# // ==============================================================================
# // MySQL only converts DATETIME values between zones when its own timezone
# // tables are installed (mysql_tzinfo_to_sql). Without them CONVERT_TZ()
# // returns NULL, so Django's __year / __month / __date lookups silently match
# // nothing: the calendar tile read "0 events this month" while November was
# // full of holidays, and the "today" panels were empty.
# //
# // Every "today" / "this month" / "this year" query is therefore expressed as a
# // half-open range on the stored (UTC) value. Ranges behave identically on
# // SQLite (PythonAnywhere) and on MySQL, whatever the server's timezone tables.
# // ==============================================================================
"""

from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.utils import timezone


def _start_of(day):
    """Midnight at the start of ``day`` in the project timezone."""
    value = datetime.combine(day, time.min)
    return timezone.make_aware(value) if settings.USE_TZ else value


def day_bounds(day):
    """Half-open [start, end) window covering one local calendar day."""
    start = _start_of(day)
    return start, start + timedelta(days=1)


def month_bounds(day):
    """Half-open [start, end) window covering the month that contains ``day``."""
    first = day.replace(day=1)
    if first.month == 12:
        following = date(first.year + 1, 1, 1)
    else:
        following = date(first.year, first.month + 1, 1)
    return _start_of(first), _start_of(following)


def year_bounds(year):
    """Half-open [start, end) window covering one local calendar year."""
    return _start_of(date(year, 1, 1)), _start_of(date(year + 1, 1, 1))
