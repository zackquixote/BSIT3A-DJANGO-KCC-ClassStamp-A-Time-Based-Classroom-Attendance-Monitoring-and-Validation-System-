"""
# // ==============================================================================
# // KCC CLASSSTAMP - ENROLLMENT VALIDATION SERVICE
# // ==============================================================================
# // Subsystem: Enrollment Integrity (tasks 2.1 / 2.2 — Req 1 & 2)
# // Description: Shared curriculum-version and class-capacity validation that
# //   MUST be called by the three existing enrollment paths:
# //     A. student_join_class            (student join code)
# //     B. class_roster_enroll           (single manual)
# //     C. class_roster_enroll_batch     (batch manual)
# //   This service does not create enrollments and does not replace those views.
# //
# // Curriculum rule (Req 1):
# //   - Student with no curriculum_version -> reject, "contact administration".
# //   - Class subject must have a Curriculum row for THAT version.
# //   - No fallback to legacy (version IS NULL) rows for a student who has a
# //     version, and no use of the term resolver (resolve_curriculum_version).
# //
# // Capacity rule (Req 2):
# //   - capacity None/0 -> unlimited.
# //   - Counting: join-code path counts ACTIVE only (current behavior);
# //     manual paths reserve ACTIVE+PENDING. Callers choose via include_pending.
# //   - Lowering capacity never evicts anyone.
# //   - Only an admin may override, explicitly, with an audit event.
# // ==============================================================================
"""

from django.utils import timezone

from apps.core.models import AuditEvent, Curriculum, Enrollment


def validate_student_curriculum(student_profile, class_obj) -> tuple:
    """
    // Validate that class_obj.subject exists in the student's curriculum version.
    //
    // Returns:
    //   (ok, code, message)
    //     ok=True, '', ''
    //     ok=False, 'CURRICULUM_VERSION_MISSING', contact-administration text
    //     ok=False, 'CURRICULUM_SUBJECT_NOT_IN_VERSION', subject-not-in-version
    """
    version_id = getattr(student_profile, 'curriculum_version_id', None)
    if not version_id:
        return (
            False,
            'CURRICULUM_VERSION_MISSING',
            'No curriculum version assigned. Please contact administration.',
        )

    exists = Curriculum.objects.filter(
        version_id=version_id,
        subject_id=class_obj.subject_id,
    ).exists()
    if not exists:
        subject_code = getattr(class_obj.subject, 'code', class_obj.subject_id)
        return (
            False,
            'CURRICULUM_SUBJECT_NOT_IN_VERSION',
            f'Subject {subject_code} is not part of your curriculum.',
        )
    return True, '', ''


def check_class_capacity(class_obj, *, include_pending: bool = False) -> tuple:
    """
    // Check whether class_obj still has room for one more ACTIVE enrollment.
    //
    // include_pending=False counts ACTIVE only (join-code path).
    // include_pending=True counts ACTIVE+PENDING (manual roster paths).
    //
    // Returns:
    //   (has_capacity, message)
    //   capacity falsy -> (True, '') unlimited; never evicts on shrink.
    """
    if not class_obj.capacity:
        return True, ''

    statuses = [Enrollment.STATUS_ACTIVE]
    if include_pending:
        statuses.append(Enrollment.STATUS_PENDING)
    reserved = Enrollment.objects.filter(
        class_obj=class_obj,
        status__in=statuses,
    ).count()

    if reserved >= class_obj.capacity:
        return (
            False,
            f'Class is full ({reserved}/{class_obj.capacity}).',
        )
    return True, ''


def audit_enrollment_rejection(
    *,
    actor,
    student_profile,
    class_obj,
    code: str,
    message: str,
    override: bool = False,
) -> None:
    """
    // Req 1.5 / 2.x: log curriculum and capacity rejections (and explicit
    // overrides) with student ID, class code, and reason.
    """
    action = {
        'CURRICULUM_VERSION_MISSING': 'ENROLLMENT_REJECTED_CURRICULUM',
        'CURRICULUM_SUBJECT_NOT_IN_VERSION': 'ENROLLMENT_REJECTED_CURRICULUM',
        'CAPACITY': 'ENROLLMENT_REJECTED_CAPACITY',
    }.get(code, 'ENROLLMENT_REJECTED')
    if override:
        action = f'{action}_OVERRIDE'

    AuditEvent.objects.create(
        actor=actor,
        action=action,
        object_type='Enrollment',
        object_id=f'{student_profile.pk}:{class_obj.pk}',
        reason=(
            f'student={student_profile.student_number or student_profile.pk} '
            f'class={class_obj.class_code} code={code} {message}'
        ),
        new_value=f'{timezone.localtime(timezone.now()):%Y-%m-%d %H:%M} {class_obj.class_code}',
    )
