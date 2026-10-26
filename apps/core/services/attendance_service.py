"""
# // ==============================================================================
# // KCC CLASSSTAMP - ATTENDANCE MATRIX AGGREGATION SERVICE
# // ==============================================================================
# // Builds the 2D attendance grid (enrolled students x class sessions) shared by
# // the admin matrix sheet and the teacher read-only matrix view.
# // ==============================================================================
"""

from django.utils import timezone

from apps.core.models import AttendanceRecord, ClassSession, Enrollment


def build_attendance_matrix(class_obj):
    """
    // [Service] Aggregates every active enrollment and session for a class into
    // per-student status cells plus attendance tallies and compliance rates.
    """
    enrollments = (
        Enrollment.objects
        .filter(class_obj=class_obj, status=Enrollment.STATUS_ACTIVE)
        .select_related('student_profile__user', 'student_profile__program')
        .order_by('student_profile__user__last_name', 'student_profile__user__first_name')
    )

    sessions = list(
        ClassSession.objects
        .filter(slot__class_obj=class_obj)
        .select_related('slot')
        .order_by('session_date', 'opened_at')
    )

    records = (
        AttendanceRecord.objects
        .filter(session__in=sessions)
        .select_related('student_profile')
    )

    record_map = {}
    for record in records:
        record_map[(record.student_profile_id, record.session_id)] = record

    session_list = []
    for session in sessions:
        session_list.append({
            'id': session.id,
            'date': session.session_date.strftime('%Y-%m-%d'),
            'display_date': session.session_date.strftime('%b %d'),
            'weekday': session.session_date.strftime('%a'),
            'room': session.slot.room if session.slot and session.slot.room else '—',
            'status': session.status,
        })

    student_rows = []
    total_attended_overall = 0
    total_possible_overall = 0

    for enrollment in enrollments:
        profile = enrollment.student_profile
        user = profile.user
        student_name = user.get_full_name() or user.username
        student_num = profile.student_number or '—'
        program_code = profile.program.code if profile.program else '—'

        present_cnt = 0
        late_cnt = 0
        absent_cnt = 0
        excused_cnt = 0
        cells = []

        for session in sessions:
            record = record_map.get((profile.id, session.id))
            if record:
                status = record.status
                if status == AttendanceRecord.STATUS_PRESENT:
                    present_cnt += 1
                elif status == AttendanceRecord.STATUS_LATE:
                    late_cnt += 1
                elif status == AttendanceRecord.STATUS_ABSENT:
                    absent_cnt += 1
                elif status == AttendanceRecord.STATUS_EXCUSED:
                    excused_cnt += 1
                cells.append({
                    'status': status,
                    'method': record.method,
                    'stamped_at': timezone.localtime(record.stamped_at).strftime('%I:%M %p') if record.stamped_at else '—',
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

    overall_rate = (
        round((total_attended_overall / total_possible_overall) * 100, 1)
        if total_possible_overall > 0 else 0
    )

    return {
        'session_list': session_list,
        'student_rows': student_rows,
        'total_students': len(student_rows),
        'total_sessions': len(session_list),
        'overall_rate': overall_rate,
    }
