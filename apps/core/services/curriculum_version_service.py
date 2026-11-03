"""
# // ==============================================================================
# // KCC CLASSSTAMP - CURRICULUM VERSION WORKFLOW SERVICE
# // ==============================================================================
# // Subsystem: Academic Organisation / Curriculum Governance
# // Description: Version resolution, draft cloning, approval, and edit guards
# //   for program curricula. Approved versions are immutable snapshots; changes
# //   are prepared in a draft and only become official when approved.
# // ==============================================================================
"""

from django.db import transaction
from django.db.models import Max, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.core.models import (
    AcademicYear,
    AuditEvent,
    Curriculum,
    CurriculumVersion,
    Program,
)


STATUS_DRAFT = CurriculumVersion.STATUS_DRAFT
STATUS_APPROVED = CurriculumVersion.STATUS_APPROVED
STATUS_ARCHIVED = CurriculumVersion.STATUS_ARCHIVED

# Versions that describe official curriculum: the current approved snapshot plus
# legacy rows created before versioning existed.
OFFICIAL_STATUSES = (STATUS_APPROVED, STATUS_ARCHIVED)


def official_curriculum_filter(prefix: str = '') -> Q:
    """Return the ORM filter for approved and legacy curriculum entries.

    Pass a relation prefix (for example ``curriculum_entries__``) when the
    filter is applied from a Subject or Program queryset.
    """
    return (
        Q(**{f'{prefix}version__status': STATUS_APPROVED})
        | Q(**{f'{prefix}version__isnull': True})
    )


def official_curriculum_entries(program=None):
    """Return the official curriculum queryset, optionally scoped to a program."""
    queryset = Curriculum.objects.filter(official_curriculum_filter())
    if program is not None:
        queryset = queryset.filter(program=program)
    return queryset


def latest_curriculum_version(program, statuses=None):
    """Return the newest version for a program, optionally filtered by status."""
    queryset = CurriculumVersion.objects.filter(program=program)
    if statuses:
        queryset = queryset.filter(status__in=statuses)
    return queryset.order_by('-version_number').first()


def current_draft_version(program):
    """Return the program's editable draft version, if any."""
    return latest_curriculum_version(program, statuses=(STATUS_DRAFT,))


def resolve_curriculum_version(program, academic_year=None):
    """
    // Resolve the curriculum version that applies to a term.
    //
    // The approved version whose effective_from is the latest term at or before
    // the requested one wins. Archived versions stay eligible so historical
    // terms can still resolve the snapshot that was in force then. A version
    // with no effective_from applies from the beginning.
    """
    queryset = CurriculumVersion.objects.filter(
        program=program,
        status__in=OFFICIAL_STATUSES,
    )
    if academic_year is not None:
        queryset = queryset.filter(
            Q(effective_from__isnull=True)
            | Q(effective_from__starts_on__lte=academic_year.starts_on)
        )
    version = queryset.order_by('-version_number').first()
    if version is not None:
        return version

    # Fall back to the newest approved version even if its effective date is
    # later than the requested term. This keeps upcoming-term setup usable.
    return (
        CurriculumVersion.objects.filter(
            program=program,
            status=STATUS_APPROVED,
        )
        .order_by('-version_number')
        .first()
    )


def curriculum_version_state(program):
    """Return the version state the matrix editor needs for one program."""
    draft = current_draft_version(program)
    approved = latest_curriculum_version(program, statuses=(STATUS_APPROVED,))
    return {
        'draft': draft,
        'approved': approved,
        'display': draft or approved,
    }


def _version_label(version):
    return f'v{version.version_number}'


def _copy_entries(version, source_version=None, include_legacy=False):
    """Copy curriculum rows into a draft, preserving year/semester/subject."""
    if source_version is not None:
        source = Curriculum.objects.filter(version=source_version)
    elif include_legacy:
        source = Curriculum.objects.filter(
            program=version.program,
            version__isnull=True,
        )
    else:
        source = Curriculum.objects.none()

    rows = [
        Curriculum(
            program=version.program,
            version=version,
            year_level=entry.year_level,
            semester=entry.semester,
            subject_id=entry.subject_id,
        )
        for entry in source.select_related('subject').order_by(
            'year_level', 'semester', 'subject__code',
        )
    ]
    if rows:
        Curriculum.objects.bulk_create(rows)
    return len(rows)


