"""
# // ==============================================================================
# // KCC CLASSSTAMP - ACADEMIC CALENDAR & INSTITUTIONAL EVENTS
# // ==============================================================================
# // Subsystem: Academic Administration (RBAC: ADMIN ONLY MANAGEMENT)
# // Description: Defines models for institutional calendar events, term milestones,
# //   examination windows, holidays, and campus activities.
# // Security References: docs/02_SECURITY.md | docs/06_ADMIN_IMPROVEMENTS_ROADMAP.md
# // ==============================================================================
"""

from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class AcademicEvent(models.Model):
    """
    // [Model] Academic & Institutional Calendar Event
    // Represents term schedules, examinations, enrollment periods, holidays,
    // and collegiate meetings. Strictly managed by Administrators.
    """

    # Event Categories
    CATEGORY_ACADEMIC_TERM = 'ACADEMIC_TERM'
    CATEGORY_ENROLLMENT = 'ENROLLMENT'
    CATEGORY_EXAMINATION = 'EXAMINATION'
    CATEGORY_HOLIDAY = 'HOLIDAY'
    CATEGORY_COLLEGE_ACTIVITY = 'COLLEGE_ACTIVITY'
    CATEGORY_DEADLINE = 'DEADLINE'
    CATEGORY_MEETING = 'MEETING'
    CATEGORY_OTHER = 'OTHER'

    CATEGORY_CHOICES = [
        (CATEGORY_ACADEMIC_TERM, 'Academic Term'),
        (CATEGORY_ENROLLMENT, 'Enrollment Period'),
        (CATEGORY_EXAMINATION, 'Examination'),
        (CATEGORY_HOLIDAY, 'Holiday / Non-Working'),
        (CATEGORY_COLLEGE_ACTIVITY, 'College Activity'),
        (CATEGORY_DEADLINE, 'Academic Deadline'),
        (CATEGORY_MEETING, 'Institutional Meeting'),
        (CATEGORY_OTHER, 'Other'),
    ]

    # Category Visual Styles (Color & FontAwesome Icon)
    CATEGORY_META = {
        CATEGORY_ACADEMIC_TERM: {'color': '#6366f1', 'bg': 'rgba(99, 102, 241, 0.15)', 'icon': 'fa-graduation-cap', 'label': 'Academic Term'},
        CATEGORY_ENROLLMENT: {'color': '#3b82f6', 'bg': 'rgba(59, 130, 246, 0.15)', 'icon': 'fa-user-plus', 'label': 'Enrollment Period'},
        CATEGORY_EXAMINATION: {'color': '#ec4899', 'bg': 'rgba(236, 72, 153, 0.15)', 'icon': 'fa-file-signature', 'label': 'Examination'},
        CATEGORY_HOLIDAY: {'color': '#10b981', 'bg': 'rgba(16, 185, 129, 0.15)', 'icon': 'fa-umbrella-beach', 'label': 'Holiday / Non-Working'},
        CATEGORY_COLLEGE_ACTIVITY: {'color': '#f59e0b', 'bg': 'rgba(245, 158, 11, 0.15)', 'icon': 'fa-flag', 'label': 'College Activity'},
        CATEGORY_DEADLINE: {'color': '#ef4444', 'bg': 'rgba(239, 68, 68, 0.15)', 'icon': 'fa-hourglass-end', 'label': 'Academic Deadline'},
        CATEGORY_MEETING: {'color': '#8b5cf6', 'bg': 'rgba(139, 92, 246, 0.15)', 'icon': 'fa-handshake', 'label': 'Institutional Meeting'},
        CATEGORY_OTHER: {'color': '#64748b', 'bg': 'rgba(100, 116, 139, 0.15)', 'icon': 'fa-calendar-day', 'label': 'Other'},
    }

    # Event Status
    STATUS_SCHEDULED = 'SCHEDULED'
    STATUS_CANCELED = 'CANCELED'

    STATUS_CHOICES = [
        (STATUS_SCHEDULED, 'Scheduled'),
        (STATUS_CANCELED, 'Canceled'),
    ]

    # Target Audience / Visibility
    VISIBILITY_ALL = 'ALL'           # Admin, Teacher, Student
    VISIBILITY_FACULTY = 'FACULTY'   # Admin & Teacher only
    VISIBILITY_ADMIN = 'ADMIN'       # Admin internal only

    VISIBILITY_CHOICES = [
        (VISIBILITY_ALL, 'Public (All Roles)'),
        (VISIBILITY_FACULTY, 'Faculty & Admin'),
        (VISIBILITY_ADMIN, 'Admin Internal Only'),
    ]

    # Semester Scope
    SEMESTER_FIRST = '1ST_SEM'
    SEMESTER_SECOND = '2ND_SEM'
    SEMESTER_SUMMER = 'SUMMER'
    SEMESTER_ALL = 'ALL'

    SEMESTER_CHOICES = [
        (SEMESTER_ALL, 'Entire Academic Year / General'),
        (SEMESTER_FIRST, '1st Semester'),
        (SEMESTER_SECOND, '2nd Semester'),
        (SEMESTER_SUMMER, 'Summer Term'),
    ]

    title = models.CharField(max_length=200, help_text="// Event title or milestone headline")
    description = models.TextField(blank=True, null=True, help_text="// Full event briefing, instructions or notes")
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default=CATEGORY_COLLEGE_ACTIVITY)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SCHEDULED)
    visibility = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default=VISIBILITY_ALL)

    start_datetime = models.DateTimeField(db_index=True, help_text="// Scheduled start date & time (Asia/Manila)")
    end_datetime = models.DateTimeField(db_index=True, help_text="// Scheduled end date & time (Asia/Manila)")
    is_all_day = models.BooleanField(default=False, help_text="// Check if event spans full day(s)")
    location = models.CharField(max_length=150, blank=True, null=True, help_text="// Venue, auditorium, or virtual link")

    academic_year = models.ForeignKey(
        'core.AcademicYear',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='academic_events',
        help_text="// Associated institutional academic term"
    )
    semester = models.CharField(max_length=20, choices=SEMESTER_CHOICES, default=SEMESTER_ALL, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_academic_events',
        help_text="// Admin who created the event"
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='updated_academic_events',
        help_text="// Last admin who modified the event"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        db_table = 'tblcs_academic_event'
        ordering = ['start_datetime', 'title']
        indexes = [
            models.Index(fields=['start_datetime', 'end_datetime']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['academic_year', 'semester']),
        ]

    def __str__(self):
        status_suffix = " (Canceled)" if self.status == self.STATUS_CANCELED else ""
        return f"{self.title}{status_suffix} ({self.start_datetime.strftime('%Y-%m-%d')})"

    def clean(self):
        """Server-side data validation."""
        super().clean()
        if not self.title or not self.title.strip():
            raise ValidationError({'title': 'Event title is required.'})

        if self.start_datetime and self.end_datetime:
            if self.end_datetime < self.start_datetime:
                raise ValidationError({'end_datetime': 'End date & time cannot precede the start date & time.'})

    @property
    def category_meta(self):
        """Returns visual styling metadata (color, icon, label)."""
        return self.CATEGORY_META.get(self.category, self.CATEGORY_META[self.CATEGORY_OTHER])

    @property
    def is_past(self):
        """Returns True if the event has already concluded."""
        return self.end_datetime < timezone.now()

    @property
    def is_upcoming(self):
        """Returns True if the event starts in the future."""
        return self.start_datetime > timezone.now()

    @property
    def is_ongoing(self):
        """Returns True if the current time falls within the event window."""
        now = timezone.now()
        return self.start_datetime <= now <= self.end_datetime

    def get_conflicting_slots_count(self):
        """
        Calculates the number of active ClassSlots whose scheduled weekday falls
        within this event's date span. Crucial for identifying potential class conflicts
        during holidays, suspensions, and campus activities.
        """
        from apps.core.models.classroom import ClassSlot
        if not self.start_datetime or not self.end_datetime:
            return 0
        start_date = timezone.localtime(self.start_datetime).date()
        end_date = timezone.localtime(self.end_datetime).date()
        weekdays = set()
        days_span = min(max((end_date - start_date).days + 1, 1), 31)
        for i in range(days_span):
            weekdays.add((start_date + timedelta(days=i)).weekday())
        return ClassSlot.objects.filter(weekday__in=weekdays, is_active=True).count()
