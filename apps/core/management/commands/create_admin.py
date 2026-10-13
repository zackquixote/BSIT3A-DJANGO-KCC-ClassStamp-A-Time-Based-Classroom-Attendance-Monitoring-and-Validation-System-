from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.core.models import Profile

User = get_user_model()


class Command(BaseCommand):
    help = (
        "Create (or update) a superuser AND its matching ADMIN Profile row, "
        "so the user can access both the Django admin site and the ClassStamp "
        "admin dashboard."
    )

    def add_arguments(self, parser):
        parser.add_argument("--username", default="admin")
        parser.add_argument("--email", default="admin@classstamp.local")
        parser.add_argument("--password", default="admin12345")

    def handle(self, *args, **options):
        username = options["username"]
        email = options["email"]
        password = options["password"]

        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": email, "is_staff": True, "is_superuser": True},
        )

        if created:
            user.set_password(password)
            user.is_staff = True
            user.is_superuser = True
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Created superuser '{username}'"))
        else:
            # Always reset password + privileges on re-run so the command is idempotent.
            user.email = email
            user.set_password(password)
            user.is_staff = True
            user.is_superuser = True
            user.save()
            self.stdout.write(self.style.WARNING(f"Updated existing user '{username}' (password reset, staff/superuser ensured)"))

        # The ClassStamp admin dashboard is driven by the ADMIN Profile row.
        # chk_cs_profile_shape requires ALL of these to be NULL for an ADMIN.
        profile, p_created = Profile.objects.get_or_create(
            user=user,
            defaults={
                "role": Profile.ROLE_ADMIN,
                "department_id": None,
                "approval_status": None,
                "student_number": None,
                "program_id": None,
                "year_level": None,
                "qr_secret": None,
            },
        )
        if not p_created:
            profile.role = Profile.ROLE_ADMIN
            profile.department_id = None
            profile.approval_status = None
            profile.student_number = None
            profile.program_id = None
            profile.year_level = None
            profile.qr_secret = None
            profile.save()
            self.stdout.write(self.style.SUCCESS("Ensured ADMIN Profile exists (all role-incompatible fields set NULL)"))
        else:
            self.stdout.write(self.style.SUCCESS("Created ADMIN Profile"))

        self.stdout.write(self.style.SUCCESS("\nAdmin ready:"))
        self.stdout.write(f"  Username: {username}")
        self.stdout.write(f"  Password: {password}")
        self.stdout.write(f"  Django admin site: http://127.0.0.1:8000/admin/")
        self.stdout.write(f"  ClassStamp dashboard: http://127.0.0.1:8000/home/")
