"""
# // ==============================================================================
# // KCC CLASSSTAMP - CLASS SECTION, SCHEDULE & ENROLLMENT CONTROLLERS
# // ==============================================================================
# // Subsystem: Classroom Operations & Timetable Management (RBAC: ADMIN ONLY)
# // Description: Provides administrative facilities to create academic class sections,
# //   link instructors and subjects, configure recurring weekly schedule slots,
# //   and manage student roster enlistment / enrollment.
# // References: docs/01_DEV_PLAN.md (Phase 2G) | apps/core/models/classroom.py
# // ==============================================================================
"""

import csv
import json
from datetime import time
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.core.decorators import role_required
from apps.core.models import (
    AcademicYear,
    AuditEvent,
    Class,
    ClassSlot,
    Curriculum,
    Department,
    Enrollment,
    Profile,
    Program,
    Subject,
)
from apps.core.services import (
    ClassAssignmentError,
    assign_class,
    detect_slot_conflicts,
    eligible_teachers_for,
    suggest_section_letter,
    validate_slot_times,
)
from apps.core.services.attendance_service import build_attendance_matrix


# // ==============================================================================
# // VIEW: Class Directory & Scheduling Masterlist (/classes/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def class_list(request):
    """
    // [Admin Controller] Masterlist of institutional classes and sections.
    """
    ay_filter = request.GET.get('ay', '').strip()
    subject_filter = request.GET.get('subject', '').strip()
    teacher_filter = request.GET.get('teacher', '').strip()
    search_q = request.GET.get('q', '').strip()
    per_page_str = request.GET.get('per_page', '20').strip()

    try:
        per_page = int(per_page_str)
        if per_page not in [10, 20, 50, 100]:
            per_page = 20
    except (ValueError, TypeError):
        per_page = 20

    active_ay = AcademicYear.objects.filter(is_active=True).first()

    classes_qs = (
        Class.objects
        .select_related('academic_year', 'subject', 'teacher_profile__user', 'teacher_profile__department')
        .prefetch_related('slots', 'enrollments')
        .annotate(
            active_enrolled=Count('enrollments', filter=Q(enrollments__status=Enrollment.STATUS_ACTIVE)),
            active_slots_count=Count('slots', filter=Q(slots__is_active=True)),
        )
        .order_by('-academic_year__starts_on', 'class_code')
    )

    if ay_filter:
        if ay_filter != 'ALL':
            classes_qs = classes_qs.filter(academic_year_id=ay_filter)
    elif active_ay:
        classes_qs = classes_qs.filter(academic_year=active_ay)
        ay_filter = str(active_ay.id)

    if subject_filter:
        classes_qs = classes_qs.filter(subject_id=subject_filter)

    if teacher_filter:
        classes_qs = classes_qs.filter(teacher_profile_id=teacher_filter)

    if search_q:
        classes_qs = classes_qs.filter(
            Q(class_code__icontains=search_q)
            | Q(subject__code__icontains=search_q)
            | Q(subject__name__icontains=search_q)
            | Q(teacher_profile__user__first_name__icontains=search_q)
            | Q(teacher_profile__user__last_name__icontains=search_q)
        )

    # Global KPI counts
    total_classes_count = Class.objects.count()
    active_classes_count = Class.objects.filter(is_active=True).count()
    total_slots_count = ClassSlot.objects.filter(is_active=True).count()
    total_enrolled_count = Enrollment.objects.filter(status=Enrollment.STATUS_ACTIVE).count()

    paginator = Paginator(classes_qs, per_page)
    page_number = request.GET.get('page', 1)
    classes_page = paginator.get_page(page_number)

    # Reference catalogs for modal select dropdowns
    academic_years = AcademicYear.objects.order_by('-starts_on')
    subjects = Subject.objects.filter(is_active=True).order_by('code')
    teachers = (
        Profile.objects.filter(role=Profile.ROLE_TEACHER, user__is_active=True)
        .select_related('user', 'department')
        .order_by('user__last_name', 'user__first_name')
    )
    departments = Department.objects.filter(is_active=True).order_by('name')
    programs = (
        Program.objects.filter(is_active=True)
        .select_related('department')
        .order_by('code')
    )

    return render(request, 'core/admin/classes.html', {
        'classes': classes_page,
        'ay_filter': ay_filter,
        'subject_filter': subject_filter,
        'teacher_filter': teacher_filter,
        'search_q': search_q,
        'per_page': str(per_page),
        'academic_years': academic_years,
        'subjects': subjects,
        'teachers': teachers,
        'departments': departments,
        'programs': programs,
        'active_ay': active_ay,
        'total_classes_count': total_classes_count,
        'active_classes_count': active_classes_count,
        'total_slots_count': total_slots_count,
        'total_enrolled_count': total_enrolled_count,
        'weekday_choices': ClassSlot.WEEKDAY_CHOICES,
    })


