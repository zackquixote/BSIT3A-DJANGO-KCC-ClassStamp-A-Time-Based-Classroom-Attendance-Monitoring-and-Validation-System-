from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


# ============================================================
# 1. ORGANISATION: department > program (course) > year level > subjects
# ============================================================

class Department(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=150, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tblcs_department'
        ordering = ['name']

    def __str__(self):
        return f'{self.code} - {self.name}'


class Program(models.Model):
    department = models.ForeignKey(
        Department,
        on_delete=models.RESTRICT,
        related_name='programs',
    )
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=150)
    years_total = models.PositiveSmallIntegerField(
        default=4,
        validators=[MinValueValidator(1), MaxValueValidator(8)],
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tblcs_program'
        ordering = ['code']

    def __str__(self):
        return f'{self.code} - {self.name}'


class Subject(models.Model):
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tblcs_subject'
        ordering = ['code']

    def __str__(self):
        return f'{self.code} - {self.name}'


class Curriculum(models.Model):
    """Maps which subjects a program offers in a given year level."""
    program = models.ForeignKey(
        Program,
        on_delete=models.RESTRICT,
        related_name='curriculum_entries',
    )
    year_level = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)],
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.RESTRICT,
        related_name='curriculum_entries',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tblcs_curriculum'
        unique_together = [('program', 'year_level', 'subject')]

    def __str__(self):
        return f'{self.program.code} Y{self.year_level} - {self.subject.code}'


class AcademicYear(models.Model):
    name = models.CharField(max_length=40, unique=True)
    starts_on = models.DateField()
    ends_on = models.DateField()
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tblcs_academic_year'
        ordering = ['-starts_on']

    def __str__(self):
        return self.name


# ============================================================
# 2. PEOPLE: one profile per auth_user, three roles
#   ADMIN   - no department, program or student fields
#   TEACHER - belongs to a department
#   STUDENT - belongs to a program and year level, validated by an admin,
#             owns a secret that signs their rotating QR code
# ============================================================

class Profile(models.Model):
    ROLE_ADMIN = 'ADMIN'
    ROLE_TEACHER = 'TEACHER'
    ROLE_STUDENT = 'STUDENT'
    ROLE_CHOICES = [
        (ROLE_ADMIN, 'Admin'),
        (ROLE_TEACHER, 'Teacher'),
        (ROLE_STUDENT, 'Student'),
    ]

    APPROVAL_PENDING = 'PENDING'
    APPROVAL_APPROVED = 'APPROVED'
    APPROVAL_REJECTED = 'REJECTED'
    APPROVAL_CHOICES = [
        (APPROVAL_PENDING, 'Pending'),
        (APPROVAL_APPROVED, 'Approved'),
        (APPROVAL_REJECTED, 'Rejected'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='classstamp_profile',
    )
    role = models.CharField(max_length=7, choices=ROLE_CHOICES)

    # Teacher field
    department = models.ForeignKey(
        Department,
        on_delete=models.RESTRICT,
        null=True, blank=True,
        related_name='profiles',
    )

    # Student-only fields
    program = models.ForeignKey(
        Program,
        on_delete=models.RESTRICT,
        null=True, blank=True,
        related_name='profiles',
    )
    year_level = models.PositiveSmallIntegerField(null=True, blank=True)
    student_number = models.CharField(max_length=50, unique=True, null=True, blank=True)
    approval_status = models.CharField(
        max_length=8,
        choices=APPROVAL_CHOICES,
        null=True, blank=True,
    )
    approval_note = models.TextField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approved_profiles',
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    # Privacy & QR
    privacy_consent_at = models.DateTimeField(null=True, blank=True)
    privacy_notice_version = models.CharField(max_length=20, null=True, blank=True)
    qr_secret = models.CharField(max_length=64, null=True, blank=True)
    qr_rotated_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tblcs_profile'

    def __str__(self):
        return f'{self.user.get_full_name()} ({self.role})'


# ============================================================
# 3. CLASSES: subject taught by one teacher in one academic year
# ============================================================

class Class(models.Model):
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.RESTRICT,
        related_name='classes',
    )
    class_code = models.CharField(max_length=40)
    subject = models.ForeignKey(
        Subject,
        on_delete=models.RESTRICT,
        related_name='classes',
    )
    teacher_profile = models.ForeignKey(
        Profile,
        on_delete=models.RESTRICT,
        related_name='taught_classes',
    )
    capacity = models.PositiveIntegerField(null=True, blank=True)
    grace_minutes = models.PositiveSmallIntegerField(default=10)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tblcs_class'
        unique_together = [('academic_year', 'class_code')]
        ordering = ['class_code']

    def __str__(self):
        return f'{self.class_code} - {self.subject.code}'


