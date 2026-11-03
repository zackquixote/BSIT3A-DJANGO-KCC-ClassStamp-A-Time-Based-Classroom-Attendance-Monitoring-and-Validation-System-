from datetime import date

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from apps.core.models import (
    AcademicYear,
    Class,
    Department,
    Enrollment,
    Profile,
    Program,
    Subject,
)
from apps.core.services.class_join_service import hash_join_code


User = get_user_model()


class ClassJoinCodeTests(TestCase):
    def setUp(self):
        cache.clear()
        self.department = Department.objects.create(code='CCS', name='Computer Studies')
        self.program = Program.objects.create(
            department=self.department,
            code='BSIT',
            name='Information Technology',
        )
        self.subject = Subject.objects.create(code='IT311', name='Web Development')
        self.term = AcademicYear.objects.create(
            name='2026-2027',
            starts_on=date(2026, 6, 1),
            ends_on=date(2027, 3, 31),
            is_active=True,
        )
        self.teacher_user = User.objects.create_user(username='join_teacher')
        self.teacher = Profile.objects.create(
            user=self.teacher_user,
            role=Profile.ROLE_TEACHER,
            department=self.department,
        )
        self.admin_user = User.objects.create_user(username='join_admin')
        Profile.objects.create(user=self.admin_user, role=Profile.ROLE_ADMIN)
        self.student_user = User.objects.create_user(username='join_student')
        self.student = Profile.objects.create(
            user=self.student_user,
            role=Profile.ROLE_STUDENT,
            student_number='2026-1001',
            program=self.program,
            year_level=3,
            approval_status=Profile.APPROVAL_APPROVED,
        )
        self.class_obj = Class.objects.create(
            academic_year=self.term,
            class_code='BSIT-3A-IT311',
            section_code='BSIT-3A',
            subject=self.subject,
            teacher_profile=self.teacher,
            program=self.program,
            year_level=3,
            capacity=2,
        )

    def _manage_code(self, action):
        self.client.force_login(self.admin_user)
        return self.client.post(
            reverse('class_join_code_manage', args=[self.class_obj.pk]),
            {'action': action},
        )

    def _issue_code(self):
        response = self._manage_code('rotate')
        self.assertEqual(response.status_code, 200)
        return response.json()['join_code']

    def test_admin_generates_hashed_code_and_student_requests_enrollment(self):
        join_code = self._issue_code()
        self.class_obj.refresh_from_db()

        self.assertEqual(len(join_code.replace('-', '')), 12)
        self.assertNotIn(join_code, self.class_obj.join_code_digest)
        self.assertEqual(self.class_obj.join_code_digest, hash_join_code(join_code))
        self.assertTrue(self.class_obj.join_code_active)

        self.client.force_login(self.student_user)
        response = self.client.post(
            reverse('student_join_class'),
            {'join_code': join_code.lower()},
        )

        self.assertRedirects(response, reverse('student_join_class'))
        enrollment = Enrollment.objects.get(class_obj=self.class_obj, student_profile=self.student)
        self.assertEqual(enrollment.status, Enrollment.STATUS_PENDING)

        self.client.force_login(self.admin_user)
        roster = self.client.get(reverse('class_roster_get', args=[self.class_obj.pk])).json()
        self.assertEqual(roster['pending_count'], 1)
        self.assertEqual(roster['pending'][0]['profile_id'], self.student.pk)
        self.assertEqual(roster['available'], [])

        approved = self.client.post(
            reverse('class_roster_enroll', args=[self.class_obj.pk]),
            {'profile_id': self.student.pk},
        )
        self.assertEqual(approved.status_code, 200)
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.status, Enrollment.STATUS_ACTIVE)

    def test_rotating_code_invalidates_previous_code(self):
        first_code = self._issue_code()
        second_code = self._issue_code()
        self.assertNotEqual(first_code, second_code)

        self.client.force_login(self.student_user)
        response = self.client.post(
            reverse('student_join_class'),
            {'join_code': first_code},
        )

        self.assertRedirects(response, reverse('student_join_class'))
        self.assertFalse(
            Enrollment.objects.filter(class_obj=self.class_obj, student_profile=self.student).exists()
        )

    def test_revoked_code_cannot_be_used(self):
        self._issue_code()
        revoked = self._manage_code('revoke')
        self.assertTrue(revoked.json()['success'])
        self.class_obj.refresh_from_db()
        self.assertFalse(self.class_obj.join_code_active)
        self.assertEqual(self.class_obj.join_code_digest, '')

    def test_wrong_program_gets_generic_failure_and_no_enrollment(self):
        join_code = self._issue_code()
        other_department = Department.objects.create(code='CBM', name='Business')
        other_program = Program.objects.create(
            department=other_department,
            code='BSBA',
            name='Business Administration',
        )
        self.student.program = other_program
        self.student.save(update_fields=['program'])

        self.client.force_login(self.student_user)
        response = self.client.post(
            reverse('student_join_class'),
            {'join_code': join_code},
        )

        self.assertRedirects(response, reverse('student_join_class'))
        self.assertFalse(
            Enrollment.objects.filter(class_obj=self.class_obj, student_profile=self.student).exists()
        )

    def test_pending_requests_reserve_capacity(self):
        self.class_obj.capacity = 1
        self.class_obj.save(update_fields=['capacity', 'updated_at'])
        join_code = self._issue_code()
        self.client.force_login(self.student_user)
        self.client.post(reverse('student_join_class'), {'join_code': join_code})

        other_user = User.objects.create_user(username='join_student_2')
        other_student = Profile.objects.create(
            user=other_user,
            role=Profile.ROLE_STUDENT,
            student_number='2026-1002',
            program=self.program,
            year_level=3,
            approval_status=Profile.APPROVAL_APPROVED,
        )
        self.client.force_login(other_user)
        self.client.post(reverse('student_join_class'), {'join_code': join_code})

        self.assertEqual(
            Enrollment.objects.filter(
                class_obj=self.class_obj,
                status=Enrollment.STATUS_PENDING,
            ).count(),
            1,
        )
        self.assertFalse(
            Enrollment.objects.filter(class_obj=self.class_obj, student_profile=other_student).exists()
        )

    def test_invalid_action_and_inactive_class_are_rejected(self):
        self.client.force_login(self.admin_user)
        invalid_action = self.client.post(
            reverse('class_join_code_manage', args=[self.class_obj.pk]),
            {'action': 'enable'},
        )
        self.assertEqual(invalid_action.status_code, 400)

        self.class_obj.is_active = False
        self.class_obj.save(update_fields=['is_active', 'updated_at'])
        inactive_class = self.client.post(
            reverse('class_join_code_manage', args=[self.class_obj.pk]),
            {'action': 'rotate'},
        )
        self.assertEqual(inactive_class.status_code, 400)
