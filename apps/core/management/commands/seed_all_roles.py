import secrets
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.core.models import (
    Department, Program, Subject, AcademicYear, Profile, Class
)

User = get_user_model()


class Command(BaseCommand):
    help = "Seeds official KCC academic entities and 3 working role accounts (Admin, Teacher, Student)"

    def handle(self, *args, **options):
        self.stdout.write("--- Seeding KCC Departments & Programs ---")
        # 1. Departments and Programs
        dept_cmat, _ = Department.objects.get_or_create(
            code="CMAT",
            defaults={"name": "College of Management, Accountancy, and Technology", "is_active": True}
        )
        dept_ceas, _ = Department.objects.get_or_create(
            code="CEAS",
            defaults={"name": "College of Education, Arts, and Sciences", "is_active": True}
        )
        dept_coc, _ = Department.objects.get_or_create(
            code="COC",
            defaults={"name": "College of Criminology", "is_active": True}
        )

        prog_bsit, _ = Program.objects.get_or_create(
            code="BSIT",
            defaults={
                "department": dept_cmat,
                "name": "Bachelor of Science in Information Technology",
                "years_total": 4,
                "is_active": True
            }
        )
        prog_bsba, _ = Program.objects.get_or_create(
            code="BSBA",
            defaults={
                "department": dept_cmat,
                "name": "Bachelor of Science in Business Administration",
                "years_total": 4,
                "is_active": True
            }
        )
        prog_bsed, _ = Program.objects.get_or_create(
            code="BSED-ENG",
            defaults={
                "department": dept_ceas,
                "name": "Bachelor of Secondary Education major in English",
                "years_total": 4,
                "is_active": True
            }
        )

        # 2. Academic Year — reuse the existing active term; only create one when none is active
        # (the DB enforces a single active academic year: uq_cs_academic_year_one_active)
        ay = AcademicYear.objects.filter(is_active=True).first()
        if ay is None:
            ay = AcademicYear.objects.create(
                name="2025-2026 1st Sem",
                starts_on="2025-08-01",
                ends_on="2025-12-20",
                is_active=True,
            )

        # 3. Subject
        subject, _ = Subject.objects.get_or_create(
            code="IT311",
            defaults={
                "name": "Web Development & Systems Architecture",
                "description": "Full-stack web application development and attendance monitoring systems.",
                "is_active": True
            }
        )

        # 4. ADMIN USER & PROFILE
        self.stdout.write("--- Ensuring Admin Account ---")
        admin_user, _ = User.objects.get_or_create(
            username="admin",
            defaults={
                "email": "admin@kcc.edu.ph",
                "first_name": "KCC",
                "last_name": "Administrator",
                "is_staff": True,
                "is_superuser": True
            }
        )
        admin_user.set_password("admin12345")
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.save()

        admin_prof, _ = Profile.objects.get_or_create(
            user=admin_user,
            defaults={"role": Profile.ROLE_ADMIN}
        )
        # chk_cs_profile_shape: ADMIN rows must keep all persona fields NULL
        admin_prof.role = Profile.ROLE_ADMIN
        admin_prof.department = None
        admin_prof.program = None
        admin_prof.year_level = None
        admin_prof.student_number = None
        admin_prof.approval_status = None
        admin_prof.qr_secret = None
        admin_prof.save()

        # Also support glenn superuser if exists
        glenn = User.objects.filter(username="glenn").first()
        if glenn:
            g_prof, _ = Profile.objects.get_or_create(user=glenn, defaults={"role": Profile.ROLE_ADMIN})
            g_prof.role = Profile.ROLE_ADMIN
            g_prof.save()

        # 5. TEACHER USER & PROFILE
        self.stdout.write("--- Ensuring Teacher Account ---")
        teacher_user, _ = User.objects.get_or_create(
            username="teacher",
            defaults={
                "email": "teacher@kcc.edu.ph",
                "first_name": "Maria",
                "last_name": "Santos",
                "is_staff": False,
                "is_superuser": False
            }
        )
        teacher_user.first_name = "Maria"
        teacher_user.last_name = "Santos"
        teacher_user.email = "teacher@kcc.edu.ph"
        teacher_user.set_password("teacher12345")
        teacher_user.save()

        teacher_prof, _ = Profile.objects.get_or_create(
            user=teacher_user,
            defaults={
                "role": Profile.ROLE_TEACHER,
                "department": dept_cmat,
            }
        )
        # chk_cs_profile_shape: TEACHER rows must keep student/approval fields NULL
        teacher_prof.role = Profile.ROLE_TEACHER
        teacher_prof.department = dept_cmat
        teacher_prof.program = None
        teacher_prof.year_level = None
        teacher_prof.student_number = None
        teacher_prof.approval_status = None
        teacher_prof.approved_by = None
        teacher_prof.approved_at = None
        teacher_prof.qr_secret = None
        teacher_prof.save()

        # Assign a sample class to Teacher
        sample_class, _ = Class.objects.get_or_create(
            academic_year=ay,
            class_code="BSIT-3A-IT311",
            defaults={
                "subject": subject,
                "teacher_profile": teacher_prof,
                "capacity": 45,
                "grace_minutes": 10,
                "is_active": True
            }
        )

        # 6. STUDENT USER & PROFILE
        self.stdout.write("--- Ensuring Student Account ---")
        student_user, _ = User.objects.get_or_create(
            username="student",
            defaults={
                "email": "student@kcc.edu.ph",
                "first_name": "Juan",
                "last_name": "Dela Cruz",
                "is_staff": False,
                "is_superuser": False
            }
        )
        student_user.first_name = "Juan"
        student_user.last_name = "Dela Cruz"
        student_user.email = "student@kcc.edu.ph"
        student_user.set_password("student12345")
        student_user.save()

        student_prof, _ = Profile.objects.get_or_create(
            user=student_user,
            defaults={
                "role": Profile.ROLE_STUDENT,
                "program": prog_bsit,
                "year_level": 3,
                "student_number": "2024-0001",
                "approval_status": Profile.APPROVAL_APPROVED,
                "approved_by": admin_user,
                "approved_at": timezone.now(),
                "qr_secret": secrets.token_hex(32)
            }
        )
        student_prof.program = prog_bsit
        student_prof.year_level = 3
        student_prof.student_number = "2024-0001"
        student_prof.department = None
        student_prof.approval_status = Profile.APPROVAL_APPROVED
        student_prof.approved_by = admin_user
        student_prof.approved_at = timezone.now()
        if not student_prof.qr_secret or len(student_prof.qr_secret) != 64:
            student_prof.qr_secret = secrets.token_hex(32)
        student_prof.save()

        self.stdout.write(self.style.SUCCESS("""
=============================================================
KCC CLASSSTAMP - THREE ROLES CONFIGURED & READY FOR LOGIN:
=============================================================
1. ADMIN ACCOUNT:
   Username: admin (or admin@kcc.edu.ph)
   Password: admin12345
   Destination: /admin/dashboard/ (Admin Dashboard)

2. TEACHER ACCOUNT:
   Username: teacher (or teacher@kcc.edu.ph)
   Password: teacher12345
   Destination: /teacher/dashboard/ (Teacher Dashboard)

3. STUDENT ACCOUNT:
   Username: student (or student@kcc.edu.ph or 2024-0001)
   Password: student12345
   Destination: /student/dashboard/ (Student Dashboard)
=============================================================
"""))
