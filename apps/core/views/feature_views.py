import json

from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch, Q
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.core.decorators import role_required
from apps.core.models import (
    AcademicEvent,
    AcademicYear,
    AttendanceRecord,
    Class,
    ClassSession,
    ClassSlot,
    Department,
    Enrollment,
    ExcuseSlip,
    Profile,
    Program,
    RoomVerification,
)
from apps.core.services.export_service import SafeCsvWriter
from apps.core.services.permission_service import PermissionService
from apps.core.services.push_notification_service import PushNotificationService


def _resolve_academic_year(raw_value):
    """Return (year, error). A blank value selects the active academic year."""
    raw_value = (raw_value or '').strip()
    if not raw_value:
        return AcademicYear.objects.filter(is_active=True).first(), None
    if not raw_value.isdigit():
        return None, HttpResponseBadRequest('Invalid academic year.')
    year = AcademicYear.objects.filter(pk=int(raw_value)).first()
    if year is None:
        return None, HttpResponseBadRequest('Invalid academic year.')
    return year, None


@login_required(login_url='login')
@role_required(Profile.ROLE_TEACHER)
def teacher_timetable(request):
    active_year = AcademicYear.objects.filter(is_active=True).first()
    classes = list(
        Class.objects.filter(
            teacher_profile__user=request.user,
            academic_year=active_year,
            is_active=True,
        )
        .select_related('subject')
        .prefetch_related(
            Prefetch(
                'slots',
                queryset=ClassSlot.objects.filter(is_active=True).order_by(
                    'weekday', 'starts_at'
                ),
                to_attr='active_slots',
            ),
            Prefetch(
                'enrollments',
                queryset=Enrollment.objects.filter(status=Enrollment.STATUS_ACTIVE),
                to_attr='active_enrollments',
            ),
        )
    )

    rows = []
    for class_obj in classes:
        for slot in class_obj.active_slots:
            rows.append({
                'weekday': slot.get_weekday_display(),
                'weekday_value': slot.weekday,
                'starts_at': slot.starts_at,
                'ends_at': slot.ends_at,
                'room': slot.room or 'TBA',
                'class_code': class_obj.class_code,
                'subject': class_obj.subject.name,
                'students': len(class_obj.active_enrollments),
            })
    rows.sort(key=lambda row: (row['weekday_value'], row['starts_at']))
    weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    day_groups = []
    for weekday_value in range(7):
        day_rows = [row for row in rows if row['weekday_value'] == weekday_value]
        if day_rows:
            day_groups.append({
                'name': weekday_names[weekday_value],
                'slots': day_rows,
            })
    return render(request, 'core/teacher/timetable.html', {
        'academic_year': active_year,
        'schedule': rows,
        'day_groups': day_groups,
        'total_slots': len(rows),
        'total_classes': len(classes),
        'total_hours': sum(
            (
                row['ends_at'].hour + row['ends_at'].minute / 60
                - row['starts_at'].hour - row['starts_at'].minute / 60
            )
            for row in rows
        ),
    })


@login_required(login_url='login')
@role_required(Profile.ROLE_TEACHER)
@require_GET
def teacher_timetable_export(request):
    active_year = AcademicYear.objects.filter(is_active=True).first()
    slots = ClassSlot.objects.filter(
        class_obj__teacher_profile__user=request.user,
        class_obj__academic_year=active_year,
        class_obj__is_active=True,
        is_active=True,
    ).select_related('class_obj', 'class_obj__subject').order_by('weekday', 'starts_at')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="classstamp-teacher-timetable.csv"'
    writer = SafeCsvWriter(response)
    writer.writerow(['Day', 'Start', 'End', 'Class', 'Subject', 'Room'])
    for slot in slots:
        writer.writerow([
            slot.get_weekday_display(),
            slot.starts_at.strftime('%I:%M %p'),
            slot.ends_at.strftime('%I:%M %p'),
            slot.class_obj.class_code,
            slot.class_obj.subject.name,
            slot.room or 'TBA',
        ])
    return response