# // ==============================================================================
# // ACTION: Save Class Section (Edit only — creation lives in the Section Wizard)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_POST
def class_save(request):
    """
    // Updates an existing Class section. New sections are created exclusively
    // through the Section Builder wizard (class_wizard_save).
    """
    class_id = request.POST.get('class_id', '').strip()
    class_code = request.POST.get('class_code', '').strip().upper()
    subject_id = request.POST.get('subject_id', '').strip()
    teacher_profile_id = request.POST.get('teacher_profile_id', '').strip()
    academic_year_id = request.POST.get('academic_year_id', '').strip()
    capacity_str = request.POST.get('capacity', '').strip()
    grace_minutes_str = request.POST.get('grace_minutes', '10').strip()

    if not class_id:
        messages.error(request, 'New sections are created through the Section Wizard.')
        return redirect('class_wizard_setup')

    if not (class_code and subject_id and teacher_profile_id and academic_year_id):
        messages.error(request, 'Class Code, Subject, Teacher, and Academic Year are all required.')
        return redirect('class_list')

    try:
        capacity = int(capacity_str) if capacity_str else None
    except ValueError:
        capacity = None

    try:
        grace_minutes = int(grace_minutes_str) if grace_minutes_str else 10
    except ValueError:
        grace_minutes = 10

    subject = get_object_or_404(Subject, pk=subject_id)
    teacher = get_object_or_404(Profile, pk=teacher_profile_id, role=Profile.ROLE_TEACHER)
    academic_year = get_object_or_404(AcademicYear, pk=academic_year_id)

    class_obj = get_object_or_404(Class, pk=class_id)

    try:
        result = assign_class(
            actor=request.user,
            teacher_profile=teacher,
            academic_year=academic_year,
            subject=subject,
            class_code=class_code,
            grace_minutes=grace_minutes,
            capacity=capacity,
            class_obj=class_obj,
        )
    except ClassAssignmentError as exc:
        messages.error(request, str(exc))
        return redirect('class_list')

    if result['reassigned_from']:
        messages.success(
            request,
            f"Class '{class_code}' reassigned from {result['reassigned_from']} successfully.",
        )
    else:
        messages.success(request, f"Class '{class_code}' updated successfully.")

    return redirect('class_list')


# // ==============================================================================
# // ACTION: Toggle Class Active State
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_POST
def class_toggle(request, pk):
    """
    // Toggles the is_active status of a class.
    """
    class_obj = get_object_or_404(Class, pk=pk)
    class_obj.is_active = not class_obj.is_active
    class_obj.save(update_fields=['is_active', 'updated_at'])

    status_str = "activated" if class_obj.is_active else "deactivated"
    AuditEvent.objects.create(
        actor=request.user,
        action='TOGGLE_CLASS',
        object_type='Class',
        object_id=str(class_obj.id),
        new_value=str(class_obj.is_active),
        reason=f"Class {class_obj.class_code} {status_str}",
    )
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        from django.http import JsonResponse
        return JsonResponse({'ok': True, 'is_active': class_obj.is_active, 'status_str': status_str})
    messages.success(request, f"Class '{class_obj.class_code}' has been {status_str}.")
    return redirect('class_list')