@transaction.atomic
def create_curriculum_draft(actor, program, notes='', source_version=None):
    """
    // Create a draft by cloning the latest approved version (or legacy rows).
    //
    // A program can only have one draft at a time. Calling this again returns
    // the existing draft so repeated clicks do not create duplicate versions.
    """
    program = get_object_or_404(
        Program.objects.select_for_update(),
        pk=getattr(program, 'pk', program),
    )
    existing = (
        CurriculumVersion.objects.select_for_update()
        .filter(program=program, status=STATUS_DRAFT)
        .order_by('-version_number')
        .first()
    )
    if existing is not None:
        return {
            'instance': existing,
            'created': False,
            'message': f'{program.code} already has draft {_version_label(existing)}.',
        }

    if source_version is None:
        source_version = latest_curriculum_version(
            program, statuses=(STATUS_APPROVED,)
        )

    next_number = (
        CurriculumVersion.objects.filter(program=program)
        .aggregate(max_number=Max('version_number'))['max_number']
        or 0
    ) + 1

    version = CurriculumVersion.objects.create(
        program=program,
        version_number=next_number,
        status=STATUS_DRAFT,
        notes=(notes or '').strip(),
        created_by=actor if getattr(actor, 'pk', None) else None,
    )
    cloned_count = _copy_entries(
        version,
        source_version=source_version,
        include_legacy=source_version is None,
    )

    AuditEvent.objects.create(
        actor=actor if getattr(actor, 'pk', None) else None,
        action='CREATE_CURRICULUM_DRAFT',
        object_type='CurriculumVersion',
        object_id=str(version.pk),
        new_value=(
            f'{program.code} {_version_label(version)} '
            f'cloned from '
            f'{_version_label(source_version) if source_version else "legacy rows"} '
            f'({cloned_count} entries)'
        ),
    )

    return {
        'instance': version,
        'created': True,
        'cloned_count': cloned_count,
        'message': (
            f'Draft {_version_label(version)} created for {program.code} '
            f'with {cloned_count} subject mapping(s).'
        ),
    }


@transaction.atomic
def approve_curriculum_draft(actor, version, effective_from=None, notes=None):
    """
    // Approve a draft, archive the outgoing approved version, and record who
    // // approved it and when.
    """
    version = (
        CurriculumVersion.objects.select_for_update()
        .select_related('program')
        .get(pk=getattr(version, 'pk', version))
    )
    if version.status != STATUS_DRAFT:
        raise ValueError('Only a draft curriculum version can be approved.')

    if not version.entries.exists():
        raise ValueError(
            'Add at least one subject to the draft before approving it.'
        )

    if effective_from is not None and not isinstance(effective_from, AcademicYear):
        effective_from = get_object_or_404(AcademicYear, pk=effective_from)

    previous = list(
        CurriculumVersion.objects.filter(
            program=version.program,
            status=STATUS_APPROVED,
        )
    )
    CurriculumVersion.objects.filter(pk__in=[row.pk for row in previous]).update(
        status=STATUS_ARCHIVED,
        updated_at=timezone.now(),
    )

    version.status = STATUS_APPROVED
    version.effective_from = effective_from
    version.approved_by = actor if getattr(actor, 'pk', None) else None
    version.approved_at = timezone.now()
    if notes is not None:
        version.notes = notes.strip()
    version.save(update_fields=[
        'status', 'effective_from', 'approved_by', 'approved_at', 'notes',
        'updated_at',
    ])

    AuditEvent.objects.create(
        actor=actor if getattr(actor, 'pk', None) else None,
        action='APPROVE_CURRICULUM_VERSION',
        object_type='CurriculumVersion',
        object_id=str(version.pk),
        old_value=(
            ', '.join(_version_label(row) for row in previous)
            if previous else 'no approved version'
        ),
        new_value=(
            f'{version.program.code} {_version_label(version)} approved'
            + (
                f' effective {effective_from.name}'
                if effective_from is not None else ' with no effective term'
            )
        ),
    )

    return {
        'instance': version,
        'archived_count': len(previous),
        'message': (
            f'{version.program.code} {_version_label(version)} is now approved'
            + (
                f' effective {effective_from.name}.'
                if effective_from is not None else ' with no effective term.'
            )
        ),
    }


def ensure_draft_version(actor, program):
    """Return the program's draft, creating one from current official rows."""
    draft = current_draft_version(program)
    if draft is not None:
        return draft
    return create_curriculum_draft(actor, program)['instance']


def assert_entry_editable(entry):
    """
    // Raise when a curriculum row belongs to an approved or archived version.
    // Legacy rows (version is null) remain editable for backward compatibility.
    """
    if entry.version_id is None:
        return
    if entry.version.status != STATUS_DRAFT:
        raise ValueError(
            'Approved curriculum versions are read-only. '
            'Create a new draft to change the subject matrix.'
        )
