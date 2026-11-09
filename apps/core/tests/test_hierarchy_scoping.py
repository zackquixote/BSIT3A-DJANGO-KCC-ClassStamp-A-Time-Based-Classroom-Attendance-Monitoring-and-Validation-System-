import json
from datetime import date, time
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import (
    AcademicYear,
    AttendanceRecord,
    AuditEvent,
    Class,
    ClassSession,
    ClassSlot,
    Curriculum,
    Department,
    Enrollment,
    Profile,
    Program,
    Subject,
)
from apps.core.services import (
    ClassAssignmentError,
    assign_class,
    promote_students,
    validate_teacher_subject_assignment,
)

User = get_user_model()


class AcademicHierarchyScopingTests(TestCase):
    def setUp(self):
        # Admin
        self.admin_user = User.objects.create_user(username='hier_admin', password='Admin!Pass123')
        self.admin_profile = Profile.objects.create(
            user=self.admin_user, role=Profile.ROLE_ADMIN, approval_status=Profile.APPROVAL_APPROVED
        )

        # Departments
        self.dept_cmat = Department.objects.create(code='CMAT', name='College of Management & Tech')
        self.dept_coc = Department.objects.create(code='COC', name='College of Criminology')

        # Programs
        self.prog_bsit = Program.objects.create(
            department=self.dept_cmat, code='BSIT', name='BS Information Technology', years_total=4
        )
        self.prog_bsba = Program.objects.create(
            department=self.dept_cmat, code='BSBA', name='BS Business Administration', years_total=4
        )
        self.prog_bscrim = Program.objects.create(
            department=self.dept_coc, code='BSCRIM', name='BS Criminology', years_total=4
        )

        # Academic Year
        self.ay = AcademicYear.objects.create(
            name='2026-2027', starts_on=date(2026, 6, 1), ends_on=date(2027, 3, 31), is_active=True
        )

        # Subjects
        self.subj_it = Subject.objects.create(code='IT101', name='Intro to Computing', units=3)
        self.subj_crim = Subject.objects.create(code='CRIM101', name='Intro to Criminology', units=3)
        self.subj_ge = Subject.objects.create(code='GEE1', name='Understanding the Self', units=3)

        # Curriculums
        Curriculum.objects.create(
            program=self.prog_bsit, subject=self.subj_it, year_level=1, semester=1, is_major=True
        )
        Curriculum.objects.create(
            program=self.prog_bscrim, subject=self.subj_crim, year_level=1, semester=1, is_major=True
        )
        Curriculum.objects.create(
            program=self.prog_bsit, subject=self.subj_ge, year_level=1, semester=1, is_major=False
        )

        # Teachers
        self.teacher_it_user = User.objects.create_user(username='prof_it', password='Teacher!Pass123')
        self.teacher_it = Profile.objects.create(
            user=self.teacher_it_user,
            role=Profile.ROLE_TEACHER,
            department=self.dept_cmat,
            approval_status=Profile.APPROVAL_APPROVED,
        )

        self.teacher_crim_user = User.objects.create_user(username='prof_crim', password='Teacher!Pass123')
        self.teacher_crim = Profile.objects.create(
            user=self.teacher_crim_user,
            role=Profile.ROLE_TEACHER,
            department=self.dept_coc,
            approval_status=Profile.APPROVAL_APPROVED,
        )

        # Students
        self.student_it_user = User.objects.create_user(username='stud_it', password='Student!Pass123')
        self.student_it = Profile.objects.create(
            user=self.student_it_user,
            role=Profile.ROLE_STUDENT,
            student_number='2026-0001',
            program=self.prog_bsit,
            year_level=1,
            approval_status=Profile.APPROVAL_APPROVED,
        )

        self.student_bsba_user = User.objects.create_user(username='stud_bsba', password='Student!Pass123')
        self.student_bsba = Profile.objects.create(
            user=self.student_bsba_user,
            role=Profile.ROLE_STUDENT,
            student_number='2026-0002',
            program=self.prog_bsba,
            year_level=1,
            approval_status=Profile.APPROVAL_APPROVED,
        )

        self.student_crim_user = User.objects.create_user(username='stud_crim', password='Student!Pass123')
        self.student_crim = Profile.objects.create(
            user=self.student_crim_user,
            role=Profile.ROLE_STUDENT,
            student_number='2026-0003',
            program=self.prog_bscrim,
            year_level=1,
            approval_status=Profile.APPROVAL_APPROVED,
        )

        # Classes
        self.class_it = Class.objects.create(
            academic_year=self.ay,
            subject=self.subj_it,
            teacher_profile=self.teacher_it,
            program=self.prog_bsit,
            year_level=1,
            class_code='BSIT-1A-IT101',
            section_code='BSIT-1A',
        )

        self.class_ge = Class.objects.create(
            academic_year=self.ay,
            subject=self.subj_ge,
            teacher_profile=self.teacher_it,
            program=self.prog_bsit,
            year_level=1,
            class_code='BSIT-1A-GEE1',
            section_code='BSIT-1A',
        )

        self.client.force_login(self.admin_user)

    # --------------------------------------------------------------------------
    # Issue 1: Teacher Load Allocation & Cross-Department Guards
    # --------------------------------------------------------------------------
    def test_teacher_subject_assignment_cross_department_blocked(self):
        # A COC teacher cannot be assigned to teach IT101 (under CMAT)
        with self.assertRaises(ClassAssignmentError) as ctx:
            assign_class(
                actor=self.admin_user,
                teacher_profile=self.teacher_crim,
                academic_year=self.ay,
                subject=self.subj_it,
                class_code='BSIT-1B-IT101',
            )
        self.assertIn('belongs to', str(ctx.exception))

    def test_teacher_subject_assignment_ge_is_allowed_cross_department(self):
        # A COC teacher CAN teach a General Education course like GEE1
        result = assign_class(
            actor=self.admin_user,
            teacher_profile=self.teacher_crim,
            academic_year=self.ay,
            subject=self.subj_ge,
            class_code='SEC-1A-GEE1',
        )
        self.assertTrue(result['created'])
        self.assertEqual(result['class'].teacher_profile, self.teacher_crim)

    def test_teacher_assign_class_ajax_enforces_department_guard(self):
        # Post via AJAX to teacher_assign_class_ajax
        url = reverse('teacher_assign_class_ajax', args=[self.teacher_crim.pk])
        response = self.client.post(url, {
            'academic_year_id': self.ay.pk,
            'subject_id': self.subj_it.pk,
            'class_code': 'BSIT-1C-IT101',
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('belongs to', response.json().get('error', ''))

    # --------------------------------------------------------------------------
    # Issue 3: Class Roster Enlistment Cross-Program Major Subject Guard
    # --------------------------------------------------------------------------
    def test_class_roster_enroll_blocks_cross_program_for_major_subject(self):
        url = reverse('class_roster_enroll', args=[self.class_it.pk])
        # Try to enroll BSBA student into IT major course
        response = self.client.post(url, {'profile_id': self.student_bsba.pk})
        self.assertEqual(response.status_code, 400)
        self.assertIn('Major subject designated for', response.json().get('message', ''))
        self.assertFalse(
            Enrollment.objects.filter(class_obj=self.class_it, student_profile=self.student_bsba).exists()
        )

    def test_class_roster_enroll_permits_cross_program_with_override_flag(self):
        url = reverse('class_roster_enroll', args=[self.class_it.pk])
        # Force/allow cross-program
        response = self.client.post(url, {
            'profile_id': self.student_bsba.pk,
            'allow_cross_program': '1',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Enrollment.objects.filter(
                class_obj=self.class_it, student_profile=self.student_bsba, status=Enrollment.STATUS_ACTIVE
            ).exists()
        )

    def test_class_roster_enroll_allows_cross_program_for_ge_subject(self):
        url = reverse('class_roster_enroll', args=[self.class_ge.pk])
        # BSBA student enrolling in GE course
        response = self.client.post(url, {'profile_id': self.student_bsba.pk})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Enrollment.objects.filter(
                class_obj=self.class_ge, student_profile=self.student_bsba, status=Enrollment.STATUS_ACTIVE
            ).exists()
        )

    # --------------------------------------------------------------------------
    # Issue 4: Student Directory Section Scoping
    # --------------------------------------------------------------------------
    def test_student_directory_sections_carry_scoping_metadata(self):
        url = reverse('student_directory')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        sections = list(response.context['sections'])
        self.assertTrue(len(sections) > 0)
        first = sections[0]
        self.assertIn('section_code', first)
        self.assertIn('program_id', first)
        self.assertIn('program__department_id', first)

    # --------------------------------------------------------------------------
    # Issue 5: Attendance Period Report Filters (Preview & CSV Export)
    # --------------------------------------------------------------------------
    def test_attendance_period_report_preview_and_export_scoped_by_dept_and_prog(self):
        # Create a slot, session, and record
        slot = ClassSlot.objects.create(
            class_obj=self.class_it, weekday=0, starts_at=time(8, 0), ends_at=time(9, 0), room='Lab 1'
        )
        session = ClassSession.objects.create(
            slot=slot, session_date=timezone.localdate(), status=ClassSession.STATUS_CLOSED,
            opened_by=self.teacher_it_user, created_by=self.teacher_it_user
        )
        Enrollment.objects.create(
            class_obj=self.class_it, student_profile=self.student_it, status=Enrollment.STATUS_ACTIVE
        )
        AttendanceRecord.objects.create(
            session=session,
            student_profile=self.student_it,
            status=AttendanceRecord.STATUS_PRESENT,
            method='QR',
        )

        # 1. Preview matching CMAT -> 1 record
        page_url = reverse('attendance_period_report')
        res_page = self.client.get(page_url, {
            'academic_year': self.ay.pk,
            'department': self.dept_cmat.pk,
        })
        self.assertEqual(res_page.status_code, 200)
        self.assertEqual(res_page.context['record_count'], 1)

        # 2. Preview matching COC -> 0 records
        res_page_other = self.client.get(page_url, {
            'academic_year': self.ay.pk,
            'department': self.dept_coc.pk,
        })
        self.assertEqual(res_page_other.status_code, 200)
        self.assertEqual(res_page_other.context['record_count'], 0)

        # 3. CSV export with department filter
        export_url = reverse('attendance_period_report_export')
        res_export = self.client.get(export_url, {
            'academic_year': self.ay.pk,
            'department': self.dept_cmat.pk,
        })
        self.assertEqual(res_export.status_code, 200)
        content = res_export.content.decode('utf-8')
        self.assertIn('Department,Program,Year Level', content)
        self.assertIn('2026-0001', content)
        self.assertIn('CMAT', content)
        self.assertIn('BSIT', content)

    # --------------------------------------------------------------------------
    # Issue 6: Scoped Student Promotion
    # --------------------------------------------------------------------------
    def test_promote_students_scoped_by_program(self):
        # Promote ONLY BSIT students
        res = promote_students(self.admin_user, program_id=self.prog_bsit.pk)
        self.assertEqual(res['promoted_count'], 1)
        self.student_it.refresh_from_db()
        self.student_bsba.refresh_from_db()
        self.student_crim.refresh_from_db()

        self.assertEqual(self.student_it.year_level, 2)
        self.assertEqual(self.student_bsba.year_level, 1)  # Untouched
        self.assertEqual(self.student_crim.year_level, 1)  # Untouched

    def test_promote_students_scoped_by_department(self):
        # Promote CMAT students (BSIT and BSBA)
        res = promote_students(self.admin_user, department_id=self.dept_cmat.pk)
        self.assertEqual(res['promoted_count'], 2)
        self.student_it.refresh_from_db()
        self.student_bsba.refresh_from_db()
        self.student_crim.refresh_from_db()

        self.assertEqual(self.student_it.year_level, 2)
        self.assertEqual(self.student_bsba.year_level, 2)
        self.assertEqual(self.student_crim.year_level, 1)  # Untouched (COC)

    def test_student_promote_all_ajax_accepts_scope(self):
        url = reverse('student_promote_all')
        res = self.client.post(url, {'program_id': self.prog_bscrim.pk})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['promoted_count'], 1)
        self.student_crim.refresh_from_db()
        self.assertEqual(self.student_crim.year_level, 2)

