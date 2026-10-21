"""
# // ==============================================================================
# // KCC CLASSSTAMP - ACADEMIC CALENDAR AUTOMATED TEST SUITE
# // ==============================================================================
# // Subsystem: Quality Assurance — Academic Calendar Module
# // Description: Comprehensive integration tests covering:
# //   1. Strict RBAC enforcement (Admin only; Teacher/Student/Anonymous blocked)
# //   2. Event lifecycle CRUD (create, retrieve, edit, cancel/restore, delete)
# //   3. FullCalendar JSON feed filtering (date range, academic year, category, semester)
# //   4. Drag-and-drop / resize reschedule controller
# //   5. Server-side validation rules (date boundaries, required title, invalid IDs)
# //   6. Immutable AuditEvent logging for all state mutations
# // References: docs/02_SECURITY.md | docs/06_ADMIN_IMPROVEMENTS_ROADMAP.md
# // ==============================================================================
"""

from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import (
    AcademicEvent,
    AcademicYear,
    AttendanceRecord,
    AuditEvent,
    Class,
    ClassSession,
    ClassSlot,
    Department,
    Enrollment,
    Profile,
    Program,
    Subject,
)
from apps.core.views.helpers.dashboard_helpers import (
    _admin_dashboard_stats,
    _teacher_dashboard_stats,
    _student_dashboard_stats,
)

User = get_user_model()


