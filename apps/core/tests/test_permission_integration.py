"""
# // ==============================================================================
# // KCC CLASSSTAMP - PERMISSION SERVICE VIEW INTEGRATION TESTS (Task 1.1)
# // ==============================================================================
# // Proves that PermissionService is actually wired into views and that
# // changing object IDs does not bypass object-level authorization.
# // Also locks in the superuser bypass that the old view helpers provided.
# // ==============================================================================
"""

from datetime import date, time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.models import (
    AcademicYear,
    AttendanceRecord,
    Class,
    ClassSession,
    ClassSlot,
    Department,
    Enrollment,
    ExcuseSlip,
    Profile,
    Program,
    Subject,
)
from apps.core.services.permission_service import PermissionService

User = get_user_model()


class PermissionServiceSuperuserTests(TestCase):
    """Superusers must keep the bypass the old view helpers provided."""

    def setUp(self):
        self.department = Department.objects.create(code='CCS', name='Computer Studies')
        self.program = Program.objects.create(
            department=self.department, code='BSIT', name='Information Technology',
        )
        self.subject = Subject.objects.create(code='IT311', name='Web Development')
        self.year = AcademicYear.objects.create(
            name='2026-2027',
            starts_on=date(2026, 6, 1),
            ends_on=date(2027, 3, 31),
            is_active=True,
        )
        self.teacher_user = User.objects.create_user(username='perm_teacher')
        self.teacher = Profile.objects.create(
            user=self.teacher_user, role=Profile.ROLE_TEACHER, department=self.department,
        )
        self.class_obj = Class.objects.create(
            academic_year=self.year,
            class_code='BSIT-3A-IT311',
            section_code='BSIT-3A',
            subject=self.subject,
            teacher_profile=self.teacher,
            program=self.program,
            year_level=3,
        )
        self.slot = ClassSlot.objects.create(
            class_obj=self.class_obj, weekday=0,
            starts_at=time(8, 0), ends_at=time(10, 0), room='IT-Lab 1',
        )
        self.session = ClassSession.objects.create(
            slot=self.slot, session_date=date(2026, 11, 9), status=ClassSession.STATUS_OPEN,
        )
        self.student_user = User.objects.create_user(username='perm_student')
        self.student = Profile.objects.create(
            user=self.student_user, role=Profile.ROLE_STUDENT,
            student_number='2026-2001', program=self.program, year_level=3,
            approval_status=Profile.APPROVAL_APPROVED,
        )
        self.enrollment = Enrollment.objects.create(
            class_obj=self.class_obj, student_profile=self.student,
            status=Enrollment.STATUS_ACTIVE,
        )
        self.record = AttendanceRecord.objects.create(
            session=self.session, student_profile=self.student,
            status=AttendanceRecord.STATUS_ABSENT,
        )
        self.slip = ExcuseSlip.objects.create(
            student_profile=self.student, session=self.session,
            reason='Medical', status=ExcuseSlip.STATUS_PENDING,
        )
        # Superuser with no ClassStamp profile at all.
        self.bare_superuser = User.objects.create_superuser(
            username='perm_bare_su', password='Super-Secret-2026!'
        )

    def test_superuser_without_profile_passes_all_four_methods(self):
        self.assertTrue(PermissionService.can_user_access_class(self.bare_superuser, self.class_obj))
        self.assertTrue(PermissionService.can_user_modify_session(self.bare_superuser, self.session))
        self.assertTrue(PermissionService.can_user_approve_excuse(self.bare_superuser, self.slip))
        self.assertTrue(PermissionService.can_user_manage_enrollment(self.bare_superuser, self.class_obj))

    def test_teacher_still_cannot_touch_another_teachers_objects(self):
        other_user = User.objects.create_user(username='perm_other_teacher')
        other_profile = Profile.objects.create(
            user=other_user, role=Profile.ROLE_TEACHER, department=self.department,
        )
        self.assertFalse(PermissionService.can_user_access_class(other_user, self.class_obj))
        self.assertFalse(PermissionService.can_user_modify_session(other_user, self.session))
        self.assertFalse(PermissionService.can_user_approve_excuse(other_user, self.slip))
        self.assertFalse(PermissionService.can_user_manage_enrollment(other_user, self.class_obj))