class ClassSlot(models.Model):
    """A recurring weekly time slot for a class."""
    WEEKDAY_CHOICES = [
        (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'),
        (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday'),
    ]

    class_obj = models.ForeignKey(
        Class,
        on_delete=models.RESTRICT,
        related_name='slots',
        db_column='class_id',
    )
    weekday = models.PositiveSmallIntegerField(
        choices=WEEKDAY_CHOICES,
        validators=[MaxValueValidator(6)],
    )
    starts_at = models.TimeField()
    ends_at = models.TimeField()
    room = models.CharField(max_length=100, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tblcs_class_slot'
        unique_together = [('class_obj', 'weekday', 'starts_at')]

    def __str__(self):
        return f'{self.class_obj.class_code} - {self.get_weekday_display()} {self.starts_at}'


class Enrollment(models.Model):
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
    )
    class_obj = models.ForeignKey(
        Class,
        on_delete=models.RESTRICT,
        related_name='enrollments',
        db_column='class_id',
    )
    status = models.CharField(max_length=9, choices=STATUS_CHOICES, default=STATUS_PENDING)
    starts_on = models.DateField(null=True, blank=True)
    ends_on = models.DateField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approved_enrollments',
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tblcs_enrollment'
        unique_together = [('student_profile', 'class_obj')]

    def __str__(self):
        return f'{self.student_profile} -> {self.class_obj.class_code} ({self.status})'


# ============================================================
# 4. ATTENDANCE
# ============================================================

class ClassSession(models.Model):
    STATUS_SCHEDULED = 'SCHEDULED'
    STATUS_OPEN = 'OPEN'
    STATUS_CLOSED = 'CLOSED'
    STATUS_CANCELED = 'CANCELED'
    STATUS_CHOICES = [
        (STATUS_SCHEDULED, 'Scheduled'),
        (STATUS_OPEN, 'Open'),
        (STATUS_CLOSED, 'Closed'),
        (STATUS_CANCELED, 'Canceled'),
    ]

    slot = models.ForeignKey(
        ClassSlot,
        on_delete=models.RESTRICT,
        related_name='sessions',
    )
    session_date = models.DateField()
    status = models.CharField(max_length=9, choices=STATUS_CHOICES, default=STATUS_SCHEDULED)
    opened_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_sessions',
    )
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='opened_sessions',
    )
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='closed_sessions',
    )
    auto_closed = models.BooleanField(default=False)
    cancellation_reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tblcs_class_session'
        unique_together = [('slot', 'session_date')]
        ordering = ['-session_date']

    def __str__(self):
        return f'{self.slot.class_obj.class_code} - {self.session_date} ({self.status})'


class AttendanceRecord(models.Model):
    STATUS_PRESENT = 'PRESENT'
    STATUS_LATE = 'LATE'
    STATUS_ABSENT = 'ABSENT'
    STATUS_EXCUSED = 'EXCUSED'
    STATUS_CHOICES = [
        (STATUS_PRESENT, 'Present'),
        (STATUS_LATE, 'Late'),
        (STATUS_ABSENT, 'Absent'),
        (STATUS_EXCUSED, 'Excused'),
    ]

    METHOD_QR = 'QR'
    METHOD_CODE = 'CODE'
    METHOD_MANUAL = 'MANUAL'
    METHOD_SYSTEM = 'SYSTEM'
    METHOD_CHOICES = [
        (METHOD_QR, 'QR Scan'),
        (METHOD_CODE, 'Code'),
        (METHOD_MANUAL, 'Manual'),
        (METHOD_SYSTEM, 'System'),
    ]

    session = models.ForeignKey(
        ClassSession,
        on_delete=models.RESTRICT,
        related_name='attendance_records',
    )
    student_profile = models.ForeignKey(
        Profile,
        on_delete=models.RESTRICT,
        related_name='attendance_records',
    )
    status = models.CharField(max_length=8, choices=STATUS_CHOICES)
    method = models.CharField(max_length=6, choices=METHOD_CHOICES)
    stamped_at = models.DateTimeField(null=True, blank=True)
    late_minutes = models.PositiveSmallIntegerField(default=0)
    correction_reason = models.TextField(null=True, blank=True)
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.RESTRICT,
        null=True, blank=True,
        related_name='marked_attendance_records',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tblcs_attendance_record'
        unique_together = [('session', 'student_profile')]

    def __str__(self):
        return f'{self.student_profile} - {self.session} - {self.status}'