class AcademicCalendarTests(TestCase):
    """Integration and RBAC tests for the Academic Calendar feature."""

    def setUp(self):
        # 1. Admin User
        self.admin_user = User.objects.create_user(
            username='admin_calendar_tester',
            password='AdminPassword123!',
            first_name='Admin',
            last_name='Officer'
        )
        self.admin_profile = Profile.objects.create(
            user=self.admin_user,
            role=Profile.ROLE_ADMIN
        )

        # 2. Teacher User
        self.teacher_user = User.objects.create_user(
            username='teacher_tester',
            password='TeacherPassword123!',
            first_name='Professor',
            last_name='Santos'
        )
        self.teacher_profile = Profile.objects.create(
            user=self.teacher_user,
            role=Profile.ROLE_TEACHER
        )

        # 3. Student User
        self.student_user = User.objects.create_user(
            username='student_tester',
            password='StudentPassword123!',
            first_name='Juan',
            last_name='Dela Cruz'
        )
        self.student_profile = Profile.objects.create(
            user=self.student_user,
            role=Profile.ROLE_STUDENT,
            student_number='2024-0099',
            approval_status=Profile.APPROVAL_APPROVED,
            qr_secret='e' * 64
        )

        # 4. Academic Years
        today = timezone.localdate()
        self.ay_active = AcademicYear.objects.create(
            name='2025-2026 1st Sem',
            starts_on=today - timedelta(days=30),
            ends_on=today + timedelta(days=90),
            is_active=True
        )
        self.ay_inactive = AcademicYear.objects.create(
            name='2024-2025 2nd Sem',
            starts_on=today - timedelta(days=365),
            ends_on=today - timedelta(days=180),
            is_active=False
        )

        # 5. Seed Test Events
        self.now = timezone.now()
        self.event1 = AcademicEvent.objects.create(
            title='Midterm Examinations',
            description='College-wide midterm exams for all degree programs.',
            category=AcademicEvent.CATEGORY_EXAMINATION,
            status=AcademicEvent.STATUS_SCHEDULED,
            visibility=AcademicEvent.VISIBILITY_ALL,
            start_datetime=self.now + timedelta(days=10),
            end_datetime=self.now + timedelta(days=15),
            is_all_day=True,
            location='Main Campus Classrooms',
            academic_year=self.ay_active,
            semester=AcademicEvent.SEMESTER_FIRST,
            created_by=self.admin_user,
        )

        self.event2 = AcademicEvent.objects.create(
            title='Ninoy Aquino Day',
            description='National Special Non-Working Holiday.',
            category=AcademicEvent.CATEGORY_HOLIDAY,
            status=AcademicEvent.STATUS_SCHEDULED,
            visibility=AcademicEvent.VISIBILITY_ALL,
            start_datetime=self.now + timedelta(days=20),
            end_datetime=self.now + timedelta(days=20, hours=23, minutes=59),
            is_all_day=True,
            academic_year=self.ay_active,
            semester=AcademicEvent.SEMESTER_ALL,
            created_by=self.admin_user,
        )

    # --------------------------------------------------------------------------
    # 1. RBAC & PERMISSION ENFORCEMENT
    # --------------------------------------------------------------------------
    def test_admin_can_access_calendar_dashboard(self):
        """Admin user can view the Academic Calendar page."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('admin_calendar'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/admin/calendar.html')
        self.assertIn('total_events', response.context)
        self.assertIn('active_academic_year', response.context)

    def test_anonymous_user_redirected_to_login(self):
        """Unauthenticated user is redirected to login for calendar view and APIs."""
        r_view = self.client.get(reverse('admin_calendar'))
        self.assertEqual(r_view.status_code, 302)
        self.assertIn('/?next=', r_view.url)

        r_feed = self.client.get(reverse('admin_calendar_events_json'))
        self.assertEqual(r_feed.status_code, 302)

        r_save = self.client.post(reverse('admin_calendar_event_save'), {'title': 'Hack'})
        self.assertEqual(r_save.status_code, 302)

    def test_teacher_cannot_access_calendar_admin(self):
        """Teacher role cannot access admin calendar view or modification APIs."""
        self.client.force_login(self.teacher_user)
        r_view = self.client.get(reverse('admin_calendar'))
        # role_required redirects non-authorized roles to their appropriate dashboard
        self.assertEqual(r_view.status_code, 302)

        r_save = self.client.post(reverse('admin_calendar_event_save'), {
            'title': 'Faculty Incursion',
            'start_datetime': '2026-10-25T08:00',
            'end_datetime': '2026-10-25T17:00',
            'category': AcademicEvent.CATEGORY_COLLEGE_ACTIVITY
        })
        self.assertEqual(r_save.status_code, 302)

    def test_student_cannot_access_calendar_admin(self):
        """Student role cannot access admin calendar view or modification APIs."""
        self.client.force_login(self.student_user)
        r_view = self.client.get(reverse('admin_calendar'))
        self.assertEqual(r_view.status_code, 302)

        r_save = self.client.post(reverse('admin_calendar_event_save'), {'title': 'Student Hack'})
        self.assertEqual(r_save.status_code, 302)

    # --------------------------------------------------------------------------
    # 2. EVENT RETRIEVAL & FILTERING
    # --------------------------------------------------------------------------
    def test_events_json_feed_returns_events_within_window(self):
        """JSON feed returns events intersecting the requested date window."""
        self.client.force_login(self.admin_user)
        start_str = (self.now + timedelta(days=5)).isoformat()
        end_str = (self.now + timedelta(days=30)).isoformat()

        response = self.client.get(reverse('admin_calendar_events_json'), {
            'start': start_str,
            'end': end_str,
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 2)
        event_titles = [d['title'] for d in data]
        self.assertIn('Midterm Examinations', event_titles)
        self.assertIn('Ninoy Aquino Day', event_titles)

    def test_events_json_feed_filters_by_category(self):
        """Feed correctly filters events by category code."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('admin_calendar_events_json'), {
            'category': AcademicEvent.CATEGORY_HOLIDAY,
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['title'], 'Ninoy Aquino Day')

    def test_events_json_feed_filters_by_academic_year(self):
        """Feed correctly filters by academic year ID."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('admin_calendar_events_json'), {
            'academic_year': self.ay_inactive.id,
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 0)

    def test_events_json_feed_search_query(self):
        """Feed searches title, description, or location."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('admin_calendar_events_json'), {
            'q': 'Gymnasium',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 0)

        response2 = self.client.get(reverse('admin_calendar_events_json'), {
            'q': 'Midterm',
        })
        self.assertEqual(response2.status_code, 200)
        self.assertEqual(len(response2.json()), 1)

    def test_get_single_event_details(self):
        """Single event details API returns complete serialized payload."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('admin_calendar_event_get', kwargs={'pk': self.event1.id}))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['event']['title'], 'Midterm Examinations')
        self.assertEqual(data['event']['extendedProps']['category'], AcademicEvent.CATEGORY_EXAMINATION)

    # --------------------------------------------------------------------------
    # 3. CREATE, UPDATE & AUDIT LOGGING
    # --------------------------------------------------------------------------
    def test_create_event_success_and_audit_event_logged(self):
        """Admin can create an academic event and AuditEvent is created."""
        self.client.force_login(self.admin_user)
        start_str = (self.now + timedelta(days=40)).strftime('%Y-%m-%dT%H:%M')
        end_str = (self.now + timedelta(days=40, hours=4)).strftime('%Y-%m-%dT%H:%M')

        response = self.client.post(reverse('admin_calendar_event_save'), {
            'title': 'General Faculty Assembly',
            'description': 'Mandatory term planning and curriculum review.',
            'category': AcademicEvent.CATEGORY_MEETING,
            'status': AcademicEvent.STATUS_SCHEDULED,
            'visibility': AcademicEvent.VISIBILITY_FACULTY,
            'start_datetime': start_str,
            'end_datetime': end_str,
            'is_all_day': 'false',
            'location': 'Audio-Visual Room 1',
            'academic_year': self.ay_active.id,
            'semester': AcademicEvent.SEMESTER_FIRST,
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')

        # Verify DB creation
        created_event = AcademicEvent.objects.filter(title='General Faculty Assembly').first()
        self.assertIsNotNone(created_event)
        self.assertEqual(created_event.category, AcademicEvent.CATEGORY_MEETING)
        self.assertEqual(created_event.location, 'Audio-Visual Room 1')

        # Verify Audit Log
        audit = AuditEvent.objects.filter(
            action='CREATE_ACADEMIC_EVENT',
            object_type='AcademicEvent',
            object_id=str(created_event.id)
        ).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.actor, self.admin_user)

    def test_edit_event_success_and_audit_event_logged(self):
        """Admin can edit an existing event and updates are tracked in audit log."""
        self.client.force_login(self.admin_user)
        start_str = (self.now + timedelta(days=11)).strftime('%Y-%m-%dT%H:%M')
        end_str = (self.now + timedelta(days=16)).strftime('%Y-%m-%dT%H:%M')

        response = self.client.post(reverse('admin_calendar_event_save'), {
            'event_id': self.event1.id,
            'title': 'Midterm Examinations (Rescheduled)',
            'description': 'Updated schedule following typhoon suspension.',
            'category': AcademicEvent.CATEGORY_EXAMINATION,
            'status': AcademicEvent.STATUS_SCHEDULED,
            'visibility': AcademicEvent.VISIBILITY_ALL,
            'start_datetime': start_str,
            'end_datetime': end_str,
            'is_all_day': 'true',
            'location': 'Designated Exam Halls',
            'academic_year': self.ay_active.id,
            'semester': AcademicEvent.SEMESTER_FIRST,
        })
        self.assertEqual(response.status_code, 200)

        self.event1.refresh_from_db()
        self.assertEqual(self.event1.title, 'Midterm Examinations (Rescheduled)')
        self.assertEqual(self.event1.location, 'Designated Exam Halls')
        self.assertTrue(self.event1.is_all_day)

        # Audit verification
        audit = AuditEvent.objects.filter(
            action='UPDATE_ACADEMIC_EVENT',
            object_type='AcademicEvent',
            object_id=str(self.event1.id)
        ).first()
        self.assertIsNotNone(audit)

    def test_create_event_validation_errors(self):
        """Validation rejects empty title, invalid categories, or end before start."""
        self.client.force_login(self.admin_user)

        # Missing title
        r1 = self.client.post(reverse('admin_calendar_event_save'), {
            'title': '',
            'start_datetime': '2026-10-25T08:00',
            'end_datetime': '2026-10-25T10:00',
            'category': AcademicEvent.CATEGORY_COLLEGE_ACTIVITY,
        })
        self.assertEqual(r1.status_code, 400)
        self.assertIn('title is required', r1.json()['error'].lower())

        # End date before start date
        r2 = self.client.post(reverse('admin_calendar_event_save'), {
            'title': 'Backwards Event',
            'start_datetime': '2026-10-25T10:00',
            'end_datetime': '2026-10-25T08:00',
            'category': AcademicEvent.CATEGORY_COLLEGE_ACTIVITY,
        })
        self.assertEqual(r2.status_code, 400)
        self.assertIn('cannot be before start', r2.json()['error'].lower())

        # Invalid category
        r3 = self.client.post(reverse('admin_calendar_event_save'), {
            'title': 'Bad Category',
            'start_datetime': '2026-10-25T08:00',
            'end_datetime': '2026-10-25T10:00',
            'category': 'NON_EXISTENT_CATEGORY',
        })
        self.assertEqual(r3.status_code, 400)

    # --------------------------------------------------------------------------
    # 4. RESCHEDULE (DRAG & DROP / RESIZE)
    # --------------------------------------------------------------------------
    def test_drag_drop_reschedule_endpoint(self):
        """Reschedule endpoint updates dates and emits audit trail."""
        self.client.force_login(self.admin_user)
        new_start = (self.now + timedelta(days=25)).isoformat()
        new_end = (self.now + timedelta(days=25, hours=3)).isoformat()

        response = self.client.post(reverse('admin_calendar_event_reschedule', kwargs={'pk': self.event1.id}), {
            'start': new_start,
            'end': new_end,
            'all_day': 'false',
        })
        self.assertEqual(response.status_code, 200)

        self.event1.refresh_from_db()
        self.assertFalse(self.event1.is_all_day)

        # Audit
        audit = AuditEvent.objects.filter(
            action='RESCHEDULE_ACADEMIC_EVENT',
            object_type='AcademicEvent',
            object_id=str(self.event1.id)
        ).first()
        self.assertIsNotNone(audit)

    # --------------------------------------------------------------------------
    # 5. CANCEL & DELETE
    # --------------------------------------------------------------------------
    def test_cancel_and_restore_event(self):
        """Admin can cancel an event and restore it; history is preserved."""
        self.client.force_login(self.admin_user)

        # 1. Cancel
        r_cancel = self.client.post(reverse('admin_calendar_event_cancel', kwargs={'pk': self.event1.id}))
        self.assertEqual(r_cancel.status_code, 200)
        self.event1.refresh_from_db()
        self.assertEqual(self.event1.status, AcademicEvent.STATUS_CANCELED)

        # 2. Restore
        r_restore = self.client.post(reverse('admin_calendar_event_cancel', kwargs={'pk': self.event1.id}))
        self.assertEqual(r_restore.status_code, 200)
        self.event1.refresh_from_db()
        self.assertEqual(self.event1.status, AcademicEvent.STATUS_SCHEDULED)

    def test_delete_event(self):
        """Admin can delete an event and an audit log entry records the deletion."""
        self.client.force_login(self.admin_user)
        event_id = self.event2.id

        response = self.client.post(reverse('admin_calendar_event_delete', kwargs={'pk': event_id}))
        self.assertEqual(response.status_code, 200)

        # Verify gone from DB
        self.assertFalse(AcademicEvent.objects.filter(pk=event_id).exists())

        # Verify Audit Log
        audit = AuditEvent.objects.filter(
            action='DELETE_ACADEMIC_EVENT',
            object_type='AcademicEvent',
            object_id=str(event_id)
        ).first()
        self.assertIsNotNone(audit)

    # --------------------------------------------------------------------------
    # 6. DASHBOARD & ATTENDANCE INTEGRATION TESTS
    # --------------------------------------------------------------------------
    def test_admin_dashboard_mini_calendar_context(self):
        """Admin dashboard stats helper supplies mini-calendar JSON and upcoming events."""
        stats = _admin_dashboard_stats()
        self.assertIn('upcoming_calendar_events', stats)
        self.assertIn('mini_calendar_events_json', stats)
        self.assertIn('today_events', stats)
        if stats['mini_calendar_events_json']:
            evt = stats['mini_calendar_events_json'][0]
            self.assertIn('title', evt)
            self.assertIn('start_date', evt)
            self.assertIn('category_color', evt)

    def test_teacher_dashboard_calendar_visibility(self):
        """Teacher dashboard receives Faculty- and All-visible events, but NOT Admin-only."""
        AcademicEvent.objects.create(
            title='Admin Only Budget Meeting',
            category=AcademicEvent.CATEGORY_MEETING,
            status=AcademicEvent.STATUS_SCHEDULED,
            visibility=AcademicEvent.VISIBILITY_ADMIN,
            start_datetime=self.now,
            end_datetime=self.now + timedelta(hours=2)
        )
        AcademicEvent.objects.create(
            title='Faculty Academic Assembly',
            category=AcademicEvent.CATEGORY_MEETING,
            status=AcademicEvent.STATUS_SCHEDULED,
            visibility=AcademicEvent.VISIBILITY_FACULTY,
            start_datetime=self.now + timedelta(days=1),
            end_datetime=self.now + timedelta(days=1, hours=2)
        )

        stats = _teacher_dashboard_stats(self.teacher_profile)
        upcoming = stats['upcoming_calendar_events']
        upcoming_titles = [e.title for e in upcoming]
        self.assertIn('Faculty Academic Assembly', upcoming_titles)
        self.assertNotIn('Admin Only Budget Meeting', upcoming_titles)

    def test_student_dashboard_calendar_visibility(self):
        """Student dashboard receives only ALL-visible events and upcoming exams."""
        AcademicEvent.objects.create(
            title='Confidential Faculty Evaluation',
            category=AcademicEvent.CATEGORY_MEETING,
            status=AcademicEvent.STATUS_SCHEDULED,
            visibility=AcademicEvent.VISIBILITY_FACULTY,
            start_datetime=self.now + timedelta(days=2),
            end_datetime=self.now + timedelta(days=2, hours=2)
        )
        exam_evt = AcademicEvent.objects.create(
            title='Final Semester Exams',
            category=AcademicEvent.CATEGORY_EXAMINATION,
            status=AcademicEvent.STATUS_SCHEDULED,
            visibility=AcademicEvent.VISIBILITY_ALL,
            start_datetime=self.now + timedelta(days=15),
            end_datetime=self.now + timedelta(days=18)
        )

        stats = _student_dashboard_stats(self.student_profile)
        upcoming = stats['upcoming_calendar_events']
        upcoming_titles = [e.title for e in upcoming]
        self.assertIn('Final Semester Exams', upcoming_titles)
        self.assertNotIn('Confidential Faculty Evaluation', upcoming_titles)
        self.assertTrue(any(e.id == exam_evt.id for e in stats['upcoming_exams']))

    def test_attendance_session_on_holiday_advisory(self):
        """
        Opening a class session on an official holiday yields a warning notice
        without preventing the session from opening or corrupting attendance records.
        """
        dept = Department.objects.create(code='CITE', name='College of Info Tech')
        prog = Program.objects.create(department=dept, code='BSIT', name='BS Info Tech')
        subj = Subject.objects.create(code='IT301', name='Web Systems')
        class_obj = Class.objects.create(
            class_code='BSIT-3A',
            subject=subj,
            teacher_profile=self.teacher_profile,
            academic_year=self.ay_active,
            is_active=True
        )
        slot = ClassSlot.objects.create(
            class_obj=class_obj,
            weekday=timezone.localdate().weekday(),
            starts_at='08:00:00',
            ends_at='09:30:00',
            room='Lab 1'
        )

        AcademicEvent.objects.create(
            title='National Day Holiday',
            category=AcademicEvent.CATEGORY_HOLIDAY,
            status=AcademicEvent.STATUS_SCHEDULED,
            visibility=AcademicEvent.VISIBILITY_ALL,
            start_datetime=timezone.now() - timedelta(hours=1),
            end_datetime=timezone.now() + timedelta(hours=5),
            is_all_day=True
        )

        self.client.force_login(self.teacher_user)
        response = self.client.post(reverse('teacher_session_open'), {
            'class_id': class_obj.id,
            'slot_id': slot.id,
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        session = ClassSession.objects.filter(slot=slot, session_date=timezone.localdate()).first()
        self.assertIsNotNone(session)
        self.assertEqual(session.status, ClassSession.STATUS_OPEN)

        messages_list = list(response.context['messages'])
        self.assertTrue(any('Calendar Advisory' in str(m) for m in messages_list))

    def test_conflict_slot_calculation(self):
        """get_conflicting_slots_count counts active slots on affected weekdays."""
        dept = Department.objects.create(code='CITE2', name='College of Info Tech 2')
        prog = Program.objects.create(department=dept, code='BSIT2', name='BS Info Tech 2')
        subj = Subject.objects.create(code='IT302', name='Database Admin')
        class_obj = Class.objects.create(
            class_code='BSIT-3B',
            subject=subj,
            teacher_profile=self.teacher_profile,
            academic_year=self.ay_active,
            is_active=True
        )
        today_wd = timezone.localdate().weekday()
        ClassSlot.objects.create(
            class_obj=class_obj,
            weekday=today_wd,
            starts_at='10:00:00',
            ends_at='11:30:00',
            room='Lab 2'
        )
        event = AcademicEvent.objects.create(
            title='Campus Suspension Event',
            category=AcademicEvent.CATEGORY_HOLIDAY,
            status=AcademicEvent.STATUS_SCHEDULED,
            visibility=AcademicEvent.VISIBILITY_ALL,
            start_datetime=timezone.now(),
            end_datetime=timezone.now() + timedelta(hours=2),
            is_all_day=False
        )
        conflicts = event.get_conflicting_slots_count()
        self.assertGreaterEqual(conflicts, 1)

    def test_sync_philippine_holidays_idempotent(self):
        """Calling sync-holidays endpoint multiple times does not create duplicate events."""
        self.client.force_login(self.admin_user)
        r1 = self.client.post(reverse('admin_calendar_sync_holidays'))
        self.assertEqual(r1.status_code, 200)
        count1 = AcademicEvent.objects.filter(category=AcademicEvent.CATEGORY_HOLIDAY).count()
        self.assertGreaterEqual(count1, 18)

        r2 = self.client.post(reverse('admin_calendar_sync_holidays'))
        self.assertEqual(r2.status_code, 200)
        data2 = r2.json()
        self.assertEqual(data2['created_count'], 0)
        self.assertGreaterEqual(data2['existing_count'], 18)

        count2 = AcademicEvent.objects.filter(category=AcademicEvent.CATEGORY_HOLIDAY).count()
        self.assertEqual(count1, count2)