class PermissionViewIntegrationTests(TestCase):
    """Changing IDs in the URL must not bypass object-level checks."""

    def setUp(self):
        self.department = Department.objects.create(code='CCS', name='Computer Studies')
        self.program = Program.objects.create(
            department=self.department, code='BSIT', name='Information Technology',
        )
        self.subject = Subject.objects.create(code='IT311', name='Web Development')
        self.year = AcademicYear.objects.create(
            name='2026-2027',
            starts_on=date(2026, 6, 1),
            ends_on=date(2027, 3, 31),
            is_active=True,
        )
        self.teacher_user = User.objects.create_user(username='view_teacher')
        self.teacher = Profile.objects.create(
            user=self.teacher_user, role=Profile.ROLE_TEACHER, department=self.department,
        )
        self.other_teacher_user = User.objects.create_user(username='view_other_teacher')
        self.other_teacher = Profile.objects.create(
            user=self.other_teacher_user, role=Profile.ROLE_TEACHER, department=self.department,
        )
        self.class_obj = Class.objects.create(
            academic_year=self.year,
            class_code='BSIT-3A-IT311',
            section_code='BSIT-3A',
            subject=self.subject,
            teacher_profile=self.teacher,
            program=self.program,
            year_level=3,
        )
        self.other_class = Class.objects.create(
            academic_year=self.year,
            class_code='BSIT-3B-IT311',
            section_code='BSIT-3B',
            subject=self.subject,
            teacher_profile=self.other_teacher,
            program=self.program,
            year_level=3,
        )
        self.slot = ClassSlot.objects.create(
            class_obj=self.class_obj, weekday=0,
            starts_at=time(8, 0), ends_at=time(10, 0), room='IT-Lab 1',
        )
        self.session = ClassSession.objects.create(
            slot=self.slot, session_date=date(2026, 11, 9), status=ClassSession.STATUS_OPEN,
        )
        self.student_user = User.objects.create_user(username='view_student')
        self.student = Profile.objects.create(
            user=self.student_user, role=Profile.ROLE_STUDENT,
            student_number='2026-2002', program=self.program, year_level=3,
            approval_status=Profile.APPROVAL_APPROVED,
        )
        self.enrollment = Enrollment.objects.create(
            class_obj=self.class_obj, student_profile=self.student,
            status=Enrollment.STATUS_ACTIVE,
        )
        self.record = AttendanceRecord.objects.create(
            session=self.session, student_profile=self.student,
            status=AttendanceRecord.STATUS_ABSENT,
        )
        self.slip = ExcuseSlip.objects.create(
            student_profile=self.student, session=self.session,
            reason='Medical', status=ExcuseSlip.STATUS_PENDING,
        )

    def test_other_teacher_cannot_read_live_roster_by_changing_session_id(self):
        self.client.force_login(self.other_teacher_user)
        response = self.client.get(reverse('teacher_session_roster_json', args=[self.session.pk]))
        self.assertEqual(response.status_code, 403)

    def test_assigned_teacher_can_read_own_live_roster(self):
        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse('teacher_session_roster_json', args=[self.session.pk]))
        self.assertNotEqual(response.status_code, 403)

    def test_other_teacher_cannot_review_excuse_by_changing_slip_id(self):
        self.client.force_login(self.other_teacher_user)
        response = self.client.post(
            reverse('excuse_slip_review_ajax', args=[self.slip.pk]),
            {'action': 'approve', 'note': 'ok'},
        )
        self.assertEqual(response.status_code, 403)
        self.slip.refresh_from_db()
        self.assertEqual(self.slip.status, ExcuseSlip.STATUS_PENDING)

    def test_assigned_teacher_can_review_own_excuse(self):
        self.client.force_login(self.teacher_user)
        response = self.client.post(
            reverse('excuse_slip_review_ajax', args=[self.slip.pk]),
            {'action': 'approve', 'note': 'ok'},
        )
        self.assertEqual(response.status_code, 200)
        self.slip.refresh_from_db()
        self.assertEqual(self.slip.status, ExcuseSlip.STATUS_APPROVED)

    def test_other_teacher_cannot_enroll_into_another_class_by_changing_class_id(self):
        self.client.force_login(self.other_teacher_user)
        response = self.client.post(
            reverse('class_roster_enroll', args=[self.class_obj.pk]),
            {'profile_id': self.student.pk},
        )
        self.assertEqual(response.status_code, 404)
        # No new enrollment was created for the other class's teacher.
        self.assertEqual(
            Enrollment.objects.filter(class_obj=self.class_obj).count(),
            1,
        )

    def test_student_cannot_reach_teacher_roster_json(self):
        self.client.force_login(self.student_user)
        response = self.client.get(reverse('teacher_session_roster_json', args=[self.session.pk]))
        self.assertEqual(response.status_code, 403)

    def test_superuser_without_profile_still_reaches_own_tools(self):
        su = User.objects.create_superuser(username='view_bare_su', password='Super-Secret-2026!')
        self.client.force_login(su)
        response = self.client.get(reverse('teacher_session_roster_json', args=[self.session.pk]))
        self.assertNotEqual(response.status_code, 403)