@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_GET
def attendance_period_report(request):
    academic_year, error = _resolve_academic_year(request.GET.get('academic_year'))
    if error:
        return error

    dept_id = request.GET.get('department', '').strip()
    prog_id = request.GET.get('program', '').strip()
    year_level = request.GET.get('year_level', '').strip()

    records = AttendanceRecord.objects.select_related(
        'student_profile__user',
        'student_profile__program__department',
        'session__slot__class_obj__subject',
        'session__slot__class_obj__program__department',
    ).filter(session__slot__class_obj__academic_year=academic_year)

    if dept_id.isdigit():
        d_id = int(dept_id)
        records = records.filter(
            Q(session__slot__class_obj__program__department_id=d_id)
            | Q(student_profile__program__department_id=d_id)
        )

    if prog_id.isdigit():
        p_id = int(prog_id)
        records = records.filter(
            Q(session__slot__class_obj__program_id=p_id)
            | Q(student_profile__program_id=p_id)
        )

    if year_level.isdigit():
        yr = int(year_level)
        records = records.filter(
            Q(session__slot__class_obj__year_level=yr)
            | Q(student_profile__year_level=yr)
        )

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="classstamp-period-report.csv"'
    writer = SafeCsvWriter(response)
    writer.writerow([
        'Date', 'Academic Year', 'Department', 'Program', 'Year Level', 'Class', 'Subject', 'Student Number',
        'Student Name', 'Status', 'Method', 'Late Minutes',
    ])
    for record in records.order_by('session__session_date', 'student_profile__student_number'):
        cls_obj = record.session.slot.class_obj
        student = record.student_profile
        prog = cls_obj.program or (student.program if student else None)
        dept = (prog.department if prog else None) or (student.program.department if student and student.program else None)
        yr = cls_obj.year_level or (student.year_level if student else '')
        writer.writerow([
            record.session.session_date,
            academic_year.name if academic_year else '',
            dept.code if dept else '',
            prog.code if prog else '',
            yr,
            cls_obj.class_code,
            cls_obj.subject.name,
            student.student_number if student else '',
            student.user.get_full_name() if student else '',
            record.status,
            record.method,
            record.late_minutes,
        ])
    return response


@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_GET
def attendance_period_report_page(request):
    academic_years = AcademicYear.objects.order_by('-starts_on')
    selected_year, error = _resolve_academic_year(request.GET.get('academic_year'))
    if error:
        return error

    departments = Department.objects.filter(is_active=True).order_by('name')
    programs = Program.objects.filter(is_active=True).select_related('department').order_by('code')

    dept_id = request.GET.get('department', '').strip()
    prog_id = request.GET.get('program', '').strip()
    year_level = request.GET.get('year_level', '').strip()

    records_qs = AttendanceRecord.objects.filter(
        session__slot__class_obj__academic_year=selected_year
    ) if selected_year else AttendanceRecord.objects.none()

    if dept_id.isdigit():
        d_id = int(dept_id)
        records_qs = records_qs.filter(
            Q(session__slot__class_obj__program__department_id=d_id)
            | Q(student_profile__program__department_id=d_id)
        )

    if prog_id.isdigit():
        p_id = int(prog_id)
        records_qs = records_qs.filter(
            Q(session__slot__class_obj__program_id=p_id)
            | Q(student_profile__program_id=p_id)
        )

    if year_level.isdigit():
        yr = int(year_level)
        records_qs = records_qs.filter(
            Q(session__slot__class_obj__year_level=yr)
            | Q(student_profile__year_level=yr)
        )

    record_count = records_qs.count()

    preview_records = (
        records_qs
        .select_related(
            'student_profile__user',
            'student_profile__program',
            'session__slot__class_obj__subject',
            'session__slot__class_obj__program',
        )
        .order_by('-session__session_date', 'student_profile__student_number')[:10]
    )

    return render(request, 'core/admin/attendance_period_report.html', {
        'academic_years': academic_years,
        'selected_academic_year': selected_year,
        'departments': departments,
        'programs': programs,
        'selected_dept': dept_id,
        'selected_prog': prog_id,
        'selected_year_level': year_level,
        'record_count': record_count,
        'preview_records': preview_records,
    })


@login_required(login_url='login')
@role_required(Profile.ROLE_TEACHER, Profile.ROLE_ADMIN)
@require_POST
def verify_classroom(request, session_id):
    session = get_object_or_404(ClassSession.objects.select_related('slot__class_obj'), pk=session_id)
    if not PermissionService.can_user_modify_session(request.user, session):
        return JsonResponse({'error': 'Not authorized for this class.'}, status=403)

    expected = (session.slot.room or '').strip()
    room = request.POST.get('room', '').strip()
    if not room:
        return JsonResponse({'error': 'Room is required.'}, status=400)
    if expected and room.casefold() != expected.casefold():
        return JsonResponse({
            'error': f'Room mismatch. This session is assigned to {expected}.',
        }, status=400)

    verification, _ = RoomVerification.objects.update_or_create(
        session=session,
        defaults={'room': room, 'verified_by': request.user},
    )
    return JsonResponse({
        'ok': True,
        'room': verification.room,
        'verified_at': verification.verified_at.isoformat(),
    })


