"""
# // ==============================================================================
# // KCC CLASSSTAMP - CLASSROOM STRUCTURE, ROSTERS & ENROLLMENT MODELS
# // ==============================================================================
# // Subsystem: Classroom Management
# // Description: Models that represent the physical-to-digital classroom layer:
# //   - Class:      A subject section assigned to a teacher in an academic year.
# //   - ClassSlot:  Recurring weekly schedule slot with room and time window.
# //   - Enrollment: M2M binding of an approved student to a class section.
# // References: docs/04_MODELS_REFERENCE.md § Classroom Structure
# // ==============================================================================
"""

from django.conf import settings
from django.core.validators import MaxValueValidator
from django.db import models

from .academic import AcademicYear, Subject
from .profile import Profile


class Class(models.Model):
    """
    // [Model] Academic Class Section
    // Represents a specific subject section assigned to a teacher within an academic year.
    """
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.RESTRICT,
        related_name='classes',
        help_text="// Associated academic school year/term"
    )
    class_code = models.CharField(
        max_length=40,
        help_text="// Course section code, e.g. BSIT-3A-CS101"
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.RESTRICT,
        related_name='classes',
        help_text="// Academic subject being instructed"
    )
    teacher_profile = models.ForeignKey(
        Profile,
        on_delete=models.RESTRICT,
        related_name='taught_classes',
        help_text="// Instructor responsible for class delivery"
    )
    capacity = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="// Maximum allowable roster size"
    )
    grace_minutes = models.PositiveSmallIntegerField(
        default=10,
        help_text="// Grace period window in minutes before stamping triggers LATE status"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        db_table = 'tblcs_class'
        unique_together = [('academic_year', 'class_code')]
        ordering = ['class_code']

    def __str__(self):
        return f'{self.class_code} - {self.subject.code}'


class ClassSlot(models.Model):
    """
    // [Model] Weekly Recurring Class Schedule Slot
    // Defines recurring meeting times (e.g., Monday 08:00 - 10:00 in Room IT-Lab 1).
    """
    WEEKDAY_CHOICES = [
        (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'),
        (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday'),
    ]

    class_obj = models.ForeignKey(
        Class,
        on_delete=models.RESTRICT,
        related_name='slots',
        db_column='class_id',
        help_text="// Parent class section"
    )
    weekday = models.PositiveSmallIntegerField(
        choices=WEEKDAY_CHOICES,
        validators=[MaxValueValidator(6)],
        help_text="// Day of the week (0 = Monday .. 6 = Sunday)"
    )
    starts_at = models.TimeField(help_text="// Scheduled start time")
    ends_at = models.TimeField(help_text="// Scheduled end time")
    room = models.CharField(max_length=100, default='', help_text="// Assigned physical or virtual classroom")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        db_table = 'tblcs_class_slot'
        unique_together = [('class_obj', 'weekday', 'starts_at')]

    def __str__(self):
        return f'{self.class_obj.class_code} - {self.get_weekday_display()} {self.starts_at}'


class Enrollment(models.Model):
    """
    // [Model] Student Class Roster Enrollment
    // Associates an approved student with a class section.
    """
    STATUS_PENDING = 'PENDING'
    STATUS_ACTIVE = 'ACTIVE'
    STATUS_COMPLETED = 'COMPLETED'
    STATUS_WITHDRAWN = 'WITHDRAWN'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_ACTIVE, 'Active'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_WITHDRAWN, 'Withdrawn'),
    ]

    student_profile = models.ForeignKey(
        Profile,
        on_delete=models.RESTRICT,
        related_name='enrollments',
        help_text="// Enrolled student profile"
    )
    class_obj = models.ForeignKey(
        Class,
        on_delete=models.RESTRICT,
        related_name='enrollments',
        db_column='class_id',
        help_text="// Enrolled class section"
    )
    status = models.CharField(max_length=9, choices=STATUS_CHOICES, default=STATUS_PENDING)
    starts_on = models.DateField(null=True, blank=True)
    ends_on = models.DateField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approved_enrollments',
        help_text="// Admin or Teacher granting enrollment"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        db_table = 'tblcs_enrollment'
        unique_together = [('student_profile', 'class_obj')]

    def __str__(self):
        return f'{self.student_profile} -> {self.class_obj.class_code} ({self.status})'
