"""Compatibility exports for dashboard helper modules."""

from .admin_dashboard import _admin_dashboard_stats
from .dashboard_activity import (
    get_activity_feed,
    get_attendance_chart_data,
    get_attendance_heatmap_data,
    get_pending_count,
)
from .student_dashboard import _student_dashboard_stats
from .teacher_dashboard import _teacher_dashboard_stats

__all__ = [
    "_admin_dashboard_stats",
    "_teacher_dashboard_stats",
    "_student_dashboard_stats",
    "get_activity_feed",
    "get_pending_count",
    "get_attendance_chart_data",
    "get_attendance_heatmap_data",
]
