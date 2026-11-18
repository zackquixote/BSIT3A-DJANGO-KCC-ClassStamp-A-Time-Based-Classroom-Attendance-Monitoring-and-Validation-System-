"""
# // ==============================================================================
# // KCC CLASSSTAMP - ATTENDANCE REPORT RANGE RESOLVER
# // ==============================================================================
# // One place that turns a report request ("this week", "prelim", "custom
# // 2026-11-01..2026-11-15") into a real start/end date pair for the teacher and
# // admin attendance exports. Grading periods come from the admin-managed
# // GradingPeriod rows, never from a hard-coded meeting count.
# // ==============================================================================
"""

from datetime import date, timedelta

from django.utils import timezone

from apps.core.models import GradingPeriod

PERIOD_CODES = (
    GradingPeriod.CODE_PRELIM,
    GradingPeriod.CODE_MIDTERM,
    GradingPeriod.CODE_FINALS,
)


def available_grading_periods(class_obj):
    """Ordered GradingPeriod rows for the class's academic year."""
    year = getattr(class_obj, 'academic_year', None)
    if year is None:
        return []
    return list(year.grading_periods.all().order_by('start_date'))


def _format_window(start, end):
    if start and end:
        if start == end:
            return start.strftime('%b %d, %Y')
        return f'{start:%b %d, %Y} – {end:%b %d, %Y}'
    return 'All recorded meetings'


def resolve_report_range(
    class_obj, *, period='', range_key='term', start='', end='', today=None,
):
    """
    Resolve a report selection into:
        {key, label, start, end, period, error}

    - period=prelim/midterm/finals uses the configured GradingPeriod dates.
    - range_key=week uses the current Monday–Sunday window.
    - range_key=custom requires both ISO dates.
    - range_key=term/all leaves both bounds empty.
    """
    today = today or timezone.localdate()
    period = (period or '').strip().upper()
    range_key = (range_key or 'term').strip().lower()

    if period:
        if period not in PERIOD_CODES:
            return {
                'key': 'term', 'label': 'Whole Term', 'start': None, 'end': None,
                'period': None, 'error': 'Unknown grading period.',
            }
        configured = {
            row.code: row for row in available_grading_periods(class_obj)
        }.get(period)
        if configured is None:
            return {
                'key': period.lower(),
                'label': period.title(),
                'start': None, 'end': None, 'period': None,
                'error': (
                    'Grading periods are not configured for this term. '
                    'Ask an administrator to set the Prelim, Midterm, and Finals dates.'
                ),
            }
        return {
            'key': period.lower(),
            'label': configured.get_code_display(),
            'start': configured.start_date,
            'end': configured.end_date,
            'period': configured,
            'error': '',
        }

    if range_key in ('prelim', 'midterm', 'finals'):
        return resolve_report_range(class_obj, period=range_key, today=today)

    if range_key == 'week':
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        return {
            'key': 'week',
            'label': f'This Week ({_format_window(monday, sunday)})',
            'start': monday,
            'end': sunday,
            'period': None,
            'error': '',
        }

    if range_key == 'custom':
        try:
            start_date = date.fromisoformat((start or '').strip())
            end_date = date.fromisoformat((end or '').strip())
        except ValueError:
            return {
                'key': 'custom', 'label': 'Custom Range', 'start': None, 'end': None,
                'period': None,
                'error': 'Choose both a start date and an end date for the custom range.',
            }
        if start_date > end_date:
            return {
                'key': 'custom', 'label': 'Custom Range', 'start': None, 'end': None,
                'period': None,
                'error': 'The custom range start date must be on or before the end date.',
            }
        year = getattr(class_obj, 'academic_year', None)
        if year is not None and (start_date < year.starts_on or end_date > year.ends_on):
            return {
                'key': 'custom', 'label': 'Custom Range', 'start': None, 'end': None,
                'period': None,
                'error': (
                    f'The custom range must fit inside {year.name} '
                    f'({year.starts_on:%b %d, %Y} – {year.ends_on:%b %d, %Y}).'
                ),
            }
        return {
            'key': 'custom',
            'label': f'Custom Range ({_format_window(start_date, end_date)})',
            'start': start_date,
            'end': end_date,
            'period': None,
            'error': '',
        }

    return {
        'key': 'term',
        'label': 'Whole Term',
        'start': None,
        'end': None,
        'period': None,
        'error': '',
    }
