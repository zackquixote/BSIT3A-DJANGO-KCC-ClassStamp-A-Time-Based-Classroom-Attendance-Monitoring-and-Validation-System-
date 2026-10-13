"""
// ==============================================================================
// KCC CLASSSTAMP - DOMAIN MODELS & ENTITY SCHEMA
// ==============================================================================
// Description: Core relational schema supporting Time-Based Classroom Attendance
// Monitoring and Validation System. Implements multi-tier academic structure,
// role-based persona profiles (Admin, Teacher, Student), automated attendance
// sessions, QR-based stamp auditing, and fraud anomaly detection.
// References: docs/04_MODELS_REFERENCE.md | docs/02_SECURITY.md
// ==============================================================================
"""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


# // ==============================================================================
# // SECTION 1: ACADEMIC ORGANISATION (Department -> Program -> Subject -> Curriculum)
# // ==============================================================================

class Department(models.Model):
    """
    // [Model] Academic Department
    // Represents top-level institutional division (e.g., College of Computer Studies).
    // Teachers are bound directly to a Department.
    """
    code = models.CharField(max_length=20, unique=True, help_text="// Unique department code, e.g. CCS")
    name = models.CharField(max_length=150, unique=True, help_text="// Full department name")
    is_active = models.BooleanField(default=True, help_text="// Soft-delete flag for academic departments")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tblcs_department'
        ordering = ['name']

    def __str__(self):
        return f'{self.code} - {self.name}'


class Program(models.Model):
    """
    // [Model] Degree Program / Course
    // Belongs to a single Department. Defines default curriculum duration (e.g. BSIT = 4 years).
    // Students are enrolled under a specific Program.
    """
    department = models.ForeignKey(
        Department,
        on_delete=models.RESTRICT,
        related_name='programs',
        help_text="// Owning academic department"
    )
    code = models.CharField(max_length=20, unique=True, help_text="// Unique degree acronym, e.g. BSIT")
    name = models.CharField(max_length=150, help_text="// Full degree program title")
    years_total = models.PositiveSmallIntegerField(
        default=4,
        validators=[MinValueValidator(1), MaxValueValidator(8)],
        help_text="// Maximum allowable years for degree completion"
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
    """
    // [Model] Academic Subject / Course Offering
    // Represents an institutional subject/course (e.g., IT 101 - Web Development).
    """
    code = models.CharField(max_length=40, unique=True, help_text="// Unique course code, e.g. IT311")
    name = models.CharField(max_length=150, help_text="// Official subject descriptive title")
    description = models.TextField(blank=True, null=True, help_text="// Syllabus syllabus/overview")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tblcs_subject'
        ordering = ['code']

    def __str__(self):
        return f'{self.code} - {self.name}'


class Curriculum(models.Model):
    """
    // [Model] Curriculum Matrix
    // Maps which subjects a program offers across designated year levels.
    """
    program = models.ForeignKey(
        Program,
        on_delete=models.RESTRICT,
        related_name='curriculum_entries',
        help_text="// Program this curriculum belongs to"
    )
    year_level = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)],
        help_text="// Standing year level (1 = 1st Year, etc.)"
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.RESTRICT,
        related_name='curriculum_entries',
        help_text="// Subject included in program prospectus"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tblcs_curriculum'
        unique_together = [('program', 'year_level', 'subject')]

    def __str__(self):
        return f'{self.program.code} Y{self.year_level} - {self.subject.code}'


class AcademicYear(models.Model):
    """
    // [Model] Academic Year & Term Period
    // Governs semester / school year validity window for class allocations and attendance.
    """
    name = models.CharField(max_length=40, unique=True, help_text="// Term identifier, e.g. 2025-2026 1st Sem")
    starts_on = models.DateField(help_text="// Term opening date")
    ends_on = models.DateField(help_text="// Term closing date")
    is_active = models.BooleanField(default=False, help_text="// Only one active academic term recommended")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tblcs_academic_year'
        ordering = ['-starts_on']

    def __str__(self):
        return self.name


# // ==============================================================================
# // SECTION 2: IDENTITY & ROLE-BASED ACCESS CONTROL (Profile)
# // ==============================================================================

