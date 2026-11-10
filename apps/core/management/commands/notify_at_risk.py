"""
# // ==============================================================================
# // KCC CLASSSTAMP - AT-RISK ATTENDANCE WORKFLOW (task 4.4)
# // ==============================================================================
# // Usage: python manage.py notify_at_risk [--dry-run] [--threshold 20]
# // Description:
# //   Walks every active class in the active term, computes each student's
# //   unexcused absence rate with the canonical absence-radar calculation, and:
# //     - at/above threshold: creates at most one OPEN AnomalyFlag per
# //       student/class/academic year, emails AND in-app notifies the student
# //       and the assigned teacher (Web Push then flows through the repaired
# //       notification integration), and audits flags + notifications;
# //     - below threshold: marks any OPEN at-risk flag RESOLVED with
# //       resolved_at set (e.g. after an excuse approval lowered the rate).
# //
# //   This is the deliberate alternative to mailing on every scan: one
# //   auditable daily run instead of notification spam.
# //     --dry-run    report who would be mailed; no flags, mail, or resolves
# //     --threshold  override the SystemPolicy value for this run
# //
# // Daily scheduling:
# //   Windows Task Scheduler (XAMPP deployment) — run daily at 06:00:
# //     schtasks /create /tn "ClassStamp At-Risk" /tr "python <project>\\pmanage.py notify_at_risk" /sc daily /st 06:00
# //   Linux/cron:
# //     0 6 * * * python /path/to/pmanage.py notify_at_risk
# // ==============================================================================
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core.models import AcademicYear, AnomalyFlag, AuditEvent, Class, Enrollment
from apps.core.services.attendance_policy import absence_threshold_percent
from apps.core.services.in_app_notification_service import create_notification
from apps.core.services.notification_service import notify_at_risk, notify_user
from apps.core.views.helpers.absence_radar import absence_radar_for_students

RULE_AT_RISK = 'RULE_AT_RISK_ABSENCE'


class Command(BaseCommand):
    help = (
        'Emails and in-app notifies students and teachers whose unexcused '
        'absence rate has reached the threshold, and maintains at-risk flags'
    )

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

        classes = Class.objects.filter(
            academic_year=term, is_active=True,
        ).select_related('teacher_profile__user')

        already_mailed = set()
        notified_teacher_keys = set()
        mailed = 0
        at_risk = 0
        flags_created = 0
        flags_resolved = 0
        notifications_sent = 0

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
                    # Below threshold: resolve any OPEN at-risk flag for this
                    # student/class/term (e.g. after an excuse was approved).
                    if dry_run:
                        continue
                    resolved = AnomalyFlag.objects.filter(
                        student_profile=profile,
                        class_obj=class_obj,
                        academic_year=term,
                        rule_code=RULE_AT_RISK,
                        status=AnomalyFlag.STATUS_OPEN,
                    ).update(
                        status=AnomalyFlag.STATUS_RESOLVED,
                        resolved_at=timezone.now(),
                    )
                    if resolved:
                        flags_resolved += resolved
                        AuditEvent.objects.create(
                            actor=None,
                            action='AT_RISK_FLAG_RESOLVED',
                            object_type='AnomalyFlag',
                            object_id=str(profile.pk),
                            reason=(
                                f'{profile.student_number} {class_obj.class_code} '
                                f'rate {entry["rate"]}% is below {threshold}%'
                            ),
                        )
                    continue

                at_risk += 1

                if dry_run:
                    self.stdout.write(
                        f'[DRY-RUN] {profile.student_number} {profile.user.get_full_name()} '
                        f'— {class_obj.class_code} at {entry["rate"]}%'
                    )
                    continue

                # At most one OPEN flag per student/class/academic year.
                open_flag = AnomalyFlag.objects.filter(
                    student_profile=profile,
                    class_obj=class_obj,
                    academic_year=term,
                    rule_code=RULE_AT_RISK,
                    status=AnomalyFlag.STATUS_OPEN,
                ).first()
                if open_flag is None:
                    AnomalyFlag.objects.create(
                        student_profile=profile,
                        class_obj=class_obj,
                        academic_year=term,
                        rule_code=RULE_AT_RISK,
                        reason=(
                            f'Unexcused absence rate {entry["rate"]}% is at or above '
                            f'the institutional threshold of {threshold}% '
                            f'({entry["absent"]}/{entry["total"]} finalized records).'
                        ),
                        risk_score=None,
                    )
                    flags_created += 1
                    AuditEvent.objects.create(
                        actor=None,
                        action='AT_RISK_FLAG_CREATED',
                        object_type='AnomalyFlag',
                        object_id=f'{profile.pk}:{class_obj.pk}',
                        reason=(
                            f'{profile.student_number} {class_obj.class_code} '
                            f'rate {entry["rate"]}% >= {threshold}%'
                        ),
                    )

                # One student email per run even if at risk in several subjects.
                if profile.id not in already_mailed:
                    already_mailed.add(profile.id)
                    if notify_at_risk(profile, class_obj, entry['rate'], threshold):
                        mailed += 1
                        notifications_sent += 1
                    create_notification(
                        profile.user,
                        'attendance',
                        'Attendance warning',
                        (
                            f'Your unexcused absence rate in {class_obj.class_code} '
                            f'is {entry["rate"]}%, at or above the {threshold}% limit. '
                            'Please coordinate with your instructor.'
                        ),
                        '/student/attendance/',
                    )
                    notifications_sent += 1

                # Notify the assigned teacher for this class (email + in-app).
                teacher_user = (
                    class_obj.teacher_profile.user
                    if class_obj.teacher_profile else None
                )
                teacher_key = (class_obj.pk, profile.id)
                if teacher_user is not None and teacher_key not in notified_teacher_keys:
                    notified_teacher_keys.add(teacher_key)
                    if notify_user(
                        teacher_user,
                        f'[KCC ClassStamp] Student at risk — {class_obj.class_code}',
                        (
                            f'{profile.user.get_full_name() or profile.user.get_username()} '
                            f'({profile.student_number}) is at {entry["rate"]}% unexcused '
                            f'absences in {class_obj.class_code} ({class_obj.subject.code}), '
                            f'at or above the {threshold}% limit.'
                        ),
                        action='NOTIFY_AT_RISK_TEACHER',
                        object_type='Class',
                        object_id=class_obj.pk,
                    ):
                        notifications_sent += 1
                    create_notification(
                        teacher_user,
                        'attendance',
                        'Student at risk',
                        (
                            f'{profile.user.get_full_name() or profile.user.get_username()} '
                            f'is at {entry["rate"]}% unexcused absences in '
                            f'{class_obj.class_code}.'
                        ),
                        '/teacher/classes/',
                    )
                    notifications_sent += 1

        if not dry_run:
            AuditEvent.objects.create(
                actor=None,
                action='AT_RISK_RUN_COMPLETE',
                object_type='AcademicYear',
                object_id=str(term.pk),
                new_value=(
                    f'at_risk_class_warnings={at_risk}; flags_created={flags_created}; '
                    f'flags_resolved={flags_resolved}; notifications_sent={notifications_sent}; '
                    f'students_emailed={len(already_mailed)}'
                ),
                reason=f'threshold={threshold}%',
            )

        verb = 'Would email' if dry_run else 'Emailed'
        self.stdout.write(self.style.SUCCESS(
            f'{verb} {len(already_mailed)} student(s) at or above {threshold}% '
            f'({at_risk} class-level warning(s)); flags created {flags_created}, '
            f'resolved {flags_resolved}, notifications {notifications_sent}.'
        ))