# // ==============================================================================
# // ACTION: Schedule Slot Management (Add / Delete)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_POST
def class_slot_save(request, class_id):
    """
    // Adds a recurring weekly timetable slot to a class section.
    """
    class_obj = get_object_or_404(Class, pk=class_id)
    weekday_str = request.POST.get('weekday', '').strip()
    starts_at = request.POST.get('starts_at', '').strip()
    ends_at = request.POST.get('ends_at', '').strip()
    room = request.POST.get('room', '').strip()

    if not (weekday_str and starts_at and ends_at):
        return JsonResponse({'success': False, 'message': 'Weekday, Start Time, and End Time are required.'}, status=400)

    try:
        weekday = int(weekday_str)
        if weekday not in range(7):
            raise ValueError()
    except ValueError:
        return JsonResponse({'success': False, 'message': 'Invalid weekday selected.'}, status=400)

    try:
        starts_t = time.fromisoformat(starts_at)
        ends_t = time.fromisoformat(ends_at)
    except ValueError:
        return JsonResponse({'success': False, 'message': 'Times must be in HH:MM format.'}, status=400)

    try:
        validate_slot_times(starts_t, ends_t)
    except ValueError as exc:
        return JsonResponse({'success': False, 'message': str(exc)}, status=400)

    # Check for slot duplicate
    if ClassSlot.objects.filter(class_obj=class_obj, weekday=weekday, starts_at=starts_t).exists():
        return JsonResponse({'success': False, 'message': 'A schedule slot already exists for this day and time.'}, status=400)

    # Cross-class timetable conflicts (A-19): teacher clashes hard-block,
    # room clashes only warn (rooms are free text, often 'TBA').
    conflicts = detect_slot_conflicts(
        teacher_profile_id=class_obj.teacher_profile_id,
        weekday=weekday,
        starts_at=starts_t,
        ends_at=ends_t,
        room=room,
    )
    teacher_conflicts = [c for c in conflicts if c['type'] == 'teacher']
    if teacher_conflicts:
        c = teacher_conflicts[0]
        return JsonResponse({
            'success': False,
            'message': (
                f"Schedule conflict: the teacher is already teaching "
                f"{c['class_code']} {ClassSlot.WEEKDAY_CHOICES[c['weekday']][1]} "
                f"{c['starts_at']}-{c['ends_at']}."
            ),
        }, status=400)

    room_warnings = [
        f"{c['class_code']} {ClassSlot.WEEKDAY_CHOICES[c['weekday']][1]} "
        f"{c['starts_at']}-{c['ends_at']}"
        for c in conflicts if c['type'] == 'room'
    ]

    slot = ClassSlot.objects.create(
        class_obj=class_obj,
        weekday=weekday,
        starts_at=starts_t,
        ends_at=ends_t,
        room=room or 'TBA',
        is_active=True,
    )

    AuditEvent.objects.create(
        actor=request.user,
        action='ADD_CLASS_SLOT',
        object_type='ClassSlot',
        object_id=str(slot.id),
        reason=f"Added slot for {class_obj.class_code}: {slot.get_weekday_display()} {starts_at}-{ends_at}",
    )

    return JsonResponse({
        'success': True,
        'slot': {
            'id': slot.id,
            'weekday': slot.get_weekday_display(),
            'starts_at': str(slot.starts_at)[:5],
            'ends_at': str(slot.ends_at)[:5],
            'room': slot.room,
        },
        'warnings': room_warnings,
    })


@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_POST
def class_slot_delete(request, slot_id):
    """
    // Removes or safely retires a recurring weekly schedule slot.
    // Slots with historical sessions are deactivated instead of hard-deleted
    // because ClassSession.slot is protected by a RESTRICT foreign key.
    """
    slot = get_object_or_404(ClassSlot, pk=slot_id)
    class_code = slot.class_obj.class_code
    slot_desc = f"{slot.get_weekday_display()} {slot.starts_at}-{slot.ends_at}"

    if slot.sessions.exists():
        slot.is_active = False
        slot.save(update_fields=['is_active'])
        AuditEvent.objects.create(
            actor=request.user,
            action='DEACTIVATE_CLASS_SLOT',
            object_type='ClassSlot',
            object_id=str(slot_id),
            reason=f"Retired schedule slot {slot_desc} from {class_code} while preserving session history",
        )
        return JsonResponse({
            'success': True,
            'archived': True,
            'message': 'This slot has session history, so it was retired instead of deleted.',
        })

    slot.delete()
    AuditEvent.objects.create(
        actor=request.user,
        action='DELETE_CLASS_SLOT',
        object_type='ClassSlot',
        object_id=str(slot_id),
        reason=f"Removed schedule slot {slot_desc} from {class_code}",
    )

    return JsonResponse({'success': True})


