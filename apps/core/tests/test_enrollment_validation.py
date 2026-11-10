"""
# // ==============================================================================
# // KCC CLASSSTAMP - ENROLLMENT CURRICULUM & CAPACITY TESTS (tasks 2.1 / 2.2)
# // ==============================================================================
"""

from datetime import date

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from apps.core.models import (
    AcademicYear,
    AuditEvent,
    Class,
    Curriculum,
    CurriculumVersion,
    Department,
    Enrollment,
    Profile,
    Program,
    Subject,
)
from apps.core.services.enrollment_service import (
    check_class_capacity,
    validate_student_curriculum,
)

User = get_user_model()


class CurriculumValidationFixtures(TestCase):
    """Shared fixtures for curriculum + capacity enrollment tests."""

    @classmethod
    def setUpTestData(cls):
        cls.department = Department.objects.create(code='CCS', name='Computer Studies')
        cls.program = Program.objects.create(
            department=cls.department, code='BSIT', name='Information Technology',
        )
        cls.other_program = Program.objects.create(
            department=cls.department, code='BSCS', name='Computer Science',
        )
        cls.subject = Subject.objects.create(code='IT311', name='Web Development')
        cls.foreign_subject = Subject.objects.create(code='CS999', name='Not In Curriculum')
        cls.year = AcademicYear.objects.create(
            name='2026-2027',
            starts_on=date(2026, 6, 1),
            ends_on=date(2027, 3, 31),
            is_active=True,
        )
        cls.version = CurriculumVersion.objects.create(
            program=cls.program,
            version_number=1,
            status=CurriculumVersion.STATUS_APPROVED,
        )
        Curriculum.objects.create(
            program=cls.program,
            version=cls.version,
            subject=cls.subject,
            year_level=3,
            semester=1,
        )
        cls.teacher_user = User.objects.create_user(username='curr_teacher')
        cls.teacher = Profile.objects.create(
            user=cls.teacher_user, role=Profile.ROLE_TEACHER, department=cls.department,
        )
        cls.admin_user = User.objects.create_user(username='curr_admin')
        cls.admin = Profile.objects.create(user=cls.admin_user, role=Profile.ROLE_ADMIN)

        cls.class_obj = Class.objects.create(
            academic_year=cls.year,
            class_code='BSIT-3A-IT311',
            section_code='BSIT-3A',
            subject=cls.subject,
            teacher_profile=cls.teacher,
            program=cls.program,
            year_level=3,
            capacity=2,
        )

    def _student(self, number, with_version=True, program=None):
        user = User.objects.create_user(username=f'curr_{number}')
        profile = Profile.objects.create(
            user=user,
            role=Profile.ROLE_STUDENT,
            student_number=number,
            program=program or self.program,
            year_level=3,
            approval_status=Profile.APPROVAL_APPROVED,
            curriculum_version=self.version if with_version else None,
        )
        return user, profile

    def _join(self, user, join_code):
        self.client.force_login(user)
        return self.client.post(reverse('student_join_class'), {'join_code': join_code})


class ServiceCurriculumTests(CurriculumValidationFixtures):
    def test_missing_version_is_rejected(self):
        _, profile = self._student('2026-4001', with_version=False)
        ok, code, message = validate_student_curriculum(profile, self.class_obj)
        self.assertFalse(ok)
        self.assertEqual(code, 'CURRICULUM_VERSION_MISSING')
        self.assertIn('contact administration', message.lower())

    def test_subject_outside_version_is_rejected(self):
        _, profile = self._student('2026-4002')
        foreign_class = Class.objects.create(
            academic_year=self.year,
            class_code='BSIT-3A-CS999',
            section_code='BSIT-3A',
            subject=self.foreign_subject,
            teacher_profile=self.teacher,
            program=self.program,
            year_level=3,
        )
        ok, code, message = validate_student_curriculum(profile, foreign_class)
        self.assertFalse(ok)
        self.assertEqual(code, 'CURRICULUM_SUBJECT_NOT_IN_VERSION')
        self.assertIn('CS999', message)

    def test_subject_inside_version_passes(self):
        _, profile = self._student('2026-4003')
        ok, code, message = validate_student_curriculum(profile, self.class_obj)
        self.assertTrue(ok)
        self.assertEqual(code, '')


class JoinCurriculumTests(CurriculumValidationFixtures):
    def setUp(self):
        cache.clear()
        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse('class_join_code_manage', args=[self.class_obj.pk]),
            {'action': 'rotate'},
        )
        self.assertEqual(response.status_code, 200)
        self.join_code = response.json()['join_code']
        self.client.logout()

    def test_join_without_curriculum_version_is_rejected_and_audited(self):
        user, profile = self._student('2026-4010', with_version=False)
        response = self._join(user, self.join_code)
        self.assertRedirects(response, reverse('student_join_class'))
        self.assertFalse(
            Enrollment.objects.filter(class_obj=self.class_obj, student_profile=profile).exists()
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                action='ENROLLMENT_REJECTED_CURRICULUM',
                object_id=f'{profile.pk}:{self.class_obj.pk}',
            ).exists()
        )

    def test_join_with_matching_curriculum_enrolls(self):
        user, profile = self._student('2026-4011', with_version=True)
        response = self._join(user, self.join_code)
        self.assertRedirects(response, reverse('student_join_class'))
        enrollment = Enrollment.objects.get(
            class_obj=self.class_obj, student_profile=profile,
        )
        self.assertEqual(enrollment.status, Enrollment.STATUS_ACTIVE)


