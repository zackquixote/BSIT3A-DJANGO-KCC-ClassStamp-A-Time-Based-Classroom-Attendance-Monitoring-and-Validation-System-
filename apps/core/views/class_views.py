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
    AttendanceRecord,
    AuditEvent,
    Class,
    ClassSession,
    ClassSlot,
    Curriculum,
    Department,
    Enrollment,
    Profile,
    Program,
    Subject,
)


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

    # Build subject cascade data for the modal JS filter
    # curriculum_map: { program_id: { year_level: [subject_id, ...] } }
    curriculum_entries = (
        Curriculum.objects
        .select_related('subject', 'program')
        .filter(subject__is_active=True)
        .values('program_id', 'year_level', 'subject_id')
    )
    curriculum_map: dict = {}
    for entry in curriculum_entries:
        pid = str(entry['program_id'])
        yl  = str(entry['year_level'])
        sid = entry['subject_id']
        curriculum_map.setdefault(pid, {}).setdefault(yl, []).append(sid)

    subjects_json = json.dumps([
        {'id': s.id, 'code': s.code, 'name': s.name}
        for s in subjects
    ])
    departments_json = json.dumps([
        {'id': d.id, 'code': d.code, 'name': d.name}
        for d in departments
    ])
    programs_json = json.dumps([
        {'id': p.id, 'code': p.code, 'name': p.name,
         'dept_id': p.department_id, 'years_total': p.years_total}
        for p in programs
    ])
    curriculum_map_json = json.dumps(curriculum_map)

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
        'subjects_json': subjects_json,
        'departments_json': departments_json,
        'programs_json': programs_json,
        'curriculum_map_json': curriculum_map_json,
    })


# // ==============================================================================
# // ACTION: Save Class Section (Create / Edit)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_POST
def class_save(request):
    """
    // Creates or updates a Class section. Supports both AJAX and standard POST.
    """
    class_id = request.POST.get('class_id', '').strip()
    class_code = request.POST.get('class_code', '').strip().upper()
    subject_id = request.POST.get('subject_id', '').strip()
    teacher_profile_id = request.POST.get('teacher_profile_id', '').strip()
    academic_year_id = request.POST.get('academic_year_id', '').strip()
    capacity_str = request.POST.get('capacity', '').strip()
    grace_minutes_str = request.POST.get('grace_minutes', '10').strip()

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

    # Check for duplicate class_code within the same academic year
    conflict_qs = Class.objects.filter(academic_year=academic_year, class_code=class_code)
    if class_id:
        conflict_qs = conflict_qs.exclude(pk=class_id)
    if conflict_qs.exists():
        messages.error(request, f"A class with code '{class_code}' already exists for {academic_year.name}.")
        return redirect('class_list')

    if class_id:
        class_obj = get_object_or_404(Class, pk=class_id)
        old_val = f"{class_obj.class_code} ({class_obj.subject.code})"
        class_obj.class_code = class_code
        class_obj.subject = subject
        class_obj.teacher_profile = teacher
        class_obj.academic_year = academic_year
        class_obj.capacity = capacity
        class_obj.grace_minutes = grace_minutes
        class_obj.save()

        AuditEvent.objects.create(
            actor=request.user,
            action='UPDATE_CLASS',
            object_type='Class',
            object_id=str(class_obj.id),
            old_value=old_val,
            new_value=f"{class_code} ({subject.code})",
            reason=f"Updated class section {class_code}",
        )
        messages.success(request, f"Class '{class_code}' updated successfully.")
    else:
        class_obj = Class.objects.create(
            class_code=class_code,
            subject=subject,
            teacher_profile=teacher,
            academic_year=academic_year,
            capacity=capacity,
            grace_minutes=grace_minutes,
            is_active=True,
        )
        AuditEvent.objects.create(
            actor=request.user,
            action='CREATE_CLASS',
            object_type='Class',
            object_id=str(class_obj.id),
            new_value=f"{class_code} ({subject.code})",
            reason=f"Created class section {class_code}",
        )
        messages.success(request, f"Class '{class_code}' created successfully.")

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

    # Check for slot duplicate
    if ClassSlot.objects.filter(class_obj=class_obj, weekday=weekday, starts_at=starts_at).exists():
        return JsonResponse({'success': False, 'message': 'A schedule slot already exists for this day and time.'}, status=400)

    slot = ClassSlot.objects.create(
        class_obj=class_obj,
        weekday=weekday,
        starts_at=starts_at,
        ends_at=ends_at,
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
        }
    })


