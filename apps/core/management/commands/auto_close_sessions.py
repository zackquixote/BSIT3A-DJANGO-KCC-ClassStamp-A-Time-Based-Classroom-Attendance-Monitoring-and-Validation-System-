"""
# // ==============================================================================
# // KCC CLASSSTAMP - AUTOMATIC SESSION CLOSE SCHEDULER (B-12)
# // ==============================================================================
# // Usage: python manage.py auto_close_sessions [--dry-run] [--grace-minutes N]
# // Description: Cron-friendly maintenance command that finalizes OPEN attendance
# //   sessions whose scheduled end time (slot.ends_at) has passed. Marks all
# //   unscanned active enrollees ABSENT (METHOD_SYSTEM), sets auto_closed=True,
# //   and records an AUTO_CLOSE_SESSION audit entry per session.
# //   Recommended cron: */5 * * * * python manage.py auto_close_sessions
# // ==============================================================================
"""

from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.models import (
    AttendanceRecord,
    AuditEvent,
    ClassSession,
    Enrollment,
    Profile,
)


class Command(BaseCommand):
    help = 'Auto-closes OPEN class sessions past their scheduled end time'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report sessions that would be closed without writing anything',
        )
        parser.add_argument(
            '--grace-minutes',
            type=int,
            default=0,
            help='Extra minutes past slot.ends_at before a session is auto-closed (default: 0)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        grace = timedelta(minutes=max(0, options['grace_minutes']))

        # // Slot times are wall-clock (Asia/Manila): compare in local time, not UTC.
        local_now = timezone.localtime()
        now = timezone.now()

        open_sessions = list(
            ClassSession.objects.filter(status=ClassSession.STATUS_OPEN)
            .select_related('slot__class_obj')
            .order_by('session_date')
        )

        due = []
        for session in open_sessions:
            slot = session.slot
            end_dt = timezone.make_aware(datetime.combine(session.session_date, slot.ends_at))
            if local_now >= end_dt + grace:
                due.append(session)

        if not due:
            self.stdout.write(self.style.NOTICE(
                'No OPEN sessions are past their scheduled end time.'
            ))
            return

        total_closed = 0
        total_absent = 0

        for session in due:
            enrolled_profiles = Profile.objects.filter(
                enrollments__class_obj=session.slot.class_obj,
                enrollments__status=Enrollment.STATUS_ACTIVE,
            )
            stamped_ids = set(
                session.attendance_records.values_list('student_profile_id', flat=True)
            )
            missing_profiles = list(enrolled_profiles.exclude(id__in=stamped_ids))

            label = f'{session.slot.class_obj.class_code} {session.session_date}'

            if dry_run:
                self.stdout.write(
                    f'[DRY-RUN] Would close {label} '
                    f'({len(missing_profiles)} student(s) would be marked ABSENT)'
                )
                total_closed += 1
                total_absent += len(missing_profiles)
                continue

            with transaction.atomic():
                new_absent_records = [
                    AttendanceRecord(
                        session=session,
                        student_profile=p,
                        status=AttendanceRecord.STATUS_ABSENT,
                        method=AttendanceRecord.METHOD_SYSTEM,
                        stamped_at=now,
                        marked_by=None,
                        correction_reason='Auto-marked absent at scheduled session end',
                    )
                    for p in missing_profiles
                ]
                if new_absent_records:
                    AttendanceRecord.objects.bulk_create(new_absent_records)

                session.status = ClassSession.STATUS_CLOSED
                session.closed_at = now
                session.auto_closed = True
                session.save(update_fields=['status', 'closed_at', 'auto_closed'])

                AuditEvent.objects.create(
                    actor=None,
                    action='AUTO_CLOSE_SESSION',
                    object_type='ClassSession',
                    object_id=str(session.pk),
                    new_value=f'Auto-closed {label} ({len(new_absent_records)} auto-marked absent)',
                    reason='Automatic session close scheduler',
                )

            self.stdout.write(self.style.SUCCESS(
                f'Closed {label} — {len(new_absent_records)} marked ABSENT'
            ))
            total_closed += 1
            total_absent += len(new_absent_records)

        verb = 'Would close' if dry_run else 'Closed'
        self.stdout.write(self.style.SUCCESS(
            f'[{"DRY-RUN" if dry_run else "SUCCESS"}] {verb} {total_closed} session(s), '
            f'{total_absent} student(s) auto-marked ABSENT.'
        ))