# // ==============================================================================
# // ACTION: Student Roster & Enlistment (Get, Enroll, Remove)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_GET
def class_roster_get(request, class_id):
    """
    // Returns active enrolled students for a class and list of eligible students to enroll.
    """
    class_obj = get_object_or_404(Class, pk=class_id)
    enrollments = (
        Enrollment.objects.filter(class_obj=class_obj, status=Enrollment.STATUS_ACTIVE)
        .select_related('student_profile__user', 'student_profile__program')
        .order_by('student_profile__user__last_name', 'student_profile__user__first_name')
    )

    enrolled_data = []
    enrolled_profile_ids = []
    for en in enrollments:
        enrolled_profile_ids.append(en.student_profile_id)
        enrolled_data.append({
            'enrollment_id': en.id,
            'student_id': en.student_profile.student_number or '—',
            'student_name': en.student_profile.user.get_full_name() or en.student_profile.user.username,
            'program': en.student_profile.program.code if en.student_profile.program else '—',
            'enrolled_at': timezone.localtime(en.created_at).strftime('%b %d, %Y') if en.created_at else '—',
        })

    # Available approved students not yet in this class (limit 100).
    # Candidate scope defaults to the section's own program/year level so the
    # enlistment dropdown shows relevant students first; explicit query params
    # widen or narrow that scope.
    prog_filter = request.GET.get('program_id', '').strip()
    if not prog_filter and class_obj.program_id:
        prog_filter = str(class_obj.program_id)
    year_filter = request.GET.get('year_level', '').strip()
    if not year_filter and class_obj.year_level:
        year_filter = str(class_obj.year_level)

    available_qs = (
        Profile.objects.filter(
            role=Profile.ROLE_STUDENT,
            approval_status=Profile.APPROVAL_APPROVED,
        )
        .exclude(id__in=enrolled_profile_ids)
        .select_related('user', 'program')
    )
    if prog_filter:
        available_qs = available_qs.filter(program_id=prog_filter)
    if year_filter:
        try:
            available_qs = available_qs.filter(year_level=int(year_filter))
        except ValueError:
            pass
    available_students = available_qs.order_by('user__last_name', 'user__first_name')[:100]

    available_data = []
    for s in available_students:
        available_data.append({
            'profile_id': s.id,
            'student_id': s.student_number or '—',
            'student_name': s.user.get_full_name() or s.user.username,
            'program': s.program.code if s.program else '—',
        })

    return JsonResponse({
        'success': True,
        'class_code': class_obj.class_code,
        'capacity': class_obj.capacity,
        'enrolled_count': len(enrolled_data),
        'remaining_capacity': (
            None if not class_obj.capacity
            else max(class_obj.capacity - len(enrolled_data), 0)
        ),
        'class_program_id': class_obj.program_id,
        'class_program_code': class_obj.program.code if class_obj.program else None,
        'class_year_level': class_obj.year_level,
        'enrolled': enrolled_data,
        'available': available_data,
    })


@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_POST
def class_roster_enroll(request, class_id):
    """
    // Enrolls an approved student profile into a class section.
    """
    class_obj = get_object_or_404(Class, pk=class_id)
    profile_id = request.POST.get('profile_id', '').strip()

    if not profile_id:
        return JsonResponse({'success': False, 'message': 'Student profile ID is required.'}, status=400)

    student = get_object_or_404(
        Profile,
        pk=profile_id,
        role=Profile.ROLE_STUDENT,
        approval_status=Profile.APPROVAL_APPROVED,
    )

    # Check capacity limit
    current_enrolled = Enrollment.objects.filter(class_obj=class_obj, status=Enrollment.STATUS_ACTIVE).count()
    if class_obj.capacity and current_enrolled >= class_obj.capacity:
        return JsonResponse({'success': False, 'message': f"Class has reached its maximum capacity of {class_obj.capacity} students."}, status=400)

    # Check if existing enrollment
    enrollment, created = Enrollment.objects.get_or_create(
        class_obj=class_obj,
        student_profile=student,
        defaults={
            'status': Enrollment.STATUS_ACTIVE,
            'approved_by': request.user,
            'approved_at': timezone.now(),
        }
    )

    if not created and enrollment.status != Enrollment.STATUS_ACTIVE:
        enrollment.status = Enrollment.STATUS_ACTIVE
        enrollment.approved_by = request.user
        enrollment.approved_at = timezone.now()
        enrollment.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])

    AuditEvent.objects.create(
        actor=request.user,
        action='ENROLL_STUDENT',
        object_type='Enrollment',
        object_id=str(enrollment.id),
        reason=f"Enrolled student {student.student_number} into {class_obj.class_code}",
    )

    return JsonResponse({
        'success': True,
        'student': {
            'enrollment_id': enrollment.id,
            'student_id': student.student_number or '—',
            'student_name': student.user.get_full_name() or student.user.username,
            'program': student.program.code if student.program else '—',
            'enrolled_at': timezone.localtime(timezone.now()).strftime('%b %d, %Y'),
        }
    })


