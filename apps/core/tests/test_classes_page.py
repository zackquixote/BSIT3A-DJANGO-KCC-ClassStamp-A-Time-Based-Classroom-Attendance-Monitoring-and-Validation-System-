"""
# // ==============================================================================
# // KCC CLASSSTAMP - CLASS SECTION MANAGEMENT TESTS
# // ==============================================================================
# // Two fixes on /classes/:
# //   - a class with recorded meetings can no longer change subject or term
# //   - batch enlistment now refuses timetable clashes, like single enlistment does
# ==============================================================================
"""

from datetime import date, time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import (
    AcademicYear,
    Class,
    ClassSession,
    ClassSlot,
    Department,
    Enrollment,
    Profile,
    Program,
    Subject,
)
from apps.core.services.class_service import ClassAssignmentError, assign_class

User = get_user_model()


class ClassBase(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username='cls_admin')
        Profile.objects.create(user=self.admin_user, role=Profile.ROLE_ADMIN)
        self.department = Department.objects.create(code='CCS', name='College of Computer Studies')
        self.program = Program.objects.create(
            department=self.department, code='BSIT', name='BS Information Technology',
        )
        self.subject = Subject.objects.create(code='IT311', name='Web Development', units=3)
        self.other_subject = Subject.objects.create(code='IT312', name='Mobile Development', units=3)
        self.year = AcademicYear.objects.create(
            name='2026-2027', starts_on=date(2026, 6, 1), ends_on=date(2027, 3, 31),
            is_active=True,
        )
        self.next_year = AcademicYear.objects.create(
            name='2027-2028', starts_on=date(2027, 6, 1), ends_on=date(2028, 3, 31),
            is_active=False,
        )
        self.teacher_user = User.objects.create_user(username='cls_teacher')
        self.teacher = Profile.objects.create(
            user=self.teacher_user, role=Profile.ROLE_TEACHER, department=self.department,
        )
        self.class_obj = Class.objects.create(
            academic_year=self.year, class_code='BSIT-1A-IT311', subject=self.subject,
            teacher_profile=self.teacher, program=self.program, year_level=1,
        )
        self.client.force_login(self.admin_user)

    def _slot(self, class_obj=None, weekday=None, start=time(8, 0), end=time(9, 0)):
        return ClassSlot.objects.create(
            class_obj=class_obj or self.class_obj,
            weekday=weekday if weekday is not None else timezone.localdate().weekday(),
            starts_at=start, ends_at=end, room='Room 1',
        )

    def _session(self, slot, status=ClassSession.STATUS_CLOSED):
        return ClassSession.objects.create(
            slot=slot, session_date=timezone.localdate(), status=status,
            opened_by=self.teacher_user, created_by=self.teacher_user,
        )

    def _save(self, **overrides):
        payload = {
            'class_id': self.class_obj.pk,
            'class_code': self.class_obj.class_code,
            'subject_id': self.subject.pk,
            'teacher_profile_id': self.teacher.pk,
            'academic_year_id': self.year.pk,
            'capacity': '40',
            'grace_minutes': '10',
        }
        payload.update(overrides)
        return self.client.post(reverse('class_save'), payload)


class ClassHistoryLockTests(ClassBase):
    def test_subject_change_is_refused_once_meetings_exist(self):
        self._session(self._slot())

        response = self._save(subject_id=self.other_subject.pk)

        self.assertEqual(response.status_code, 302)
        self.class_obj.refresh_from_db()
        self.assertEqual(self.class_obj.subject_id, self.subject.pk)

    def test_academic_year_change_is_refused_once_meetings_exist(self):
        self._session(self._slot())

        response = self._save(academic_year_id=self.next_year.pk)

        self.assertEqual(response.status_code, 302)
        self.class_obj.refresh_from_db()
        self.assertEqual(self.class_obj.academic_year_id, self.year.pk)

    def test_teacher_change_is_still_allowed(self):
        self._session(self._slot())
        replacement_user = User.objects.create_user(username='cls_teacher_b')
        replacement = Profile.objects.create(
            user=replacement_user, role=Profile.ROLE_TEACHER, department=self.department,
        )

        self._save(teacher_profile_id=replacement.pk)

        self.class_obj.refresh_from_db()
        self.assertEqual(self.class_obj.teacher_profile_id, replacement.pk)

    def test_subject_change_is_allowed_without_meetings(self):
        self._slot()  # slot exists, but no session was ever opened

        self._save(subject_id=self.other_subject.pk)

        self.class_obj.refresh_from_db()
        self.assertEqual(self.class_obj.subject_id, self.other_subject.pk)

    def test_service_raises_for_direct_callers(self):
        self._session(self._slot())

        with self.assertRaises(ClassAssignmentError) as ctx:
            assign_class(
                actor=self.admin_user,
                teacher_profile=self.teacher,
                academic_year=self.year,
                subject=self.other_subject,
                class_code=self.class_obj.class_code,
                class_obj=self.class_obj,
            )

        self.assertIn('recorded meetings', str(ctx.exception))


class BatchEnlistmentClashTests(ClassBase):
    def setUp(self):
        super().setUp()
        # Second section in the same term, same weekday, overlapping hour.
        self.second_class = Class.objects.create(
            academic_year=self.year, class_code='BSIT-1A-IT312', subject=self.other_subject,
            teacher_profile=self.teacher, program=self.program, year_level=1,
        )
        self._slot()                                  # 08:00-09:00 on class 1
        self._slot(class_obj=self.second_class)       # 08:00-09:00 on class 2

    def _student(self, number):
        user = User.objects.create_user(username=f'user_{number}')
        return Profile.objects.create(
            user=user,
            role=Profile.ROLE_STUDENT,
            student_number=number,
            program=self.program,
            year_level=1,
            approval_status=Profile.APPROVAL_APPROVED,
        )

    def _enroll(self, student, class_obj):
        return Enrollment.objects.create(
            student_profile=student, class_obj=class_obj,
            status=Enrollment.STATUS_ACTIVE,
        )

    def test_batch_skips_students_with_overlapping_sections(self):
        student = self._student('2026-6001')
        self._enroll(student, self.class_obj)

        response = self.client.post(
            reverse('class_roster_enroll_batch', args=[self.second_class.pk]), {}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['enrolled_count'], 0)
        self.assertIn('overlap this timetable', response.json()['message'])
        self.assertFalse(
            Enrollment.objects.filter(
                student_profile=student, class_obj=self.second_class,
            ).exists()
        )

    def test_batch_enrolls_students_without_a_clash(self):
        student = self._student('2026-6002')

        response = self.client.post(
            reverse('class_roster_enroll_batch', args=[self.second_class.pk]), {}
        )

        self.assertEqual(response.json()['enrolled_count'], 1)
        self.assertTrue(
            Enrollment.objects.filter(
                student_profile=student, class_obj=self.second_class,
                status=Enrollment.STATUS_ACTIVE,
            ).exists()
        )

    def test_single_enlistment_still_refuses_the_clash(self):
        student = self._student('2026-6003')
        self._enroll(student, self.class_obj)

        response = self.client.post(
            reverse('class_roster_enroll', args=[self.second_class.pk]),
            {'profile_id': student.pk},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('overlaps', response.json()['message'])