class JoinCapacityTests(CurriculumValidationFixtures):
    def setUp(self):
        self.class_obj.capacity = 1
        self.class_obj.save(update_fields=['capacity', 'updated_at'])
        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse('class_join_code_manage', args=[self.class_obj.pk]),
            {'action': 'rotate'},
        )
        self.join_code = response.json()['join_code']
        self.client.logout()

    def test_second_joiner_is_rejected_when_full_and_audited(self):
        user_a, profile_a = self._student('2026-4020')
        user_b, profile_b = self._student('2026-4021')
        self._join(user_a, self.join_code)
        self._join(user_b, self.join_code)
        self.assertEqual(
            Enrollment.objects.filter(class_obj=self.class_obj).count(),
            1,
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                action='ENROLLMENT_REJECTED_CAPACITY',
                object_id=f'{profile_b.pk}:{self.class_obj.pk}',
            ).exists()
        )

    def test_unlimited_when_capacity_unset(self):
        self.class_obj.capacity = None
        self.class_obj.save(update_fields=['capacity', 'updated_at'])
        ok, message = check_class_capacity(self.class_obj)
        self.assertTrue(ok)
        self.assertEqual(message, '')


class RosterCurriculumTests(CurriculumValidationFixtures):
    def test_admin_enroll_rejects_subject_outside_curriculum(self):
        user, profile = self._student('2026-4030')
        foreign_class = Class.objects.create(
            academic_year=self.year,
            class_code='BSIT-3A-CS999',
            section_code='BSIT-3A',
            subject=self.foreign_subject,
            teacher_profile=self.teacher,
            program=self.program,
            year_level=3,
        )
        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse('class_roster_enroll', args=[foreign_class.pk]),
            {'profile_id': profile.pk},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('curriculum', response.json()['message'].lower())
        self.assertFalse(
            Enrollment.objects.filter(class_obj=foreign_class, student_profile=profile).exists()
        )

    def test_admin_curriculum_override_with_force_is_audited(self):
        user, profile = self._student('2026-4031')
        foreign_class = Class.objects.create(
            academic_year=self.year,
            class_code='BSIT-3A-CS999',
            section_code='BSIT-3A',
            subject=self.foreign_subject,
            teacher_profile=self.teacher,
            program=self.program,
            year_level=3,
        )
        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse('class_roster_enroll', args=[foreign_class.pk]),
            {'profile_id': profile.pk, 'force': '1'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Enrollment.objects.filter(class_obj=foreign_class, student_profile=profile).exists()
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                action='ENROLLMENT_REJECTED_CURRICULUM_OVERRIDE',
            ).exists()
        )

    def test_admin_capacity_override_requires_explicit_flag(self):
        user, profile = self._student('2026-4032')
        other_user, other_profile = self._student('2026-4033')
        Enrollment.objects.create(
            class_obj=self.class_obj, student_profile=other_profile,
            status=Enrollment.STATUS_ACTIVE,
        )
        self.assertEqual(self.class_obj.capacity, 2)
        # Fill the second seat.
        third_user, third_profile = self._student('2026-4034')
        Enrollment.objects.create(
            class_obj=self.class_obj, student_profile=third_profile,
            status=Enrollment.STATUS_ACTIVE,
        )
        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse('class_roster_enroll', args=[self.class_obj.pk]),
            {'profile_id': profile.pk},
        )
        self.assertEqual(response.status_code, 400)
        self.assertTrue(
            AuditEvent.objects.filter(
                action='ENROLLMENT_REJECTED_CAPACITY',
                object_id=f'{profile.pk}:{self.class_obj.pk}',
            ).exists()
        )

        response = self.client.post(
            reverse('class_roster_enroll', args=[self.class_obj.pk]),
            {'profile_id': profile.pk, 'override_capacity': '1'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Enrollment.objects.filter(
                class_obj=self.class_obj, student_profile=profile,
                status=Enrollment.STATUS_ACTIVE,
            ).exists()
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                action='ENROLLMENT_REJECTED_CAPACITY_OVERRIDE',
            ).exists()
        )

    def test_lowering_capacity_does_not_evict(self):
        user, profile = self._student('2026-4035')
        Enrollment.objects.create(
            class_obj=self.class_obj, student_profile=profile,
            status=Enrollment.STATUS_ACTIVE,
        )
        self.class_obj.capacity = 0  # falsy = unlimited; also never evicts
        self.class_obj.save(update_fields=['capacity', 'updated_at'])
        ok, _ = check_class_capacity(self.class_obj)
        self.assertTrue(ok)
        self.assertTrue(
            Enrollment.objects.filter(
                class_obj=self.class_obj, student_profile=profile,
                status=Enrollment.STATUS_ACTIVE,
            ).exists()
        )