@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_POST
def class_roster_enroll_batch(request, class_id):
    """
    // Enlists every approved student matching the section's program/year level
    // (or an explicit program_id/year_level override) who is not already active
    // in this class, up to the section's capacity. One audit event per student.
    """
    class_obj = get_object_or_404(Class, pk=class_id)

    prog_id = request.POST.get('program_id', '').strip()
    if not prog_id and class_obj.program_id:
        prog_id = str(class_obj.program_id)
    year_level = request.POST.get('year_level', '').strip()
    if not year_level and class_obj.year_level:
        year_level = str(class_obj.year_level)

    candidates = Profile.objects.filter(
        role=Profile.ROLE_STUDENT,
        approval_status=Profile.APPROVAL_APPROVED,
    ).select_related('user', 'program')
    if prog_id:
        candidates = candidates.filter(program_id=prog_id)
    if year_level:
        try:
            candidates = candidates.filter(year_level=int(year_level))
        except ValueError:
            return JsonResponse({'success': False, 'message': 'Invalid year level.'}, status=400)

    active_ids = Enrollment.objects.filter(
        class_obj=class_obj, status=Enrollment.STATUS_ACTIVE,
    ).values_list('student_profile_id', flat=True)
    candidates = candidates.exclude(id__in=active_ids).order_by('user__last_name', 'user__first_name')

    enrolled = 0
    skipped_full = False
    with transaction.atomic():
        for student in candidates.iterator():
            current_enrolled = Enrollment.objects.filter(
                class_obj=class_obj, status=Enrollment.STATUS_ACTIVE,
            ).count()
            if class_obj.capacity and current_enrolled >= class_obj.capacity:
                skipped_full = True
                break

            enrollment, created = Enrollment.objects.get_or_create(
                class_obj=class_obj,
                student_profile=student,
                defaults={
                    'status': Enrollment.STATUS_ACTIVE,
                    'approved_by': request.user,
                    'approved_at': timezone.now(),
                },
            )
            if not created and enrollment.status != Enrollment.STATUS_ACTIVE:
                enrollment.status = Enrollment.STATUS_ACTIVE
                enrollment.approved_by = request.user
                enrollment.approved_at = timezone.now()
                enrollment.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])

            AuditEvent.objects.create(
                actor=request.user,
                action='ENROLL_STUDENT',
                object_type='Enrollment',
                object_id=str(enrollment.id),
                reason=(
                    f"Batch-enlisted student {student.student_number} into "
                    f"{class_obj.class_code}"
                ),
            )
            enrolled += 1

    message = f'Enlisted {enrolled} student(s) into {class_obj.class_code}.'
    if skipped_full:
        message += f' Stopped early: the section reached its capacity of {class_obj.capacity}.'
    elif class_obj.capacity and Enrollment.objects.filter(
        class_obj=class_obj, status=Enrollment.STATUS_ACTIVE,
    ).count() >= class_obj.capacity:
        message += f' The section is now at its capacity of {class_obj.capacity}.'

    return JsonResponse({'success': True, 'enrolled_count': enrolled, 'message': message})


@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_POST
def class_roster_remove(request, enrollment_id):
    """
    // Withdraws or removes a student enrollment from a class section.
    """
    enrollment = get_object_or_404(Enrollment, pk=enrollment_id)
    class_code = enrollment.class_obj.class_code
    student_num = enrollment.student_profile.student_number

    enrollment.status = Enrollment.STATUS_WITHDRAWN
    enrollment.save(update_fields=['status', 'updated_at'])

    AuditEvent.objects.create(
        actor=request.user,
        action='WITHDRAW_ENROLLMENT',
        object_type='Enrollment',
        object_id=str(enrollment.id),
        reason=f"Withdrew student {student_num} from {class_code}",
    )

    return JsonResponse({'success': True})