class Profile(models.Model):
    """
    // [Model] ClassStamp User Persona Profile
    // One-to-one extension of Django AUTH_USER_MODEL defining role boundaries:
    // - ADMIN: Full management privileges, validation queue oversight, audit log review.
    // - TEACHER: Bound to Department; manages assigned classes, activates attendance sessions.
    // - STUDENT: Bound to Program & year level; undergoes Admin approval; holds TOTP QR secret.
    //
    // Integrity Constraints (Enforced at DB trigger & application layers):
    // - Teacher must specify department, student must NOT specify department.
    // - Student must specify program, year_level, student_number, and approval_status.
    """
    # // [Role Enumeration]
    ROLE_ADMIN = 'ADMIN'
    ROLE_TEACHER = 'TEACHER'
    ROLE_STUDENT = 'STUDENT'
    ROLE_CHOICES = [
        (ROLE_ADMIN, 'Admin'),
        (ROLE_TEACHER, 'Teacher'),
        (ROLE_STUDENT, 'Student'),
    ]

    # // [Student Account Approval Enumeration]
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
        help_text="// Underlying authentication account"
    )
    role = models.CharField(
        max_length=7,
        choices=ROLE_CHOICES,
        help_text="// System access persona role (ADMIN, TEACHER, STUDENT)"
    )

    # // ----------------------------------------------------------------------
    # // Teacher-Specific Attributes
    # // ----------------------------------------------------------------------
    department = models.ForeignKey(
        Department,
        on_delete=models.RESTRICT,
        null=True, blank=True,
        related_name='profiles',
        help_text="// Faculty department affiliation (Required for TEACHER)"
    )

    # // ----------------------------------------------------------------------
    # // Student-Specific Attributes
    # // ----------------------------------------------------------------------
    program = models.ForeignKey(
        Program,
        on_delete=models.RESTRICT,
        null=True, blank=True,
        related_name='profiles',
        help_text="// Enrolled college program (Required for STUDENT)"
    )
    year_level = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="// Current academic year level (e.g., 1, 2, 3, 4)"
    )
    student_number = models.CharField(
        max_length=50,
        unique=True,
        null=True, blank=True,
        help_text="// Institutional Student ID number from physical KCC badge"
    )
    registration_proof = models.FileField(
        upload_to='registration_proofs/',
        null=True, blank=True,
        help_text="// Uploaded Certificate of Registration (COR) or ID badge proof"
    )
    approval_status = models.CharField(
        max_length=8,
        choices=APPROVAL_CHOICES,
        null=True, blank=True,
        help_text="// Administrative verification state for student accounts"
    )
    approval_note = models.TextField(
        null=True, blank=True,
        help_text="// Administrative remarks (Mandatory if registration is REJECTED)"
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approved_profiles',
        help_text="// Admin who evaluated registration"
    )
    approved_at = models.DateTimeField(
        null=True, blank=True,
        help_text="// Timestamp of approval or rejection"
    )

    # // ----------------------------------------------------------------------
    # // Security, Privacy & QR TOTP Attributes
    # // ----------------------------------------------------------------------
    privacy_consent_at = models.DateTimeField(
        null=True, blank=True,
        help_text="// Timestamp when data privacy notice was acknowledged"
    )
    privacy_notice_version = models.CharField(
        max_length=20,
        null=True, blank=True,
        help_text="// Version string of accepted privacy terms"
    )
    qr_secret = models.CharField(
        max_length=64,
        null=True, blank=True,
        help_text="// 64-char hex secret utilized to sign rotating dynamic TOTP QR stamps"
    )
    qr_rotated_at = models.DateTimeField(
        null=True, blank=True,
        help_text="// Timestamp when student's QR secret was last cycled"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tblcs_profile'

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.username} ({self.role})'


# // ==============================================================================
# // SECTION 3: CLASSROOM STRUCTURE, ROSTERS & ENROLLMENT
# // ==============================================================================

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
        db_table = 'tblcs_enrollment'
        unique_together = [('student_profile', 'class_obj')]

    def __str__(self):
        return f'{self.student_profile} -> {self.class_obj.class_code} ({self.status})'


# // ==============================================================================
# // SECTION 4: TIME-BASED ATTENDANCE SESSIONS & ATTENDANCE RECORDS
# // ==============================================================================

class ClassSession(models.Model):
    """
    // [Model] Daily Concrete Class Attendance Session
    // Instantiated on a specific calendar date against a ClassSlot schedule.
    // Lifecycle transitions:
    // SCHEDULED -> OPEN (scanning active) -> CLOSED (scanning concluded) / CANCELED
    """
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
        help_text="// Schedule slot template"
    )
    session_date = models.DateField(help_text="// Actual calendar date of meeting")
    status = models.CharField(max_length=9, choices=STATUS_CHOICES, default=STATUS_SCHEDULED)
    opened_at = models.DateTimeField(null=True, blank=True, help_text="// Timestamp when teacher opened session")
    closed_at = models.DateTimeField(null=True, blank=True, help_text="// Timestamp when session was terminated")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_sessions'
    )
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='opened_sessions'
    )
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='closed_sessions'
    )
    auto_closed = models.BooleanField(
        default=False,
        help_text="// True if session was terminated automatically at schedule end time"
    )
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
    """
    // [Model] Confirmed Student Attendance Record
    // Captures the finalized status (PRESENT, LATE, ABSENT, EXCUSED) for a student in a session.
    """
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
        help_text="// Target attendance meeting"
    )
    student_profile = models.ForeignKey(
        Profile,
        on_delete=models.RESTRICT,
        related_name='attendance_records',
        help_text="// Student marked in session"
    )
    status = models.CharField(max_length=8, choices=STATUS_CHOICES)
    method = models.CharField(max_length=6, choices=METHOD_CHOICES, help_text="// Verification mechanism")
    stamped_at = models.DateTimeField(null=True, blank=True, help_text="// Exact timestamp of validation stamp")
    late_minutes = models.PositiveSmallIntegerField(
        default=0,
        help_text="// Minutes elapsed past scheduled start time and grace buffer"
    )
    correction_reason = models.TextField(
        null=True, blank=True,
        help_text="// Justification if marked or corrected manually by instructor"
    )
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.RESTRICT,
        null=True, blank=True,
        related_name='marked_attendance_records',
        help_text="// Instructor or system agent who recorded attendance"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tblcs_attendance_record'
        unique_together = [('session', 'student_profile')]

    def __str__(self):
        return f'{self.student_profile} - {self.session} - {self.status}'


