"""
# // ==============================================================================
# // KCC CLASSSTAMP - PHILIPPINE HOLIDAY CATALOG & AUTOMATIC CALENDAR SEEDER
# // ==============================================================================
# // Subsystem: Academic Administration & Calendar Logistics
# // Description: Generates official Republic of the Philippines regular holidays
# //   and special non-working days (including movable Holy Week feasts and
# //   National Heroes Day) and provisions them into AcademicEvent with idempotent
# //   deduplication and audit logging.
# // Legal Basis: Republic Act No. 9492 & Malacañang Proclamations
# // ==============================================================================
"""

import datetime
from django.db import transaction
from django.utils import timezone

from apps.core.models import AcademicEvent, AcademicYear, AuditEvent


def calculate_easter_sunday(year: int) -> datetime.date:
    """
    // Computes Gregorian Easter Sunday using the Meeus/Jones/Butcher algorithm.
    // Accurately predicts Western Easter Sunday for any year.
    """
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return datetime.date(year, month, day)


def get_last_monday_of_august(year: int) -> datetime.date:
    """Computes the date of National Heroes Day (Last Monday of August)."""
    d = datetime.date(year, 8, 31)
    while d.weekday() != 0:  # 0 is Monday
        d -= datetime.timedelta(days=1)
    return d


def get_philippine_holidays(year: int) -> list:
    """
    // Compiles official Philippine regular and special non-working holidays for a given year.
    // Returns a list of dicts:
    //   title, date, description, is_regular (True for Regular, False for Special Non-Working)
    """
    easter = calculate_easter_sunday(year)
    maundy_thursday = easter - datetime.timedelta(days=3)
    good_friday = easter - datetime.timedelta(days=2)
    black_saturday = easter - datetime.timedelta(days=1)
    national_heroes_day = get_last_monday_of_august(year)

    holidays = [
        # Regular Holidays
        {
            'title': "New Year's Day",
            'date': datetime.date(year, 1, 1),
            'description': "National Regular Holiday — Start of the Gregorian Year.",
            'is_regular': True,
        },
        {
            'title': "Maundy Thursday",
            'date': maundy_thursday,
            'description': "National Regular Holiday — Holy Week observance.",
            'is_regular': True,
        },
        {
            'title': "Good Friday",
            'date': good_friday,
            'description': "National Regular Holiday — Holy Week observance.",
            'is_regular': True,
        },
        {
            'title': "Araw ng Kagitingan (Day of Valor)",
            'date': datetime.date(year, 4, 9),
            'description': "National Regular Holiday — Commemorating the Fall of Bataan and Filipino heroism.",
            'is_regular': True,
        },
        {
            'title': "Labor Day",
            'date': datetime.date(year, 5, 1),
            'description': "National Regular Holiday — Commemorating the Filipino workforce.",
            'is_regular': True,
        },
        {
            'title': "Philippine Independence Day",
            'date': datetime.date(year, 6, 12),
            'description': "National Regular Holiday — Proclamation of Philippine Independence (1898).",
            'is_regular': True,
        },
        {
            'title': "National Heroes Day",
            'date': national_heroes_day,
            'description': "National Regular Holiday — Honoring all heroes of the nation.",
            'is_regular': True,
        },
        {
            'title': "Bonifacio Day",
            'date': datetime.date(year, 11, 30),
            'description': "National Regular Holiday — Birth anniversary of Andres Bonifacio.",
            'is_regular': True,
        },
        {
            'title': "Christmas Day",
            'date': datetime.date(year, 12, 25),
            'description': "National Regular Holiday — Solemnity of the Nativity of the Lord.",
            'is_regular': True,
        },
        {
            'title': "Rizal Day",
            'date': datetime.date(year, 12, 30),
            'description': "National Regular Holiday — Martyrdom anniversary of Dr. Jose Rizal.",
            'is_regular': True,
        },

        # Special Non-Working Holidays
        {
            'title': "EDSA People Power Revolution Anniversary",
            'date': datetime.date(year, 2, 25),
            'description': "Special Non-Working Day — Restoration of Philippine Democracy.",
            'is_regular': False,
        },
        {
            'title': "Black Saturday",
            'date': black_saturday,
            'description': "Special Non-Working Day — Holy Week Easter Vigil.",
            'is_regular': False,
        },
        {
            'title': "Ninoy Aquino Day",
            'date': datetime.date(year, 8, 21),
            'description': "Special Non-Working Day — Commemorating the martyrdom of Benigno Aquino Jr.",
            'is_regular': False,
        },
        {
            'title': "All Saints' Day (Undas)",
            'date': datetime.date(year, 11, 1),
            'description': "Special Non-Working Day — Solemnity of All Saints.",
            'is_regular': False,
        },
        {
            'title': "All Souls' Day",
            'date': datetime.date(year, 11, 2),
            'description': "Special Non-Working Day — Commemoration of All the Faithful Departed.",
            'is_regular': False,
        },
        {
            'title': "Feast of the Immaculate Conception",
            'date': datetime.date(year, 12, 8),
            'description': "Special Non-Working Day — Principal Patroness of the Republic of the Philippines (RA 10966).",
            'is_regular': False,
        },
        {
            'title': "Christmas Eve",
            'date': datetime.date(year, 12, 24),
            'description': "Special Non-Working Day — Christmas Eve observance.",
            'is_regular': False,
        },
        {
            'title': "Last Day of the Year (New Year's Eve)",
            'date': datetime.date(year, 12, 31),
            'description': "Special Non-Working Day — Year-end holiday.",
            'is_regular': False,
        },
    ]

    return holidays


