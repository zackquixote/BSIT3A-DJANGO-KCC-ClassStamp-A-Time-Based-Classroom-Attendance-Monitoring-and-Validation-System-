"""
# // ==============================================================================
# // KCC CLASSSTAMP - AT-RISK ATTENDANCE MAILER
# // ==============================================================================
# // Usage: python manage.py notify_at_risk [--dry-run] [--threshold 20]
# // Description:
# //   Walks every active class in the active term, computes each student's
# //   unexcused absence rate, and emails the ones at or above the institutional
# //   threshold. This is the deliberate alternative to mailing on every scan:
# //   one auditable run, run by a person, instead of notification spam.
# //     --dry-run    report who would be mailed, send nothing
# //     --threshold  override the SystemPolicy value for this run
# // ==============================================================================
"""

from django.core.management.base import BaseCommand

from apps.core.models import AcademicYear, Class, Enrollment
from apps.core.services.attendance_policy import absence_threshold_percent
from apps.core.services.notification_service import notify_at_risk
from apps.core.views.helpers.absence_radar import absence_radar_for_students


class Command(BaseCommand):
    help = 'Emails students whose unexcused absence rate has reached the threshold'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--threshold', type=float, default=None)

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        threshold = options['threshold'] or absence_threshold_percent()

        term = AcademicYear.objects.filter(is_active=True).first()
        if term is None:
            self.stdout.write(self.style.WARNING('No active academic year — nothing to do.'))
            return

        classes = Class.objects.filter(academic_year=term, is_active=True)

        already_mailed = set()
        mailed = 0
        at_risk = 0

        for class_obj in classes:
            enrollments = (
                Enrollment.objects
                .filter(class_obj=class_obj, status=Enrollment.STATUS_ACTIVE)
                .select_related('student_profile__user')
            )
            profiles = [e.student_profile for e in enrollments]
            if not profiles:
                continue

            radar = absence_radar_for_students(class_obj, [p.id for p in profiles])

            for profile in profiles:
                entry = radar.get(profile.id)
                if not entry or not entry['total']:
                    continue
                if entry['rate'] < threshold:
                    continue

                at_risk += 1
                # One message per student per run even if they are at risk in
                # several subjects; the per-class detail is in the body.
                if profile.id in already_mailed:
                    continue
                already_mailed.add(profile.id)

                if dry_run:
                    self.stdout.write(
                        f'[DRY-RUN] {profile.student_number} {profile.user.get_full_name()} '
                        f'— {class_obj.class_code} at {entry["rate"]}%'
                    )
                    continue

                if notify_at_risk(profile, class_obj, entry['rate'], threshold):
                    mailed += 1

        verb = 'Would email' if dry_run else 'Emailed'
        self.stdout.write(self.style.SUCCESS(
            f'{verb} {len(already_mailed)} student(s) at or above {threshold}% '
            f'({at_risk} class-level warning(s)).'
        ))
