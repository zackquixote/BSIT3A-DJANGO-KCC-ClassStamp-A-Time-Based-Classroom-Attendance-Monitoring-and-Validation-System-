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
        # Req 1: join-code enrollment validates the student's curriculum
        # version, so fixtures must place the subject inside that version.
        self.curriculum_version = CurriculumVersion.objects.create(
            program=self.program,
            version_number=1,
            status=CurriculumVersion.STATUS_APPROVED,
        )
        Curriculum.objects.create(
            program=self.program,
            version=self.curriculum_version,
            year_level=3,
            semester=1,
            subject=self.subject,
        )
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
            curriculum_version=self.curriculum_version,
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

    def test_admin_generates_hashed_code_and_student_enrolls_directly(self):
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
        # The current join flow deliberately auto-activates enrollment; there
        # is no teacher approval step for join-code requests anymore.
        self.assertEqual(enrollment.status, Enrollment.STATUS_ACTIVE)

        self.client.force_login(self.admin_user)
        roster = self.client.get(reverse('class_roster_get', args=[self.class_obj.pk])).json()
        self.assertEqual(roster['enrolled_count'], 1)
        self.assertEqual(roster['pending_count'], 0)
        self.assertEqual(roster['enrolled'][0]['student_id'], self.student.student_number)
        # The now-enrolled student no longer appears in the available list.
        self.assertNotIn(self.student.pk, [entry['profile_id'] for entry in roster['available']])

    def test_assigned_teacher_code_enrolls_student_directly(self):
        self.client.force_login(self.teacher_user)
        generated = self.client.post(
            reverse('class_join_code_manage', args=[self.class_obj.pk]),
            {'action': 'rotate'},
        )
        self.assertEqual(generated.status_code, 200)
        join_code = generated.json()['join_code']
        self.class_obj.refresh_from_db()
        self.assertEqual(self.class_obj.join_code_digest, hash_join_code(join_code))

        self.client.force_login(self.student_user)
        self.client.post(reverse('student_join_class'), {'join_code': join_code})
        enrollment = Enrollment.objects.get(class_obj=self.class_obj, student_profile=self.student)
        # Join codes auto-activate: no pending request and no manual approval.
        self.assertEqual(enrollment.status, Enrollment.STATUS_ACTIVE)

        # The self-service join is audited with the student as the actor.
        self.assertTrue(
            AuditEvent.objects.filter(
                action='CLASS_JOIN_ENROLL',
                object_type='Enrollment',
                object_id=str(enrollment.pk),
            ).exists()
        )

    def test_teacher_cannot_manage_another_teachers_class(self):
        other_user = User.objects.create_user(username='other_join_teacher')
        other_teacher = Profile.objects.create(
            user=other_user,
            role=Profile.ROLE_TEACHER,
            department=self.department,
        )
        other_class = Class.objects.create(
            academic_year=self.term,
            class_code='BSIT-3B-IT311',
            section_code='BSIT-3B',
            subject=self.subject,
            teacher_profile=other_teacher,
            program=self.program,
            year_level=3,
        )

        self.client.force_login(self.teacher_user)
        response = self.client.post(
            reverse('class_join_code_manage', args=[other_class.pk]),
            {'action': 'rotate'},
        )

        self.assertEqual(response.status_code, 404)
        other_class.refresh_from_db()
        self.assertFalse(other_class.join_code_active)

    def test_teacher_can_decline_only_pending_requests_for_owned_class(self):
        enrollment = Enrollment.objects.create(
            class_obj=self.class_obj,
            student_profile=self.student,
            status=Enrollment.STATUS_PENDING,
        )
        self.client.force_login(self.teacher_user)
        response = self.client.post(
            reverse('class_roster_remove', args=[enrollment.pk]),
        )

        self.assertEqual(response.status_code, 200)
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.status, Enrollment.STATUS_WITHDRAWN)

    def test_teacher_class_page_shows_join_code_and_pending_requests(self):
        self.class_obj.join_code_active = True
        self.class_obj.join_code_digest = hash_join_code('ABCD-EFGH-JK23')
        self.class_obj.save(update_fields=['join_code_active', 'join_code_digest', 'updated_at'])
        Enrollment.objects.create(
            class_obj=self.class_obj,
            student_profile=self.student,
            status=Enrollment.STATUS_PENDING,
        )

        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse('teacher_classes'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Rotate Join Code')
        self.assertContains(response, '1 pending join request')
        self.assertContains(response, self.student.student_number)
        self.assertContains(response, reverse('class_roster_enroll', args=[self.class_obj.pk]))

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

    def test_active_enrollment_consumes_capacity(self):
        # Capacity is consumed by the auto-activated enrollment itself, so the
        # second student is refused when the class is full.
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
            curriculum_version=self.curriculum_version,
            approval_status=Profile.APPROVAL_APPROVED,
        )
        self.client.force_login(other_user)
        self.client.post(reverse('student_join_class'), {'join_code': join_code})

        self.assertEqual(
            Enrollment.objects.filter(
                class_obj=self.class_obj,
                status=Enrollment.STATUS_ACTIVE,
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