# // ==============================================================================
# // A-19 SECTION BUILDER WIZARD: Options Feed (GET) & Atomic Save (POST)
# // ==============================================================================
def _parse_wizard_slots(slots_json):
    """
    // Parses and validates the wizard's slot JSON array, including internal
    // duplicate/overlap detection. Returns (parsed_slots, None) or (None, error).
    """
    try:
        slots = json.loads(slots_json)
        if not isinstance(slots, list):
            raise ValueError
    except ValueError:
        return None, 'Slots must be a JSON array.'

    parsed_slots = []
    for entry in slots:
        if not isinstance(entry, dict):
            return None, 'Each slot must be an object.'
        try:
            weekday = int(entry.get('weekday'))
            if weekday not in range(7):
                raise ValueError
            starts_t = time.fromisoformat(str(entry.get('starts_at') or '').strip())
            ends_t = time.fromisoformat(str(entry.get('ends_at') or '').strip())
            validate_slot_times(starts_t, ends_t)
        except ValueError:
            return None, 'Each slot needs a weekday (0-6) and valid HH:MM start/end times.'
        parsed_slots.append({
            'weekday': weekday,
            'starts_at': starts_t,
            'ends_at': ends_t,
            'room': str(entry.get('room') or '').strip(),
        })

    for i, a in enumerate(parsed_slots):
        for b in parsed_slots[i + 1:]:
            if (
                a['weekday'] == b['weekday']
                and a['starts_at'] < b['ends_at']
                and b['starts_at'] < a['ends_at']
            ):
                return None, 'Two or more submitted schedule slots overlap. Remove the duplicate window and try again.'
    return parsed_slots, None


def _collect_wizard_conflicts(teacher_profile_id, parsed_slots):
    """
    // Per-slot timetable conflicts for the proposed teacher:
    // [{'index', 'teacher': [labels], 'room': [labels]}, ...]
    """
    results = []
    for index, slot in enumerate(parsed_slots):
        conflicts = detect_slot_conflicts(
            teacher_profile_id=teacher_profile_id,
            weekday=slot['weekday'],
            starts_at=slot['starts_at'],
            ends_at=slot['ends_at'],
            room=slot['room'],
        )
        teacher_labels = []
        room_labels = []
        for c in conflicts:
            label = (
                f"{c['class_code']} {ClassSlot.WEEKDAY_CHOICES[c['weekday']][1]} "
                f"{c['starts_at']}-{c['ends_at']}"
            )
            if c['type'] == 'teacher':
                teacher_labels.append(label)
            else:
                room_labels.append(label)
        results.append({'index': index, 'teacher': teacher_labels, 'room': room_labels})
    return results


def _wizard_slot_minutes(parsed_slots):
    return sum(
        (s['ends_at'].hour * 60 + s['ends_at'].minute)
        - (s['starts_at'].hour * 60 + s['starts_at'].minute)
        for s in parsed_slots
    )


def _wizard_hours_label(minutes):
    h, m = divmod(minutes, 60)
    return f'{h}h' if not m else f'{h}h {m}m'


@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_GET
def class_wizard_options(request):
    """
    // Feeds the Section Builder wizard: curriculum subjects for the chosen
    // program/year/semester, eligible teachers ranked by load, and a suggested
    // next-free section code.
    """
    program_id = request.GET.get('program_id', '').strip()
    year_level_str = request.GET.get('year_level', '').strip()
    semester_str = request.GET.get('semester', '').strip()
    ay_id_str = request.GET.get('ay_id', '').strip()

    try:
        program_id_int = int(program_id)
        year_level = int(year_level_str)
        semester = int(semester_str)
    except ValueError:
        return JsonResponse({
            'success': False,
            'message': 'Program, year level, and semester are required integers.',
        }, status=400)

    if semester not in dict(Curriculum.SEMESTER_CHOICES):
        return JsonResponse({'success': False, 'message': 'Invalid semester selected.'}, status=400)

    program = get_object_or_404(Program, pk=program_id_int, is_active=True)

    if ay_id_str:
        try:
            ay_id = int(ay_id_str)
        except ValueError:
            return JsonResponse({'success': False, 'message': 'Invalid academic year.'}, status=400)
        academic_year = get_object_or_404(AcademicYear, pk=ay_id)
    else:
        academic_year = AcademicYear.objects.filter(is_active=True).first()
        if academic_year is None:
            return JsonResponse({
                'success': False,
                'message': 'No active academic year is configured. Please create one first.',
            }, status=400)

    subjects_data = [
        {
            'id': entry.subject_id,
            'code': entry.subject.code,
            'name': entry.subject.name,
            'units': entry.subject.units,
        }
        for entry in (
            Curriculum.objects
            .filter(
                program=program,
                year_level=year_level,
                semester=semester,
                subject__is_active=True,
            )
            .select_related('subject')
            .order_by('subject__code')
        )
    ]

    try:
        teachers = eligible_teachers_for(program)
        suggested_code = suggest_section_letter(
            academic_year=academic_year,
            program=program,
            year_level=year_level,
        )
    except ValueError as exc:
        return JsonResponse({'success': False, 'message': str(exc)}, status=400)

    return JsonResponse({
        'success': True,
        'academic_year': {'id': academic_year.id, 'name': academic_year.name},
        'subjects': subjects_data,
        'teachers': teachers,
        'suggested_code': suggested_code,
    })