def seed_philippine_holidays(year: int, actor=None, academic_year=None) -> dict:
    """
    // Ingests official Philippine holidays into AcademicEvent with idempotent checking.
    //
    // Returns:
    //   { 'created_count': N, 'existing_count': M, 'holidays': [...] }
    """
    holiday_catalog = get_philippine_holidays(year)
    created_count = 0
    existing_count = 0
    created_events = []

    # Attempt to locate active academic year if none provided
    if not academic_year:
        academic_year = AcademicYear.objects.filter(is_active=True).first()

    with transaction.atomic():
        for h in holiday_catalog:
            d = h['date']
            start_dt = timezone.make_aware(datetime.datetime(d.year, d.month, d.day, 0, 0, 0))
            end_dt = timezone.make_aware(datetime.datetime(d.year, d.month, d.day, 23, 59, 59))

            # Idempotent deduplication:
            # Match by exact title and category within the day's datetime boundaries (avoids MySQL CONVERT_TZ / __date quirks)
            check_start = start_dt - datetime.timedelta(hours=6)
            check_end = end_dt + datetime.timedelta(hours=6)

            existing_qs = AcademicEvent.objects.filter(
                title=h['title'],
                category=AcademicEvent.CATEGORY_HOLIDAY,
                start_datetime__gte=check_start,
                start_datetime__lte=check_end
            )

            if existing_qs.exists():
                existing_count += 1
                # If duplicate entries exist for this holiday, prune the extras to keep database clean
                duplicates = list(existing_qs.order_by('id'))
                if len(duplicates) > 1:
                    for extra in duplicates[1:]:
                        extra.delete()
                continue

            event = AcademicEvent.objects.create(
                title=h['title'],
                description=f"{h['description']} ({'Regular Holiday' if h['is_regular'] else 'Special Non-Working Day'})",
                category=AcademicEvent.CATEGORY_HOLIDAY,
                status=AcademicEvent.STATUS_SCHEDULED,
                visibility=AcademicEvent.VISIBILITY_ALL,
                start_datetime=start_dt,
                end_datetime=end_dt,
                is_all_day=True,
                location="Nationwide / KCC Campus Closed",
                academic_year=academic_year,
                semester=AcademicEvent.SEMESTER_ALL,
                created_by=actor,
                updated_by=actor,
            )
            created_events.append(event)
            created_count += 1

        if created_count > 0:
            AuditEvent.objects.create(
                actor=actor,
                action='SEED_PH_HOLIDAYS',
                object_type='AcademicEvent',
                object_id=str(year),
                new_value=f"Provisioned {created_count} official Philippine holidays for year {year}.",
                reason=f"Automated Philippine holiday calendar ingestion by {actor.username if actor else 'System'}"
            )

    return {
        'created_count': created_count,
        'existing_count': existing_count,
        'total_in_catalog': len(holiday_catalog),
        'year': year,
    }
