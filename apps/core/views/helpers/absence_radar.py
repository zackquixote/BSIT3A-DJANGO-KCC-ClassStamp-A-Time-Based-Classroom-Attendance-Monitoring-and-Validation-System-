"""
# // ==============================================================================
# // KCC CLASSSTAMP - CHED 20% ABSENCE RADAR HELPERS
# // ==============================================================================
# // Subsystem: Teacher Portal — Failure Due to Absences (FDA) Risk Telemetry
# // Description: Computes per-student unexcused absence rates within a class and
# //   classifies them into institutional radar bands:
# //     SAFE      (<10%)
# //     WATCH     (10-19%)
# //     CRITICAL  (>=20% → FDA risk per CHED policy)
# //   Only AttendanceRecord.STATUS_ABSENT counts as an absence; EXCUSED and
# //   pending sessions do not. Denominator is the student's own finalized
# //   record count for the class (auto-close backfills ABSENT on session close,
# //   so concluded sessions are complete).
# // References: docs/09_MASTER_IMPROVEMENTS_ROADMAP.md § T-01
# // ==============================================================================
"""

from django.db.models import Count, Q

from apps.core.models import AttendanceRecord

BAND_SAFE = 'SAFE'
BAND_WATCH = 'WATCH'
BAND_CRITICAL = 'CRITICAL'

BAND_DISPLAY = {
    BAND_SAFE: 'Safe',
    BAND_WATCH: 'Watchlist',
    BAND_CRITICAL: 'FDA Risk',
}


def classify_absence_rate(rate):
    """// Map an absence percentage to a CHED radar band."""
    if rate < 10.0:
        return BAND_SAFE
    if rate < 20.0:
        return BAND_WATCH
    return BAND_CRITICAL


def _build_radar(class_obj, student_ids=None):
    """// Single aggregated query: unexcused ABSENT counts vs finalized records per student."""
    qs = (
        AttendanceRecord.objects.filter(session__slot__class_obj=class_obj)
        .values('student_profile_id')
        .annotate(
            total=Count('id'),
            absent=Count('id', filter=Q(status=AttendanceRecord.STATUS_ABSENT)),
        )
    )
    if student_ids is not None:
        qs = qs.filter(student_profile_id__in=student_ids)

    radar = {}
    for row in qs:
        rate = round((row['absent'] / row['total'] * 100), 1) if row['total'] else 0.0
        radar[row['student_profile_id']] = {
            'absent': row['absent'],
            'total': row['total'],
            'rate': rate,
            'band': classify_absence_rate(rate),
        }
    return radar


def absence_radar_for_class(class_obj):
    """// Band membership counts across the class (for dashboard class cards)."""
    counts = {BAND_SAFE: 0, BAND_WATCH: 0, BAND_CRITICAL: 0}
    for entry in _build_radar(class_obj).values():
        counts[entry['band']] += 1
    return counts


def absence_radar_for_students(class_obj, student_ids):
    """// Per-student radar entries; students with no records default to SAFE / 0%."""
    radar = _build_radar(class_obj, student_ids=student_ids)
    default = {'absent': 0, 'total': 0, 'rate': 0.0, 'band': BAND_SAFE}
    return {sid: radar.get(sid, default) for sid in student_ids}