@login_required(login_url='login')
@require_POST
def push_subscription_save(request):
    try:
        payload = json.loads(request.body.decode('utf-8'))
        subscription = payload['subscription']
        keys = subscription['keys']
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError):
        return JsonResponse({'error': 'Invalid push subscription.'}, status=400)

    endpoint = subscription.get('endpoint', '').strip()
    if not endpoint or not keys.get('p256dh') or not keys.get('auth'):
        return JsonResponse({'error': 'Incomplete push subscription.'}, status=400)

    # Task 4.3: reuse PushNotificationService so subscribe/update auditing
    # matches delivery-side subscription handling.
    obj = PushNotificationService.create_subscription(
        user=request.user,
        endpoint=endpoint,
        p256dh=keys['p256dh'],
        auth=keys['auth'],
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
    )
    return JsonResponse({'ok': True, 'subscription_id': obj.pk})


@login_required(login_url='login')
@require_POST
def push_subscription_delete(request):
    endpoint = request.POST.get('endpoint', '').strip()
    if not endpoint:
        return JsonResponse({'error': 'Endpoint is required.'}, status=400)
    # Task 4.3: reuse the service so unsubscribe is audited the same way.
    deleted = PushNotificationService.delete_subscription(request.user, endpoint)
    return JsonResponse({'ok': True, 'deleted': deleted})


@login_required(login_url='login')
@require_GET
def excuse_calendar_page(request):
    profile = getattr(request.user, 'classstamp_profile', None)
    # Unified Calendar: Admins are directed to the full Academic & Leave Calendar
    if request.user.is_superuser or (profile and profile.role == Profile.ROLE_ADMIN):
        return redirect('admin_calendar')
    return render(request, 'core/excuse_calendar.html', {})


@login_required(login_url='login')
@role_required(Profile.ROLE_TEACHER, Profile.ROLE_ADMIN, Profile.ROLE_STUDENT)
@require_GET
def excuse_calendar(request):
    profile = getattr(request.user, 'classstamp_profile', None)
    slips = ExcuseSlip.objects.select_related(
        'student_profile__user',
        'session__slot__class_obj',
    ).filter(session__session_date__isnull=False)
    if profile.role == Profile.ROLE_TEACHER:
        slips = slips.filter(session__slot__class_obj__teacher_profile=profile)
    elif profile.role == Profile.ROLE_STUDENT:
        slips = slips.filter(student_profile=profile)

    events = []
    for slip in slips.order_by('session__session_date')[:500]:
        color = '#f59e0b' if slip.status == 'PENDING' else ('#10b981' if slip.status == 'APPROVED' else '#ef4444')
        student_name = (
            slip.student_profile.user.get_full_name()
            or slip.student_profile.student_number
            or slip.student_profile.user.get_username()
        )
        events.append({
            'id': f'excuse-{slip.pk}',
            # Name and section only: the status is rendered as a dot + label by
            # the calendar, not shouted into the title.
            'title': f'{student_name} · {slip.session.slot.class_obj.class_code}',
            'start': slip.session.session_date.isoformat(),
            'status': slip.status,
            'student_name': student_name,
            'class_code': slip.session.slot.class_obj.class_code,
            'subject_code': slip.session.slot.class_obj.subject.code,
            'color': color,
            'backgroundColor': color,
            'borderColor': color,
            'is_excuse': True,
        })

    # Include institutional milestones & holidays for context
    vis_filter = [AcademicEvent.VISIBILITY_ALL]
    if profile.role in (Profile.ROLE_TEACHER, Profile.ROLE_ADMIN):
        vis_filter.append(AcademicEvent.VISIBILITY_FACULTY)

    academic_events = AcademicEvent.objects.filter(
        status=AcademicEvent.STATUS_SCHEDULED,
        visibility__in=vis_filter,
    ).order_by('start_datetime')[:200]

    for ae in academic_events:
        meta = ae.category_meta
        start_val = ae.start_datetime.date().isoformat() if ae.is_all_day else ae.start_datetime.isoformat()
        end_val = ae.end_datetime.date().isoformat() if ae.is_all_day else ae.end_datetime.isoformat()
        events.append({
            'id': f'event-{ae.pk}',
            'title': ae.title,
            'start': start_val,
            'end': end_val,
            'allDay': ae.is_all_day,
            'color': meta['color'],
            'backgroundColor': meta['color'],
            'borderColor': meta['color'],
            'is_excuse': False,
        })

    return JsonResponse({'events': events})