class StampAttempt(models.Model):
    """
    // [Model] Scan & Stamp Audit Log (Anti-Replay / Fraud Prevention)
    // Immutable log capturing every QR scan or code submission attempt regardless of outcome.
    // Crucial for anomaly detection and rate-limiting brute-force attempts.
    """
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
        related_name='stamp_attempts'
    )
    student_profile = models.ForeignKey(
        Profile,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='stamp_attempts'
    )
    scanned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='stamp_attempts',
        help_text="// Teacher terminal or camera scanning the badge"
    )
    attempted_at = models.DateTimeField(auto_now_add=True)
    method = models.CharField(max_length=4, choices=METHOD_CHOICES)
    outcome = models.CharField(max_length=14, choices=OUTCOME_CHOICES)
    token_bucket = models.BigIntegerField(
        null=True, blank=True,
        help_text="// 30-second TOTP step window interval identifier"
    )
    token_age_s = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="// Age in seconds of token relative to current wall clock"
    )

    class Meta:
        db_table = 'tblcs_stamp_attempt'
        ordering = ['-attempted_at']

    def __str__(self):
        return f'{self.attempted_at} - {self.outcome}'


# // ==============================================================================
# // SECTION 5: FRAUD DETECTION, ANOMALY FLAGGING & AUDIT TRAIL
# // ==============================================================================

class AnomalyFlag(models.Model):
    """
    // [Model] Attendance Anomaly / Fraud Flag
    // Triggered automatically by pattern detectors (e.g., impossible travel time,
    // proxy device sharing, duplicate tokens in short spans).
    """
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
        related_name='anomaly_flags'
    )
    rule_code = models.CharField(
        max_length=50,
        help_text="// Rule mnemonic, e.g. RULE_RAPID_SCAN_PROXY"
    )
    reason = models.TextField(help_text="// Detailed forensic rationale")
    risk_score = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True, blank=True,
        help_text="// Statistical confidence score (0.0000 - 1.0000)"
    )
    status = models.CharField(max_length=9, choices=STATUS_CHOICES, default=STATUS_OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'tblcs_anomaly_flag'
        unique_together = [('attendance_record', 'rule_code')]

    def __str__(self):
        return f'{self.rule_code} - {self.status}'


class ReviewAction(models.Model):
    """
    // [Model] Forensic Anomaly Adjudication Action
    // Append-only history of administrative decisions rendered against AnomalyFlag alerts.
    """
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
        related_name='review_actions'
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.RESTRICT,
        related_name='review_actions',
        help_text="// Admin or authorized investigator"
    )
    decision = models.CharField(max_length=14, choices=DECISION_CHOICES)
    reason = models.TextField(help_text="// Official justification for adjudication")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tblcs_review_action'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.decision} by {self.reviewer} on flag #{self.anomaly_flag_id}'


class AuditEvent(models.Model):
    """
    // [Model] Global Append-Only Security & Operational Audit Log
    // Tracks all high-privilege activities (account validations, overrides, key rotations).
    // Immutable record: entries should never be updated or pruned in production.
    """
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='audit_events',
        help_text="// User account responsible for action"
    )
    action = models.CharField(max_length=80, help_text="// Action keyword e.g. APPROVE_STUDENT")
    object_type = models.CharField(max_length=80, help_text="// Target entity class e.g. Profile")
    object_id = models.CharField(max_length=80, null=True, blank=True, help_text="// Primary key of affected record")
    old_value = models.TextField(null=True, blank=True, help_text="// Previous state snapshot")
    new_value = models.TextField(null=True, blank=True, help_text="// Updated state snapshot")
    reason = models.TextField(null=True, blank=True, help_text="// User-provided remark or explanation")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tblcs_audit_event'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.action} on {self.object_type} #{self.object_id}'
