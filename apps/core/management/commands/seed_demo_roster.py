"""
# // ==============================================================================
# // KCC CLASSSTAMP - DEMO ROSTER SEED MANAGEMENT COMMAND
# // ==============================================================================
# // Usage: python manage.py seed_demo_roster [--count 10]
# // Description: Seeds sample cohort students for BSIT-3A and other sections with
# //   profiles in APPROVED, PENDING, and REJECTED states. Perfect for testing
# //   attendance workflows, validation queues, and directory filtering.
# // ==============================================================================
"""

import secrets
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core.models import Class, Department, Enrollment, Profile, Program, Subject

User = get_user_model()


class Command(BaseCommand):
    help = 'Seeds sample student roster for demonstration and evaluation'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=8,
            help='Number of sample student profiles to seed (default: 8)'
        )

    def handle(self, *args, **options):
        count = options['count']

        # Ensure base CMAT / BSIT program exists
        dept, _ = Department.objects.get_or_create(
            code='CMAT',
            defaults={
                'name': 'College of Management, Accountancy, and Technology',
                'is_active': True,
            }
        )
        prog, _ = Program.objects.get_or_create(
            code='BSIT',
            defaults={
                'department': dept,
                'name': 'Bachelor of Science in Information Technology',
                'years_total': 4,
                'is_active': True,
            }
        )

        # Subject and Class Section
        subject, _ = Subject.objects.get_or_create(
            code='IT311',
            defaults={
                'department': dept,
                'name': 'Advanced Systems Integration and Architecture',
                'units': 3,
                'is_active': True,
            }
        )

        # Ensure demo teacher exists
        teacher_user, _ = User.objects.get_or_create(
            username='teacher.demo',
            defaults={
                'first_name': 'Prof. Maria',
                'last_name': 'Santos',
                'email': 'maria.santos@kcc.edu.ph',
            }
        )
        if not teacher_user.has_usable_password():
            teacher_user.set_password('KccDemo2026!')
            teacher_user.save()

        teacher_profile, _ = Profile.objects.get_or_create(
            user=teacher_user,
            defaults={
                'role': Profile.ROLE_TEACHER,
                'department': dept,
                'approval_status': Profile.APPROVAL_APPROVED,
                'qr_secret': secrets.token_hex(32),
            }
        )

        class_obj, _ = Class.objects.get_or_create(
            class_code='BSIT-3A',
            defaults={
                'subject': subject,
                'program': prog,
                'section_name': '3A',
                'instructor': teacher_profile,
                'is_active': True,
            }
        )

        students_data = [
            ('2024-0010', 'Juan', 'Dela Cruz', 'juan.delacruz', 'juan.cruz@kcc.edu.ph', Profile.APPROVAL_APPROVED, 3),
            ('2024-0011', 'Ana', 'Reyes', 'ana.reyes', 'ana.reyes@kcc.edu.ph', Profile.APPROVAL_APPROVED, 3),
            ('2024-0012', 'Carlos', 'Garcia', 'carlos.garcia', 'carlos.garcia@kcc.edu.ph', Profile.APPROVAL_APPROVED, 3),
            ('2024-0013', 'Bea', 'Mendoza', 'bea.mendoza', 'bea.mendoza@kcc.edu.ph', Profile.APPROVAL_PENDING, 3),
            ('2024-0014', 'Dennis', 'Lim', 'dennis.lim', 'dennis.lim@kcc.edu.ph', Profile.APPROVAL_PENDING, 3),
            ('2024-0015', 'Elena', 'Torres', 'elena.torres', 'elena.torres@kcc.edu.ph', Profile.APPROVAL_REJECTED, 3),
            ('2024-0016', 'Francis', 'Flores', 'francis.flores', 'francis.flores@kcc.edu.ph', Profile.APPROVAL_APPROVED, 2),
            ('2024-0017', 'Grace', 'Villanueva', 'grace.v', 'grace.v@kcc.edu.ph', Profile.APPROVAL_APPROVED, 1),
        ]

        seeded_count = 0
        for s_num, fn, ln, u_name, email, app_status, yr in students_data[:count]:
            user, u_created = User.objects.get_or_create(
                username=u_name,
                defaults={
                    'first_name': fn,
                    'last_name': ln,
                    'email': email,
                }
            )
            if u_created or not user.has_usable_password():
                user.set_password('KccDemo2026!')
                user.save()

            profile, p_created = Profile.objects.get_or_create(
                user=user,
                defaults={
                    'role': Profile.ROLE_STUDENT,
                    'student_number': s_num,
                    'program': prog,
                    'year_level': yr,
                    'approval_status': app_status,
                    'qr_secret': secrets.token_hex(32),
                    'approval_note': 'Missing clear copy of Certificate of Registration' if app_status == Profile.APPROVAL_REJECTED else None,
                    'approved_at': timezone.now() if app_status == Profile.APPROVAL_APPROVED else None,
                }
            )

            # Enroll in BSIT-3A
            if app_status == Profile.APPROVAL_APPROVED:
                Enrollment.objects.get_or_create(
                    student_profile=profile,
                    class_obj=class_obj,
                    defaults={'status': Enrollment.STATUS_ACTIVE}
                )

            if p_created:
                seeded_count += 1
                self.stdout.write(self.style.SUCCESS(f"Seeded student: {fn} {ln} ({s_num}) - {app_status}"))
            else:
                self.stdout.write(f"Student exists: {fn} {ln} ({s_num})")

        self.stdout.write(self.style.SUCCESS(
            f"\n[DONE] Seeded {seeded_count} student records in section {class_obj.class_code}."
        ))
