"""
# // ==============================================================================
# // KCC CLASSSTAMP - PERMISSION SERVICE TESTS
# // ==============================================================================
# // Test Suite: PermissionService Authorization Logic
# // Description: Unit tests for centralized permission checking service.
# //   Validates all authorization rules for class access, session modification,
# //   excuse slip approval, and enrollment management.
# // ==============================================================================
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

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


class PermissionServiceTestCase(TestCase):
    """
    // Test suite for PermissionService authorization methods.
    """

    def setUp(self):
        """
        // Create test fixtures: users, profiles, academic data, classes, sessions.
        """
        # Create academic year
        self.academic_year = AcademicYear.objects.create(
            name='2023-2024',
            starts_on='2023-08-01',
            ends_on='2024-05-31',
            is_active=True
        )

        # Create program and subject
        self.department = Department.objects.create(
            code='CCS',
            name='College of Computer Studies',
            is_active=True
        )
        self.program = Program.objects.create(
            department=self.department,
            code='BSIT',
            name='Bachelor of Science in Information Technology',
            is_active=True
        )
        self.subject = Subject.objects.create(
            code='CS101',
            name='Introduction to Computing',
            units=3,
            is_active=True
        )

        # Create admin user and profile
        self.admin_user = User.objects.create_user(
            username='admin1',
            password='testpass123',
            email='admin@test.com'
        )
        self.admin_profile = Profile.objects.create(
            user=self.admin_user,
            role='ADMIN',
            approval_status='APPROVED'
        )
        self.admin_user.classstamp_profile = self.admin_profile

        # Create teacher user and profile
        self.teacher_user = User.objects.create_user(
            username='teacher1',
            password='testpass123',
            email='teacher@test.com'
        )
        self.teacher_profile = Profile.objects.create(
            user=self.teacher_user,
            role='TEACHER',
            approval_status='APPROVED'
        )
        self.teacher_user.classstamp_profile = self.teacher_profile

        # Create another teacher user and profile
        self.other_teacher_user = User.objects.create_user(
            username='teacher2',
            password='testpass123',
            email='teacher2@test.com'
        )
        self.other_teacher_profile = Profile.objects.create(
            user=self.other_teacher_user,
            role='TEACHER',
            approval_status='APPROVED'
        )
        self.other_teacher_user.classstamp_profile = self.other_teacher_profile

        # Create student user and profile
        self.student_user = User.objects.create_user(
            username='student1',
            password='testpass123',
            email='student@test.com'
        )
        self.student_profile = Profile.objects.create(
            user=self.student_user,
            role='STUDENT',
            student_number='2023-0001',
            approval_status='APPROVED'
        )
        self.student_user.classstamp_profile = self.student_profile

        # Create another student user and profile
        self.other_student_user = User.objects.create_user(
            username='student2',
            password='testpass123',
            email='student2@test.com'
        )
        self.other_student_profile = Profile.objects.create(
            user=self.other_student_user,
            role='STUDENT',
            student_number='2023-0002',
            approval_status='APPROVED'
        )
        self.other_student_user.classstamp_profile = self.other_student_profile

        # Create a class taught by teacher1
        self.class_obj = Class.objects.create(
            academic_year=self.academic_year,
            class_code='BSIT-3A-CS101',
            subject=self.subject,
            teacher_profile=self.teacher_profile,
            program=self.program,
            year_level=3,
            is_active=True
        )

        # Create a class slot
        self.class_slot = ClassSlot.objects.create(
            class_obj=self.class_obj,
            weekday=0,  # Monday
            starts_at='08:00:00',
            ends_at='10:00:00',
            room='IT-Lab 1',
            is_active=True
        )

        # Create a class session
        self.session = ClassSession.objects.create(
            slot=self.class_slot,
            session_date=timezone.now().date(),
            status=ClassSession.STATUS_OPEN
        )

        # Create active enrollment for student1
        self.enrollment = Enrollment.objects.create(
            student_profile=self.student_profile,
            class_obj=self.class_obj,
            status=Enrollment.STATUS_ACTIVE
        )

        # Create attendance record for excuse slip test
        self.attendance_record = AttendanceRecord.objects.create(
            session=self.session,
            student_profile=self.student_profile,
            status=AttendanceRecord.STATUS_ABSENT
        )

        # Create excuse slip
        self.excuse_slip = ExcuseSlip.objects.create(
            student_profile=self.student_profile,
            session=self.session,
            reason='Medical emergency',
            status=ExcuseSlip.STATUS_PENDING
        )

    # // ==============================================================================
    # // TEST: can_user_access_class
    # // ==============================================================================

    def test_admin_can_access_any_class(self):
        """
        // Verify that ADMIN role can access any class.
        """
        result = PermissionService.can_user_access_class(
            self.admin_user, self.class_obj
        )
        self.assertTrue(result)

    def test_teacher_can_access_own_class(self):
        """
        // Verify that TEACHER can access their own class.
        """
        result = PermissionService.can_user_access_class(
            self.teacher_user, self.class_obj
        )
        self.assertTrue(result)

    def test_teacher_cannot_access_other_class(self):
        """
        // Verify that TEACHER cannot access another teacher's class.
        """
        result = PermissionService.can_user_access_class(
            self.other_teacher_user, self.class_obj
        )
        self.assertFalse(result)

    def test_student_can_access_enrolled_class(self):
        """
        // Verify that STUDENT can access a class they are enrolled in.
        """
        result = PermissionService.can_user_access_class(
            self.student_user, self.class_obj
        )
        self.assertTrue(result)

    def test_student_cannot_access_unenrolled_class(self):
        """
        // Verify that STUDENT cannot access a class they are not enrolled in.
        """
        result = PermissionService.can_user_access_class(
            self.other_student_user, self.class_obj
        )
        self.assertFalse(result)

    def test_user_without_profile_cannot_access_class(self):
        """
        // Verify that user without profile cannot access any class.
        """
        user_no_profile = User.objects.create_user(
            username='noprofile',
            password='testpass123'
        )
        result = PermissionService.can_user_access_class(
            user_no_profile, self.class_obj
        )
        self.assertFalse(result)

    # // ==============================================================================
    # // TEST: can_user_modify_session
    # // ==============================================================================

    def test_admin_can_modify_any_session(self):
        """
        // Verify that ADMIN role can modify any session.
        """
        result = PermissionService.can_user_modify_session(
            self.admin_user, self.session
        )
        self.assertTrue(result)

    def test_teacher_can_modify_own_session(self):
        """
        // Verify that TEACHER can modify their own class session.
        """
        result = PermissionService.can_user_modify_session(
            self.teacher_user, self.session
        )
        self.assertTrue(result)

    def test_teacher_cannot_modify_other_session(self):
        """
        // Verify that TEACHER cannot modify another teacher's session.
        """
        result = PermissionService.can_user_modify_session(
            self.other_teacher_user, self.session
        )
        self.assertFalse(result)

    def test_student_cannot_modify_session(self):
        """
        // Verify that STUDENT cannot modify any session.
        """
        result = PermissionService.can_user_modify_session(
            self.student_user, self.session
        )
        self.assertFalse(result)

    def test_user_without_profile_cannot_modify_session(self):
        """
        // Verify that user without profile cannot modify any session.
        """
        user_no_profile = User.objects.create_user(
            username='noprofile2',
            password='testpass123'
        )
        result = PermissionService.can_user_modify_session(
            user_no_profile, self.session
        )
        self.assertFalse(result)

    # // ==============================================================================
    # // TEST: can_user_approve_excuse
    # // ==============================================================================

    def test_admin_can_approve_any_excuse(self):
        """
        // Verify that ADMIN role can approve any excuse slip.
        """
        result = PermissionService.can_user_approve_excuse(
            self.admin_user, self.excuse_slip
        )
        self.assertTrue(result)

    def test_teacher_can_approve_own_class_excuse(self):
        """
        // Verify that TEACHER can approve excuse slips for their own class.
        """
        result = PermissionService.can_user_approve_excuse(
            self.teacher_user, self.excuse_slip
        )
        self.assertTrue(result)

    def test_teacher_cannot_approve_other_class_excuse(self):
        """
        // Verify that TEACHER cannot approve excuse slips for another teacher's class.
        """
        result = PermissionService.can_user_approve_excuse(
            self.other_teacher_user, self.excuse_slip
        )
        self.assertFalse(result)

    def test_student_cannot_approve_excuse(self):
        """
        // Verify that STUDENT cannot approve any excuse slip.
        """
        result = PermissionService.can_user_approve_excuse(
            self.student_user, self.excuse_slip
        )
        self.assertFalse(result)

    def test_user_without_profile_cannot_approve_excuse(self):
        """
        // Verify that user without profile cannot approve any excuse slip.
        """
        user_no_profile = User.objects.create_user(
            username='noprofile3',
            password='testpass123'
        )
        result = PermissionService.can_user_approve_excuse(
            user_no_profile, self.excuse_slip
        )
        self.assertFalse(result)

    # // ==============================================================================
    # // TEST: can_user_manage_enrollment
    # // ==============================================================================

    def test_admin_can_manage_any_enrollment(self):
        """
        // Verify that ADMIN role can manage any enrollment.
        """
        result = PermissionService.can_user_manage_enrollment(
            self.admin_user, self.class_obj
        )
        self.assertTrue(result)

    def test_teacher_can_manage_own_class_enrollment(self):
        """
        // Verify that TEACHER can manage enrollment for their own class.
        """
        result = PermissionService.can_user_manage_enrollment(
            self.teacher_user, self.class_obj
        )
        self.assertTrue(result)

    def test_teacher_cannot_manage_other_class_enrollment(self):
        """
        // Verify that TEACHER cannot manage enrollment for another teacher's class.
        """
        result = PermissionService.can_user_manage_enrollment(
            self.other_teacher_user, self.class_obj
        )
        self.assertFalse(result)

    def test_student_cannot_manage_enrollment(self):
        """
        // Verify that STUDENT cannot manage any enrollment.
        """
        result = PermissionService.can_user_manage_enrollment(
            self.student_user, self.class_obj
        )
        self.assertFalse(result)

    def test_user_without_profile_cannot_manage_enrollment(self):
        """
        // Verify that user without profile cannot manage any enrollment.
        """
        user_no_profile = User.objects.create_user(
            username='noprofile4',
            password='testpass123'
        )
        result = PermissionService.can_user_manage_enrollment(
            user_no_profile, self.class_obj
        )
        self.assertFalse(result)

    # // ==============================================================================
    # // TEST: Helper Methods
    # // ==============================================================================

    def test_get_user_role_returns_correct_role(self):
        """
        // Verify that get_user_role returns the correct role for each user type.
        """
        self.assertEqual(PermissionService.get_user_role(self.admin_user), 'ADMIN')
        self.assertEqual(PermissionService.get_user_role(self.teacher_user), 'TEACHER')
        self.assertEqual(PermissionService.get_user_role(self.student_user), 'STUDENT')

    def test_get_user_role_returns_none_for_no_profile(self):
        """
        // Verify that get_user_role returns None for user without profile.
        """
        user_no_profile = User.objects.create_user(
            username='noprofile5',
            password='testpass123'
        )
        self.assertIsNone(PermissionService.get_user_role(user_no_profile))

    def test_is_admin_helper_method(self):
        """
        // Verify that is_admin correctly identifies admin users.
        """
        self.assertTrue(PermissionService.is_admin(self.admin_user))
        self.assertFalse(PermissionService.is_admin(self.teacher_user))
        self.assertFalse(PermissionService.is_admin(self.student_user))

    def test_is_teacher_helper_method(self):
        """
        // Verify that is_teacher correctly identifies teacher users.
        """
        self.assertFalse(PermissionService.is_teacher(self.admin_user))
        self.assertTrue(PermissionService.is_teacher(self.teacher_user))
        self.assertFalse(PermissionService.is_teacher(self.student_user))

    def test_is_student_helper_method(self):
        """
        // Verify that is_student correctly identifies student users.
        """
        self.assertFalse(PermissionService.is_student(self.admin_user))
        self.assertFalse(PermissionService.is_student(self.teacher_user))
        self.assertTrue(PermissionService.is_student(self.student_user))

    # // ==============================================================================
    # // TEST: Edge Cases
    # // ==============================================================================

    def test_withdrawn_enrollment_denies_access(self):
        """
        // Verify that student with WITHDRAWN enrollment cannot access class.
        """
        # Withdraw the enrollment
        self.enrollment.status = Enrollment.STATUS_WITHDRAWN
        self.enrollment.save()

        result = PermissionService.can_user_access_class(
            self.student_user, self.class_obj
        )
        self.assertFalse(result)

    def test_pending_enrollment_denies_access(self):
        """
        // Verify that student with PENDING enrollment cannot access class.
        """
        # Change enrollment to pending
        self.enrollment.status = Enrollment.STATUS_PENDING
        self.enrollment.save()

        result = PermissionService.can_user_access_class(
            self.student_user, self.class_obj
        )
        self.assertFalse(result)

    def test_completed_enrollment_denies_access(self):
        """
        // Verify that student with COMPLETED enrollment cannot access class.
        """
        # Change enrollment to completed
        self.enrollment.status = Enrollment.STATUS_COMPLETED
        self.enrollment.save()

        result = PermissionService.can_user_access_class(
            self.student_user, self.class_obj
        )
        self.assertFalse(result)
