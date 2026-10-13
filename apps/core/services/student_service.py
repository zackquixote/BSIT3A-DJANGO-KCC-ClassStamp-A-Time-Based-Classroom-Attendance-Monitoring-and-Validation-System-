"""
# // ==============================================================================
# // KCC CLASSSTAMP - STUDENT DIRECTORY & BULK IMPORT SERVICE
# // ==============================================================================
# // Subsystem: Student Management Business Logic
# // Description: Encapsulates student masterlist querying and the CSV bulk import
# //   pipeline. Extracted from student_views.py so the filtering/import logic can
# //   be tested in isolation and reused by management commands or future API views.
# //
# //   build_student_queryset(filters)   — Applies filter params and returns QS
# //   import_students_from_csv(reader, actor, options) — Atomic CSV ingestion
# // ==============================================================================
"""

import csv
import secrets

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.core.models import AuditEvent, Class, Enrollment, Profile, Program

User = get_user_model()


# // ==============================================================================
# // SECTION 1: STUDENT DIRECTORY QUERYSET BUILDER
# // ==============================================================================

def build_student_queryset(filters: dict):
    """
    // [Service] Student Directory Queryset Builder
    // Applies multi-attribute filter parameters against the student Profile table.
    //
    // Arguments:
    //   filters (dict): Expects the following optional keys:
    //     'department'  — Department PK string
    //     'program'     — Program PK string
    //     'year_level'  — Integer year level
    //     'section'     — Class code substring
    //     'status'      — APPROVAL_APPROVED | APPROVAL_PENDING | APPROVAL_REJECTED
    //     'q'           — Full-text search query (name / username / email / student no.)
    //     'sort'        — Sort key (see valid_sorts dict below)
    //
    // Returns: Filtered, ordered Profile QuerySet (not yet paginated).
    """
    dept_id = filters.get('department', '').strip()
    prog_id = filters.get('program', '').strip()
    year_level = filters.get('year_level', '').strip()
    section = filters.get('section', '').strip()
    status = filters.get('status', '').strip()
    q = filters.get('q', '').strip()
    sort = filters.get('sort', '-created_at').strip()

    qs = (
        Profile.objects.filter(role=Profile.ROLE_STUDENT)
        .select_related('user', 'program', 'program__department', 'approved_by')
        .prefetch_related('enrollments__class_obj')
    )

    if dept_id:
        qs = qs.filter(program__department_id=dept_id)

    if prog_id:
        qs = qs.filter(program_id=prog_id)

    if year_level:
        try:
            qs = qs.filter(year_level=int(year_level))
        except ValueError:
            pass

    if status in [Profile.APPROVAL_APPROVED, Profile.APPROVAL_PENDING, Profile.APPROVAL_REJECTED]:
        qs = qs.filter(approval_status=status)

    if section:
        qs = qs.filter(enrollments__class_obj__class_code__icontains=section).distinct()

    if q:
        qs = qs.filter(
            Q(student_number__icontains=q) |
            Q(user__first_name__icontains=q) |
            Q(user__last_name__icontains=q) |
            Q(user__username__icontains=q) |
            Q(user__email__icontains=q)
        )

    valid_sorts = {
        'id_asc':    'student_number',
        'id_desc':   '-student_number',
        'name_asc':  'user__last_name',
        'name_desc': '-user__last_name',
        'year_asc':  'year_level',
        'year_desc': '-year_level',
        'newest':    '-created_at',
        'oldest':    'created_at',
    }
    qs = qs.order_by(valid_sorts.get(sort, '-created_at'))

    return qs


# // ==============================================================================
# // SECTION 2: BULK CSV STUDENT IMPORT PIPELINE
# // ==============================================================================