class StampAttempt(models.Model):
    """Audit log for every QR/code scan attempt, accepted or not."""
    METHOD_QR = 'QR'
    METHOD_CODE = 'CODE'
    METHOD_CHOICES = [
        (METHOD_QR, 'QR Scan'),
        (METHOD_CODE, 'Code'),
    ]

    OUTCOME_ACCEPTED = 'ACCEPTED'
    OUTCOME_INVALID = 'INVALID'
    OUTCOME_EXPIRED = 'EXPIRED'
    OUTCOME_DUPLICATE = 'DUPLICATE'
    OUTCOME_INELIGIBLE = 'INELIGIBLE'
    OUTCOME_SESSION_CLOSED = 'SESSION_CLOSED'
    OUTCOME_CHOICES = [
        (OUTCOME_ACCEPTED, 'Accepted'),
        (OUTCOME_INVALID, 'Invalid'),
        (OUTCOME_EXPIRED, 'Expired'),
        (OUTCOME_DUPLICATE, 'Duplicate'),
        (OUTCOME_INELIGIBLE, 'Ineligible'),
        (OUTCOME_SESSION_CLOSED, 'Session Closed'),
    ]

    session = models.ForeignKey(
        ClassSession,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='stamp_attempts',
    )
    student_profile = models.ForeignKey(
        Profile,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='stamp_attempts',
    )
    scanned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='stamp_attempts',
    )
    attempted_at = models.DateTimeField(auto_now_add=True)
    method = models.CharField(max_length=4, choices=METHOD_CHOICES)
    outcome = models.CharField(max_length=14, choices=OUTCOME_CHOICES)
    token_bucket = models.BigIntegerField(null=True, blank=True)
    token_age_s = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        db_table = 'tblcs_stamp_attempt'
        ordering = ['-attempted_at']

    def __str__(self):
        return f'{self.attempted_at} - {self.outcome}'


# ============================================================
# 5. REVIEW AND AUDIT
# ============================================================

class AnomalyFlag(models.Model):
    STATUS_OPEN = 'OPEN'
    STATUS_DISMISSED = 'DISMISSED'
    STATUS_CONFIRMED = 'CONFIRMED'
    STATUS_EXCUSED = 'EXCUSED'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_DISMISSED, 'Dismissed'),
        (STATUS_CONFIRMED, 'Confirmed'),
        (STATUS_EXCUSED, 'Excused'),
    ]

    attendance_record = models.ForeignKey(
        AttendanceRecord,
        on_delete=models.RESTRICT,
        related_name='anomaly_flags',
    )
    rule_code = models.CharField(max_length=50)
    reason = models.TextField()
    risk_score = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    status = models.CharField(max_length=9, choices=STATUS_CHOICES, default=STATUS_OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'tblcs_anomaly_flag'
        unique_together = [('attendance_record', 'rule_code')]

    def __str__(self):
        return f'{self.rule_code} - {self.status}'


class ReviewAction(models.Model):
    """Append-only log of decisions made on anomaly flags."""
    DECISION_DISMISS = 'DISMISS'
    DECISION_CONFIRM_PROXY = 'CONFIRM_PROXY'
    DECISION_EXCUSE = 'EXCUSE'
    DECISION_OTHER = 'OTHER'
    DECISION_CHOICES = [
        (DECISION_DISMISS, 'Dismiss'),
        (DECISION_CONFIRM_PROXY, 'Confirm Proxy'),
        (DECISION_EXCUSE, 'Excuse'),
        (DECISION_OTHER, 'Other'),
    ]

    anomaly_flag = models.ForeignKey(
        AnomalyFlag,
        on_delete=models.RESTRICT,
        related_name='review_actions',
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.RESTRICT,
        related_name='review_actions',
    )
    decision = models.CharField(max_length=14, choices=DECISION_CHOICES)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tblcs_review_action'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.decision} by {self.reviewer} on flag #{self.anomaly_flag_id}'


class AuditEvent(models.Model):
    """Append-only audit trail for all significant system actions."""
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='audit_events',
    )
    action = models.CharField(max_length=80)
    object_type = models.CharField(max_length=80)
    object_id = models.CharField(max_length=80, null=True, blank=True)
    old_value = models.TextField(null=True, blank=True)
    new_value = models.TextField(null=True, blank=True)
    reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tblcs_audit_event'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.action} on {self.object_type} #{self.object_id}'
