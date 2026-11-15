"""
# // ==============================================================================
# // KCC CLASSSTAMP - TIMEZONE-SAFE DATE WINDOWS
# // ==============================================================================
# // MySQL answers __year / __month / __date through CONVERT_TZ(), which returns
# // NULL unless the server has timezone tables loaded — the calendar tile read
# // "0 events this month" over a November full of holidays. These tests pin the
# // half-open range replacement: an event stored at 16:00 UTC (midnight in
# // Manila) must still count as today / this month.
# // ==============================================================================
"""

import datetime

from django.contrib.auth import get_user_model
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AcademicEvent, AcademicYear, AuditEvent, Department, Profile
from apps.core.views.helpers.date_windows import day_bounds, month_bounds, year_bounds

User = get_user_model()
PASSWORD = 'WindowPass!2026'


class DateWindowMathTests(SimpleTestCase):
    def test_day_bounds_is_half_open_local_midnight(self):
        day = datetime.date(2026, 11, 15)
        start, end = day_bounds(day)
        self.assertEqual(timezone.localtime(start).date(), day)
        self.assertEqual(timezone.localtime(start).time(), datetime.time.min)
        self.assertEqual(end - start, datetime.timedelta(days=1))

    def test_month_bounds_handles_december_rollover(self):
        start, end = month_bounds(datetime.date(2026, 12, 15))
        self.assertEqual(timezone.localtime(start), timezone.make_aware(datetime.datetime(2026, 12, 1)))
        self.assertEqual(timezone.localtime(end), timezone.make_aware(datetime.datetime(2027, 1, 1)))

    def test_year_bounds_covers_the_whole_year(self):
        start, end = year_bounds(2026)
        self.assertEqual(timezone.localtime(start).year, 2026)
        self.assertEqual(timezone.localtime(end).year, 2027)


class CalendarKpiWindowTests(TestCase):
    """The tile and the Today panel must see events stored at 16:00 UTC."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(username='win_admin', password=PASSWORD)
        Profile.objects.create(user=cls.admin, role=Profile.ROLE_ADMIN)
        cls.year = AcademicYear.objects.create(
            name='2026-2027 Windows',
            starts_on=datetime.date(2026, 6, 1),
            ends_on=datetime.date(2027, 3, 31),
            is_active=True,
        )

    def _client(self):
        client = Client()
        client.force_login(self.admin)
        return client

    def _event(self, start_local, title, days=0):
        end_local = start_local + datetime.timedelta(days=days)
        return AcademicEvent.objects.create(
            title=title, category=AcademicEvent.CATEGORY_HOLIDAY,
            start_datetime=start_local, end_datetime=end_local,
            is_all_day=True, academic_year=self.year,
        )

    def test_this_month_counts_an_event_at_local_midnight(self):
        today = timezone.localdate()
        month_first = today.replace(day=1)
        start = timezone.make_aware(datetime.datetime.combine(month_first, datetime.time.min))
        self._event(start, 'First of the Month Holiday')

        response = self._client().get(reverse('admin_calendar'))
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.context['this_month_count'], 1)
        # the stored value really is the previous UTC day — that is the trap
        stored = AcademicEvent.objects.get(title='First of the Month Holiday').start_datetime
        self.assertEqual(timezone.localtime(stored).date(), month_first)

    def test_today_panel_includes_an_all_day_event(self):
        today = timezone.localdate()
        start = timezone.make_aware(datetime.datetime.combine(today, datetime.time.min))
        self._event(start, 'Today Holiday')

        response = self._client().get(reverse('admin_calendar'))
        titles = [event.title for event in response.context['today_events']]
        self.assertIn('Today Holiday', titles)

    def test_today_panel_excludes_yesterday(self):
        yesterday = timezone.localdate() - datetime.timedelta(days=1)
        start = timezone.make_aware(datetime.datetime.combine(yesterday, datetime.time.min))
        self._event(start, 'Yesterday Holiday')

        response = self._client().get(reverse('admin_calendar'))
        titles = [event.title for event in response.context['today_events']]
        self.assertNotIn('Yesterday Holiday', titles)

    def test_open_ended_event_overlapping_today_is_listed(self):
        today = timezone.localdate()
        start = timezone.make_aware(datetime.datetime.combine(today - datetime.timedelta(days=2), datetime.time.min))
        end = timezone.make_aware(datetime.datetime.combine(today + datetime.timedelta(days=2), datetime.time.min))
        AcademicEvent.objects.create(
            title='Week Long Festival', category=AcademicEvent.CATEGORY_COLLEGE_ACTIVITY,
            start_datetime=start, end_datetime=end, is_all_day=True, academic_year=self.year,
        )
        response = self._client().get(reverse('admin_calendar'))
        titles = [event.title for event in response.context['today_events']]
        self.assertIn('Week Long Festival', titles)


class TeacherYearFilterTests(TestCase):
    """The 'year joined' dropdown and filter must not depend on SQL extracts."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(username='year_admin', password=PASSWORD)
        Profile.objects.create(user=cls.admin, role=Profile.ROLE_ADMIN)
        cls.department = Department.objects.create(code='WIN', name='Window Department')
        teacher = User.objects.create_user(username='year_teacher', password=PASSWORD)
        User.objects.filter(pk=teacher.pk).update(date_joined=timezone.make_aware(
            datetime.datetime(2024, 7, 1, 9, 0)))
        Profile.objects.create(
            user=teacher, role=Profile.ROLE_TEACHER,
            department=cls.department, employee_number='WIN-T1',
        )

    def test_year_choices_include_join_year(self):
        client = Client()
        client.force_login(self.admin)
        response = client.get(reverse('teacher_list'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(2024, response.context['year_choices'])

    def test_filter_by_year_returns_the_teacher(self):
        client = Client()
        client.force_login(self.admin)
        response = client.get(reverse('teacher_list') + '?year_joined=2024')
        self.assertEqual(response.status_code, 200)
        usernames = [teacher.user.username for teacher in response.context['teachers']]
        self.assertIn('year_teacher', usernames)


class AuditDateFilterTests(TestCase):
    """The audit log's date filter must match the local day."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(username='audit_admin', password=PASSWORD)
        Profile.objects.create(user=cls.admin, role=Profile.ROLE_ADMIN)
        AuditEvent.objects.create(
            actor=cls.admin, action='WINDOW_TEST_EVENT',
            object_type='Profile', object_id=str(cls.admin.pk),
            reason='Created for the date-window regression test',
        )

    def test_filter_by_today_finds_the_event(self):
        client = Client()
        client.force_login(self.admin)
        today = timezone.localdate().isoformat()
        response = client.get(reverse('admin_audit_log') + f'?date={today}')
        self.assertEqual(response.status_code, 200)
        actions = [event.action for event in response.context['events']]
        self.assertIn('WINDOW_TEST_EVENT', actions)

    def test_filter_by_other_day_excludes_it(self):
        client = Client()
        client.force_login(self.admin)
        other = (timezone.localdate() - datetime.timedelta(days=30)).isoformat()
        response = client.get(reverse('admin_audit_log') + f'?date={other}')
        self.assertEqual(response.status_code, 200)
        actions = [event.action for event in response.context['events']]
        self.assertNotIn('WINDOW_TEST_EVENT', actions)