def import_students_from_csv(
    reader: csv.DictReader,
    actor,
    default_password: str = 'KccStudent2026!',
    auto_approve: bool = False,
    target_class=None,
) -> dict:
    """
    // [Service] Atomic Bulk CSV Student Ingestion
    //
    // Processes each row of a DictReader, validates field values, creates User +
    // Profile records inside individual atomic savepoints, and emits AuditEvents.
    //
    // Arguments:
    //   reader           (csv.DictReader): Parsed CSV rows iterator.
    //   actor            (User):           Admin requesting the import.
    //   default_password (str):            Fallback password if not in CSV.
    //   auto_approve     (bool):           If True, sets APPROVED + approved_by/at immediately.
    //   target_class     (Class|None):     Optional class section to enroll all imports into.
    //
    // Returns:
    //   dict with keys:
    //     'created_count' (int)  — number of successfully provisioned profiles
    //     'skipped_count' (int)  — number of skipped rows
    //     'errors'        (list) — row-level error descriptions (capped at 50)
    """
    programs_by_code = {p.code.upper(): p for p in Program.objects.all()}
    classes_by_code = {c.class_code.upper(): c for c in Class.objects.filter(is_active=True)}

    created_count = 0
    skipped_count = 0
    errors = []
    row_index = 1

    for row in reader:
        row_index += 1
        norm_row = {k.strip().lower(): v.strip() for k, v in row.items() if k}

        # // Field aliasing — accept common CSV header variations
        student_no = (
            norm_row.get('student_number') or norm_row.get('student_id')
            or norm_row.get('id_number') or norm_row.get('student no')
            or norm_row.get('student no.')
        )
        first_name   = norm_row.get('first_name') or norm_row.get('firstname') or norm_row.get('given name')
        last_name    = norm_row.get('last_name') or norm_row.get('lastname') or norm_row.get('surname')
        email        = norm_row.get('email') or norm_row.get('email address')
        prog_code    = norm_row.get('program') or norm_row.get('program_code') or norm_row.get('course')
        year_lvl_raw = norm_row.get('year_level') or norm_row.get('year') or norm_row.get('standing')
        section_code = norm_row.get('section') or norm_row.get('class_code')
        pwd          = norm_row.get('password') or default_password
        username     = norm_row.get('username')

        # // Skip completely empty rows
        if not any([student_no, first_name, last_name, email]):
            continue

        # // Row-level validation
        if not student_no:
            errors.append(f'Row {row_index}: Student ID Number is missing.')
            skipped_count += 1
            continue

        if not first_name or not last_name:
            errors.append(f'Row {row_index} ({student_no}): First Name and Last Name are required.')
            skipped_count += 1
            continue

        if not email:
            errors.append(f'Row {row_index} ({student_no}): Email address is missing.')
            skipped_count += 1
            continue

        if not prog_code or prog_code.upper() not in programs_by_code:
            errors.append(f'Row {row_index} ({student_no}): Program code "{prog_code}" does not exist.')
            skipped_count += 1
            continue
        program = programs_by_code[prog_code.upper()]

        try:
            year_level = int(year_lvl_raw) if year_lvl_raw else 1
            if year_level < 1 or year_level > program.years_total:
                errors.append(f'Row {row_index} ({student_no}): Year level {year_level} invalid for {program.code}.')
                skipped_count += 1
                continue
        except ValueError:
            errors.append(f'Row {row_index} ({student_no}): Invalid year level "{year_lvl_raw}".')
            skipped_count += 1
            continue

        if Profile.objects.filter(student_number__iexact=student_no).exists():
            errors.append(f'Row {row_index} ({student_no}): Student ID already registered.')
            skipped_count += 1
            continue

        # // Username auto-generation (firstname.lastname + numeric suffix)
        if not username:
            base_user = f"{first_name.lower().replace(' ', '')}.{last_name.lower().replace(' ', '')}"
            username = base_user
            suffix = 1
            while User.objects.filter(username__iexact=username).exists():
                username = f'{base_user}{suffix}'
                suffix += 1
        elif User.objects.filter(username__iexact=username).exists():
            errors.append(f'Row {row_index} ({student_no}): Username "{username}" already taken.')
            skipped_count += 1
            continue

        if User.objects.filter(email__iexact=email).exists():
            errors.append(f'Row {row_index} ({student_no}): Email "{email}" already in use.')
            skipped_count += 1
            continue

        # // Atomic per-row creation
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username, email=email,
                    first_name=first_name, last_name=last_name, password=pwd,
                )
                profile = Profile.objects.create(
                    user=user,
                    role=Profile.ROLE_STUDENT,
                    program=program,
                    year_level=year_level,
                    student_number=student_no,
                    approval_status=Profile.APPROVAL_APPROVED if auto_approve else Profile.APPROVAL_PENDING,
                    qr_secret=secrets.token_hex(32),
                    approved_by=actor if auto_approve else None,
                    approved_at=timezone.now() if auto_approve else None,
                )

                # // Section enrollment — prefer per-row section code over global target_class
                assigned_class = target_class
                if section_code and section_code.upper() in classes_by_code:
                    assigned_class = classes_by_code[section_code.upper()]

                if assigned_class:
                    Enrollment.objects.get_or_create(
                        student_profile=profile,
                        class_obj=assigned_class,
                        defaults={
                            'status': Enrollment.STATUS_ACTIVE,
                            'approved_by': actor,
                            'approved_at': timezone.now(),
                        }
                    )

                AuditEvent.objects.create(
                    actor=actor,
                    action='BULK_IMPORT_STUDENT',
                    object_type='Profile',
                    object_id=str(profile.pk),
                    new_value=f'{student_no} - {user.get_full_name()} ({program.code})',
                    reason='CSV Batch Import roster ingestion',
                )
                created_count += 1

        except Exception as ex:
            errors.append(f'Row {row_index} ({student_no}): Database error: {str(ex)}')
            skipped_count += 1

    return {
        'created_count': created_count,
        'skipped_count': skipped_count,
        'errors': errors[:50],
    }