@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_POST
def class_wizard_save(request):
    """
    // Creates a class section plus its weekly slots in one atomic transaction.
    // Teacher timetable clashes hard-block; room clashes return as warnings.
    """
    program_id = request.POST.get('program_id', '').strip()
    year_level_str = request.POST.get('year_level', '').strip()
    subject_id = request.POST.get('subject_id', '').strip()
    teacher_profile_id = request.POST.get('teacher_profile_id', '').strip()
    ay_id = request.POST.get('ay_id', '').strip()
    class_code = request.POST.get('class_code', '').strip().upper()
    capacity_str = request.POST.get('capacity', '').strip()
    grace_minutes_str = request.POST.get('grace_minutes', '10').strip()
    slots_json = request.POST.get('slots', '[]')

    if not (program_id and year_level_str and subject_id and teacher_profile_id and class_code):
        return JsonResponse({
            'success': False,
            'message': 'Program, year level, subject, teacher, and section code are required.',
        }, status=400)

    try:
        program_id_int = int(program_id)
        year_level = int(year_level_str)
        subject_id_int = int(subject_id)
        teacher_profile_id_int = int(teacher_profile_id)
        ay_id_int = int(ay_id)
        capacity = int(capacity_str) if capacity_str else None
        grace_minutes = int(grace_minutes_str) if grace_minutes_str else 10
    except ValueError:
        return JsonResponse({'success': False, 'message': 'Invalid numeric value provided.'}, status=400)

    if year_level < 1 or year_level > 8:
        return JsonResponse({'success': False, 'message': 'Year level must be between 1 and 8.'}, status=400)
    if capacity is not None and capacity < 1:
        capacity = None

    program = get_object_or_404(Program, pk=program_id_int, is_active=True)
    subject = get_object_or_404(Subject, pk=subject_id_int, is_active=True)
    teacher = get_object_or_404(Profile, pk=teacher_profile_id_int, role=Profile.ROLE_TEACHER)
    academic_year = get_object_or_404(AcademicYear, pk=ay_id_int)

    parsed_slots, parse_error = _parse_wizard_slots(slots_json)
    if parse_error:
        return JsonResponse({'success': False, 'message': parse_error}, status=400)

    # Total scheduled hours must equal the subject's credit units
    # (institutional rule: 1 unit = 1 class hour per week).
    total_minutes = _wizard_slot_minutes(parsed_slots)
    required_minutes = subject.units * 60
    if total_minutes != required_minutes:
        return JsonResponse({
            'success': False,
            'message': (
                f"Schedule hours don't match subject units: {subject.code} is "
                f"{subject.units} unit(s) = {_wizard_hours_label(required_minutes)} per week, "
                f"but the submitted slots total {_wizard_hours_label(total_minutes)}."
            ),
        }, status=400)

    slot_conflicts = _collect_wizard_conflicts(teacher.id, parsed_slots)
    teacher_conflicts = [label for sc in slot_conflicts for label in sc['teacher']]
    room_warnings = [label for sc in slot_conflicts for label in sc['room']]

    if teacher_conflicts:
        return JsonResponse({
            'success': False,
            'message': f"Schedule conflict: the teacher is already teaching {teacher_conflicts[0]}.",
        }, status=400)

    try:
        with transaction.atomic():
            result = assign_class(
                actor=request.user,
                teacher_profile=teacher,
                academic_year=academic_year,
                subject=subject,
                class_code=class_code,
                grace_minutes=grace_minutes,
                capacity=capacity,
                program=program,
                year_level=year_level,
            )
            class_obj = result['class']

            created_slots = []
            for slot in parsed_slots:
                created = ClassSlot.objects.create(
                    class_obj=class_obj,
                    weekday=slot['weekday'],
                    starts_at=slot['starts_at'],
                    ends_at=slot['ends_at'],
                    room=slot['room'] or 'TBA',
                    is_active=True,
                )
                AuditEvent.objects.create(
                    actor=request.user,
                    action='ADD_CLASS_SLOT',
                    object_type='ClassSlot',
                    object_id=str(created.id),
                    reason=(
                        f"Added slot for {class_code}: {created.get_weekday_display()} "
                        f"{slot['starts_at']}-{slot['ends_at']}"
                    ),
                )
                created_slots.append({
                    'id': created.id,
                    'weekday': created.get_weekday_display(),
                    'starts_at': str(created.starts_at)[:5],
                    'ends_at': str(created.ends_at)[:5],
                    'room': created.room,
                })
    except ClassAssignmentError as exc:
        return JsonResponse({'success': False, 'message': str(exc)}, status=400)

    return JsonResponse({
        'success': True,
        'class_id': class_obj.id,
        'class_code': class_obj.class_code,
        'slots': created_slots,
        'warnings': room_warnings,
    })


