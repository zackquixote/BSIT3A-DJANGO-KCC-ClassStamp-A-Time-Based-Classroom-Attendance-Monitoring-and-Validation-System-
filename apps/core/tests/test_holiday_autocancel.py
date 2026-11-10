"""
# // ==============================================================================
# // KCC CLASSSTAMP - HOLIDAY AUTO-CANCEL TESTS (task 2.3)
# // ==============================================================================
# // Creating a HOLIDAY AcademicEvent cancels SCHEDULED/OPEN sessions on those
# // dates. Deletion/cancellation does not restore them. Manual reopen stays.
# // ==============================================================================
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.utils import timezone

from apps.core.models import (
    AcademicEvent,
    AcademicYear,
    AuditEvent,
    Class,
    ClassSession,
    ClassSlot,
    Department,
    Profile,
    Program,
    Subject,
)
from apps.core.signals.holiday_signals import auto_cancel_sessions_on_holiday

MANILA = ZoneInfo('Asia/Manila')


class HolidayAutoCancelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.department = Department.objects.create(code='CCS', name='Computer Studies')
        cls.program = Program.objects.create(
            department=cls.department, code='BSIT', name='Information Technology',
        )
        cls.subject = Subject.objects.create(code='IT311', name='Web Development')
        cls.year = AcademicYear.objects.create(
            name='2026-2027',
            starts_on=date(2026, 6, 1),
            ends_on=date(2027, 3, 31),
            is_active=True,
        )
        from django.contrib.auth import get_user_model
        User = get_user_model()
        cls.teacher_user = User.objects.create_user(username='hol_teacher')
        cls.teacher = Profile.objects.create(
            user=cls.teacher_user, role=Profile.ROLE_TEACHER, department=cls.department,
        )
        cls.class_obj = Class.objects.create(
            academic_year=cls.year,
            class_code='BSIT-3A-IT311',
            section_code='BSIT-3A',
            subject=cls.subject,
            teacher_profile=cls.teacher,
            program=cls.program,
            year_level=3,
        )
        # Wednesday = 2026-11-11 (a fixed Wednesday in the term).
        cls.wednesday = date(2026, 11, 11)
        cls.slot = ClassSlot.objects.create(
            class_obj=cls.class_obj, weekday=2,
            starts_at=time(8, 0), ends_at=time(10, 0), room='IT-Lab 1',
        )

    def _session(self, session_date, status=ClassSession.STATUS_SCHEDULED):
        return ClassSession.objects.create(
            slot=self.slot, session_date=session_date, status=status,
        )

    def _holiday(self, day, title='National Holiday'):
        return AcademicEvent.objects.create(
            title=title,
            category=AcademicEvent.CATEGORY_HOLIDAY,
            start_datetime=datetime(day.year, day.month, day.day, 0, 0, tzinfo=MANILA),
            end_datetime=datetime(day.year, day.month, day.day, 23, 59, tzinfo=MANILA),
            academic_year=self.year,
        )

    def test_scheduled_session_on_holiday_is_cancelled_and_audited(self):
        session = self._session(self.wednesday)
        holiday = self._holiday(self.wednesday)

        session.refresh_from_db()
        self.assertEqual(session.status, ClassSession.STATUS_CANCELED)
        self.assertIn(holiday.title, session.cancellation_reason)
        self.assertTrue(
            AuditEvent.objects.filter(
                action='SESSION_AUTO_CANCELLED',
                object_id=str(session.pk),
            ).exists()
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                action='HOLIDAY_AUTO_CANCEL_COMPLETE',
                object_id=str(holiday.pk),
            ).exists()
        )

    def test_open_session_is_also_cancelled(self):
        session = self._session(self.wednesday, status=ClassSession.STATUS_OPEN)
        self._holiday(self.wednesday)
        session.refresh_from_db()
        self.assertEqual(session.status, ClassSession.STATUS_CANCELED)

    def test_closed_and_already_cancelled_sessions_are_untouched(self):
        # (slot, session_date) is unique, so the already-cancelled session
        # lives on a second slot that also meets on the holiday date.
        second_slot = ClassSlot.objects.create(
            class_obj=self.class_obj, weekday=2,
            starts_at=time(10, 0), ends_at=time(12, 0), room='IT-Lab 2',
        )
        closed = self._session(self.wednesday, status=ClassSession.STATUS_CLOSED)
        already = ClassSession.objects.create(
            slot=second_slot, session_date=self.wednesday,
            status=ClassSession.STATUS_CANCELED,
        )
        self._holiday(self.wednesday)
        closed.refresh_from_db()
        already.refresh_from_db()
        self.assertEqual(closed.status, ClassSession.STATUS_CLOSED)
        self.assertEqual(already.status, ClassSession.STATUS_CANCELED)

    def test_other_dates_are_untouched(self):
        other = self._session(self.wednesday + timedelta(days=1))
        self._holiday(self.wednesday)
        other.refresh_from_db()
        self.assertEqual(other.status, ClassSession.STATUS_SCHEDULED)

    def test_deleting_holiday_does_not_restore_sessions(self):
        session = self._session(self.wednesday)
        holiday = self._holiday(self.wednesday)
        session.refresh_from_db()
        self.assertEqual(session.status, ClassSession.STATUS_CANCELED)

        holiday.delete()
        session.refresh_from_db()
        self.assertEqual(session.status, ClassSession.STATUS_CANCELED)

    def test_cancelling_the_holiday_does_not_restore_sessions(self):
        session = self._session(self.wednesday)
        holiday = self._holiday(self.wednesday)
        session.refresh_from_db()
        self.assertEqual(session.status, ClassSession.STATUS_CANCELED)

        holiday.status = AcademicEvent.STATUS_CANCELED
        holiday.save()
        session.refresh_from_db()
        self.assertEqual(session.status, ClassSession.STATUS_CANCELED)

    def test_non_holiday_events_do_not_cancel(self):
        session = self._session(self.wednesday)
        AcademicEvent.objects.create(
            title='Intramurals',
            category=AcademicEvent.CATEGORY_COLLEGE_ACTIVITY,
            start_datetime=datetime(2026, 11, 11, 8, 0, tzinfo=MANILA),
            end_datetime=datetime(2026, 11, 11, 17, 0, tzinfo=MANILA),
            academic_year=self.year,
        )
        session.refresh_from_db()
        self.assertEqual(session.status, ClassSession.STATUS_SCHEDULED)

    def test_signal_is_registered(self):
        # Saving an event through the ORM must fire the receiver.
        from django.test.utils import captured_stdout

        session = self._session(self.wednesday)
        # If the signal were not registered, this would stay SCHEDULED.
        self._holiday(self.wednesday, title='Signal Check')
        session.refresh_from_db()
        self.assertEqual(session.status, ClassSession.STATUS_CANCELED)
