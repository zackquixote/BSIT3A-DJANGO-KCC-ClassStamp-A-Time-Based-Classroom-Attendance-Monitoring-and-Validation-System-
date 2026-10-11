from django.core.management.base import BaseCommand
from apps.core.models import Department, Program


class Command(BaseCommand):
    help = 'Seeds KCC official College Departments and Programs'

    def handle(self, *args, **options):
        data = [
            {
                'code': 'CEAS',
                'name': 'College of Education, Arts, and Sciences',
                'programs': [
                    ('BSED-ENG', 'Bachelor of Secondary Education major in English', 4),
                    ('BSED-SCI', 'Bachelor of Secondary Education major in Science', 4),
                    ('BSED-FIL', 'Bachelor of Secondary Education major in Filipino', 4),
                    ('BSED-VAL', 'Bachelor of Secondary Education major in Values Education', 4),
                    ('BEED', 'Bachelor of Elementary Education', 4),
                    ('AB-PHIL', 'Bachelor of Arts in Philosophy', 4),
                    ('AB-PSYCH', 'Bachelor of Arts in Psychology', 4),
                    ('AB-ELS', 'Bachelor of Arts in English Language Studies', 4),
                ]
            },
            {
                'code': 'CMAT',
                'name': 'College of Management, Accountancy, and Technology',
                'programs': [
                    ('BSA', 'Bachelor of Science in Accountancy', 4),
                    ('BSBA', 'Bachelor of Science in Business Administration', 4),
                    ('BSIT', 'Bachelor of Science in Information Technology', 4),
                ]
            },
            {
                'code': 'COC',
                'name': 'College of Criminology',
                'programs': [
                    ('BSCRIM', 'Bachelor of Science in Criminology', 4),
                ]
            },
        ]

        created_depts = 0
        created_progs = 0

        for item in data:
            dept, created = Department.objects.get_or_create(
                code=item['code'],
                defaults={'name': item['name'], 'is_active': True}
            )
            if created:
                created_depts += 1
                self.stdout.write(self.style.SUCCESS(f"Created Department: {dept.name} ({dept.code})"))
            else:
                self.stdout.write(f"Department exists: {dept.name} ({dept.code})")

            for p_code, p_name, years in item['programs']:
                prog, p_created = Program.objects.get_or_create(
                    code=p_code,
                    defaults={
                        'department': dept,
                        'name': p_name,
                        'years_total': years,
                        'is_active': True
                    }
                )
                if p_created:
                    created_progs += 1
                    self.stdout.write(self.style.SUCCESS(f"  + Program: {prog.name} ({prog.code})"))
                else:
                    self.stdout.write(f"  Program exists: {prog.name} ({prog.code})")

        self.stdout.write(self.style.SUCCESS(
            f"\nDone! Added {created_depts} departments and {created_progs} programs."
        ))