@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_POST
def class_wizard_slots_check(request):
    """
    // Dry-run timetable conflict scan for the wizard's schedule step.
    // Nothing is saved; returns per-slot teacher clashes and room warnings.
    """
    teacher_profile_id = request.POST.get('teacher_profile_id', '').strip()
    try:
        teacher_profile_id_int = int(teacher_profile_id)
    except ValueError:
        return JsonResponse({'success': False, 'message': 'Teacher is required.'}, status=400)
    teacher = get_object_or_404(Profile, pk=teacher_profile_id_int, role=Profile.ROLE_TEACHER)

    parsed_slots, parse_error = _parse_wizard_slots(request.POST.get('slots', '[]'))
    if parse_error:
        return JsonResponse({'success': False, 'message': parse_error}, status=400)

    return JsonResponse({
        'success': True,
        'slots': _collect_wizard_conflicts(teacher.id, parsed_slots),
        'total_minutes': _wizard_slot_minutes(parsed_slots),
    })


@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_GET
def class_wizard_setup(request):
    """
    // Renders the 5-step Section Builder wizard page (A-19 Phase 4).
    """
    programs = (
        Program.objects.filter(is_active=True)
        .select_related('department')
        .order_by('code')
    )
    academic_years = AcademicYear.objects.order_by('-starts_on')
    active_ay = AcademicYear.objects.filter(is_active=True).first()
    programs_json = json.dumps([
        {'id': p.id, 'code': p.code, 'name': p.name, 'years_total': p.years_total}
        for p in programs
    ])
    return render(request, 'core/admin/class_wizard.html', {
        'programs': programs,
        'programs_json': programs_json,
        'academic_years': academic_years,
        'active_ay': active_ay,
        'weekday_choices': ClassSlot.WEEKDAY_CHOICES,
        'semester_choices': Curriculum.SEMESTER_CHOICES,
    })


# // ==============================================================================
# // VIEW: Per-Class Section Attendance Matrix Sheet (/classes/<int:class_id>/matrix/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def class_attendance_matrix(request, class_id):
    """
    // [Admin Controller] Attendance Matrix Sheet
    // Returns full 2D grid matrix (Enrolled Students x Session Dates) with
    // individual statuses, summary tallies, and attendance compliance rates.
    // Supports CSV export via ?format=csv.
    """
    class_obj = get_object_or_404(
        Class.objects.select_related('subject', 'teacher_profile__user', 'academic_year'),
        id=class_id,
    )

    matrix = build_attendance_matrix(class_obj)
    session_list = matrix['session_list']
    student_rows = matrix['student_rows']
    overall_rate = matrix['overall_rate']

    # CSV Export format
    if request.GET.get('format') == 'csv':
        response = HttpResponse(content_type='text/csv')
        filename = f"attendance_matrix_{class_obj.class_code}_{timezone.localdate().strftime('%Y%m%d')}.csv"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)
        headers = ['Student ID', 'Student Name', 'Program']
        for s in session_list:
            headers.append(f"{s['display_date']} ({s['weekday']})")
        headers.extend(['Present', 'Late', 'Absent', 'Excused', 'Attendance Rate %'])
        writer.writerow(headers)

        for row in student_rows:
            csv_row = [row['student_number'], row['name'], row['program']]
            for c in row['cells']:
                csv_row.append(c['status'])
            csv_row.extend([row['present'], row['late'], row['absent'], row['excused'], f"{row['rate']}%"])
            writer.writerow(csv_row)

        return response

    return JsonResponse({
        'success': True,
        'class_code': class_obj.class_code,
        'subject_code': class_obj.subject.code,
        'subject_name': class_obj.subject.name,
        'teacher_name': class_obj.teacher_profile.user.get_full_name() if class_obj.teacher_profile else '—',
        'academic_year': class_obj.academic_year.name if class_obj.academic_year else '—',
        'sessions': session_list,
        'students': student_rows,
        'summary': {
            'total_students': len(student_rows),
            'total_sessions': len(session_list),
            'overall_rate': overall_rate,
        },
    })