@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_POST
def class_slot_delete(request, slot_id):
    """
    // Removes a recurring weekly schedule slot from a class section.
    """
    slot = get_object_or_404(ClassSlot, pk=slot_id)
    class_code = slot.class_obj.class_code
    slot_desc = f"{slot.get_weekday_display()} {slot.starts_at}-{slot.ends_at}"
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

    # Available approved students not yet in this class (limit 100)
    available_students = (
        Profile.objects.filter(
            role=Profile.ROLE_STUDENT,
            approval_status=Profile.APPROVAL_APPROVED,
        )
        .exclude(id__in=enrolled_profile_ids)
        .select_related('user', 'program')
        .order_by('user__last_name', 'user__first_name')[:100]
    )

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

    # All active enrollments sorted by student last name, first name
    enrollments = (
        Enrollment.objects
        .filter(class_obj=class_obj, status=Enrollment.STATUS_ACTIVE)
        .select_related('student_profile__user', 'student_profile__program')
        .order_by('student_profile__user__last_name', 'student_profile__user__first_name')
    )

    # All class sessions held for this class
    sessions = (
        ClassSession.objects
        .filter(slot__class_obj=class_obj)
        .select_related('slot')
        .order_by('session_date', 'opened_at')
    )

    # All attendance records for these sessions
    records = (
        AttendanceRecord.objects
        .filter(session__in=sessions)
        .select_related('student_profile')
    )

    # Fast lookup dictionary: (student_profile_id, session_id) -> record
    record_map = {}
    for r in records:
        record_map[(r.student_profile_id, r.session_id)] = r

    session_list = []
    for s in sessions:
        session_list.append({
            'id': s.id,
            'date': s.session_date.strftime('%Y-%m-%d'),
            'display_date': s.session_date.strftime('%b %d'),
            'weekday': s.session_date.strftime('%a'),
            'room': s.slot.room if s.slot and s.slot.room else '—',
            'status': s.status,
        })

    student_rows = []
    total_attended_overall = 0
    total_possible_overall = 0

    for en in enrollments:
        profile = en.student_profile
        user = profile.user
        student_name = user.get_full_name() or user.username
        student_num = profile.student_number or '—'
        program_code = profile.program.code if profile.program else '—'

        present_cnt = 0
        late_cnt = 0
        absent_cnt = 0
        excused_cnt = 0
        cells = []

        for s in sessions:
            rec = record_map.get((profile.id, s.id))
            if rec:
                st = rec.status
                if st == AttendanceRecord.STATUS_PRESENT:
                    present_cnt += 1
                elif st == AttendanceRecord.STATUS_LATE:
                    late_cnt += 1
                elif st == AttendanceRecord.STATUS_ABSENT:
                    absent_cnt += 1
                elif st == AttendanceRecord.STATUS_EXCUSED:
                    excused_cnt += 1
                cells.append({
                    'status': st,
                    'method': rec.method,
                    'stamped_at': timezone.localtime(rec.stamped_at).strftime('%I:%M %p') if rec.stamped_at else '—',
                })
            else:
                cells.append({
                    'status': '—',
                    'method': None,
                    'stamped_at': '—',
                })

        attended = present_cnt + late_cnt
        total_sessions = len(sessions)
        rate = round((attended / total_sessions) * 100, 1) if total_sessions > 0 else 0

        total_attended_overall += attended
        total_possible_overall += total_sessions

        student_rows.append({
            'student_id': profile.id,
            'student_number': student_num,
            'name': student_name,
            'program': program_code,
            'cells': cells,
            'present': present_cnt,
            'late': late_cnt,
            'absent': absent_cnt,
            'excused': excused_cnt,
            'attended': attended,
            'rate': rate,
        })

    overall_rate = round((total_attended_overall / total_possible_overall) * 100, 1) if total_possible_overall > 0 else 0

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

