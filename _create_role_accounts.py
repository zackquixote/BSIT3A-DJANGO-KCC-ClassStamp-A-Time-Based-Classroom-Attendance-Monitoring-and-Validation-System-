"""Create role-based verification accounts (ADMIN / TEACHER / STUDENT).

Runs against whichever database the environment selects:
    SQLite:  $env:USE_SQLITE='True'; python _create_role_accounts.py
    MySQL:   python _create_role_accounts.py

All accounts share the password Verify#2026x.
"""
import os
import secrets
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from apps.core.models import Department, Program, CurriculumVersion, Profile  # noqa: E402

PASSWORD = 'Verify#2026x'


def upsert_user(username, *, first_name, last_name, is_superuser=False):
    User = get_user_model()
    user, _ = User.objects.get_or_create(
        username=username,
        defaults={
            'first_name': first_name,
            'last_name': last_name,
            'email': f'{username}@classstamp.local',
        },
    )
    user.set_password(PASSWORD)
    user.is_active = True
    user.is_superuser = is_superuser
    user.is_staff = is_superuser
    user.save()
    return user


def upsert_profile(user, **fields):
    profile = getattr(user, 'classstamp_profile', None)
    if profile is None:
        profile = Profile(user=user)
    for key, value in fields.items():
        setattr(profile, key, value)
    profile.totp_enabled = False
    profile.save()
    return profile


def main():
    cmat = Department.objects.filter(code='CMAT', is_active=True).first() \
        or Department.objects.filter(is_active=True).first()
    bsit = Program.objects.get(code='BSIT')
    bsa = Program.objects.get(code='BSA')
    bsit_cv = (CurriculumVersion.objects
               .filter(program=bsit, status='APPROVED')
               .order_by('-version_number')
               .first())
    bsa_cv = (CurriculumVersion.objects
              .filter(program=bsa, status='APPROVED')
              .order_by('-version_number')
              .first())

    # ADMIN — superuser with ADMIN profile (full console access)
    admin = upsert_user('verify_admin', first_name='Vera', last_name='Admin',
                        is_superuser=True)
    upsert_profile(admin, role=Profile.ROLE_ADMIN, department=None)

    # TEACHER — faculty account bound to CMAT
    teacher = upsert_user('verify_teacher', first_name='Theo', last_name='Teacher')
    upsert_profile(teacher, role=Profile.ROLE_TEACHER, department=cmat)

    # STUDENTS
    def student(username, first, last, number, *, program=bsit, cv=bsit_cv,
                approval=Profile.APPROVAL_APPROVED, qr=None):
        u = upsert_user(username, first_name=first, last_name=last)
        return upsert_profile(
            u, role=Profile.ROLE_STUDENT, program=program, year_level=3,
            student_number=number, approval=approval, curriculum_version=cv,
            entry_year=2024, gender='M', qr_secret=qr,
        )

    student('verify_student', 'Sofia', 'Student', '2026-VER01',
            qr=secrets.token_hex(32))          # approved, main student
    student('verify_student2', 'Sam', 'Second', '2026-VER02',
            qr=secrets.token_hex(32))          # approved, secondary
    student('verify_student3', 'Tara', 'Third', '2026-VER03',
            qr=secrets.token_hex(32))          # approved, no enrollments
    student('verify_low', 'Liam', 'Low', '2026-LOW1',
            qr=secrets.token_hex(32))          # approved, at-risk history
    student('verify_nocv', 'Noa', 'Curriculum', '2026-NOCV', cv=None,
            qr=secrets.token_hex(32))          # approved, no curriculum
    student('verify_bsa', 'Bea', 'Accounting', '2026-BSA1',
            program=bsa, cv=bsa_cv, qr=secrets.token_hex(32))  # approved, other program
    student('verify_pending', 'Pia', 'Pending', '2026-PEND',
            approval=Profile.APPROVAL_PENDING, qr=secrets.token_hex(32))  # pending

    print('ROLE ACCOUNTS OK on', 'SQLite' if os.environ.get('USE_SQLITE') else 'MySQL')


if __name__ == '__main__':
    main()
