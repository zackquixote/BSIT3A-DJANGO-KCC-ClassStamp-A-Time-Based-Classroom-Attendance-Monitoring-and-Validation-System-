"""
# // ==============================================================================
# // KCC CLASSSTAMP - USER PROFILE & RBAC MODEL
# // ==============================================================================
# // Subsystem: Identity & Role-Based Access Control
# // Description: One-to-one extension of Django's AUTH_USER_MODEL that defines
# //   the three system personas:
# //   - ADMIN:   Full management privileges, validation queue, audit log review.
# //   - TEACHER: Bound to a Department; manages classes and attendance sessions.
# //   - STUDENT: Bound to Program & year level; undergoes Admin approval;
# //              holds a 64-char TOTP QR secret for badge scanning.
# //
# // Live DB Integrity Constraints (enforced by triggers AND application layer):
# //   - chk_cs_profile_shape: Teacher must have department_id; Student must NOT.
# //   - Student must carry student_number, program, year_level, approval_status.
# //   - trg_cs_profile_bi: year_level must not exceed program.years_total.
# //   - trg_cs_profile_bu: only ADMIN may set approval fields; sets approved_at.
# // References: docs/02_SECURITY.md | docs/04_MODELS_REFERENCE.md § Profile
# // ==============================================================================
"""

from django.conf import settings
from django.db import models

from .academic import Department, Program


class Profile(models.Model):
    """
    // [Model] ClassStamp User Persona Profile
    // One-to-one extension of Django AUTH_USER_MODEL defining role boundaries.
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

    # // [Gender Enumeration]
    GENDER_MALE = 'M'
    GENDER_FEMALE = 'F'
    GENDER_CHOICES = [
        (GENDER_MALE, 'Male'),
        (GENDER_FEMALE, 'Female'),
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

    # // ------------------------------------------------------------------
    # // Teacher-Specific Attributes
    # // ------------------------------------------------------------------
    department = models.ForeignKey(
        Department,
        on_delete=models.RESTRICT,
        null=True, blank=True,
        related_name='profiles',
        help_text="// Faculty department affiliation (Required for TEACHER)"
    )

    # // ------------------------------------------------------------------
    # // Student-Specific Attributes
    # // ------------------------------------------------------------------
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
    gender = models.CharField(
        max_length=1,
        choices=GENDER_CHOICES,
        null=True, blank=True,
        help_text="// Student sex / gender (M: Male, F: Female)"
    )
    phone_number = models.CharField(
        max_length=20,
        null=True, blank=True,
        help_text="// Student mobile contact number (e.g. 09123456789)"
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

    # // ------------------------------------------------------------------
    # // Security, Privacy & QR TOTP Attributes
    # // ------------------------------------------------------------------
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

    @property
    def initials(self):
        """
        // Return 1-2 letter uppercase initials for profile avatar badges (e.g. 'Yaster Josua Dado' -> 'YD').
        """
        first = (self.user.first_name or '').strip()
        last = (self.user.last_name or '').strip()
        if first and last:
            return f"{first[0]}{last[0]}".upper()
        if first:
            parts = first.split()
            if len(parts) >= 2:
                return f"{parts[0][0]}{parts[-1][0]}".upper()
            return first[:2].upper()
        if last:
            parts = last.split()
            if len(parts) >= 2:
                return f"{parts[0][0]}{parts[-1][0]}".upper()
            return last[:2].upper()
        if self.user.username:
            return self.user.username[:2].upper()
        return "??"

    @property
    def estimated_gender(self):
        """
        // Gender accessor: returns explicit gender if set, fallback to heuristic.
        """
        if self.gender:
            return self.gender
        first = (self.user.first_name or '').strip().lower()
        female_names = (
            'micaella', 'mica', 'maria', 'mary', 'ana', 'anna', 'jane', 'joy',
            'grace', 'rose', 'princess', 'angel', 'bea', 'claire', 'patricia',
            'kristine', 'charlene', 'sarah', 'nicole', 'jessica', 'michelle',
            'stephanie', 'kim', 'althea', 'jasmine', 'chloe', 'ella', 'hannah',
            'faith', 'kate', 'mae', 'kaye', 'angela', 'jenny', 'karen', 'lisa',
            'cath', 'cathy', 'denise', 'danielle', 'diana', 'erika', 'fatima'
        )
        for fn in female_names:
            if fn in first:
                return 'F'
        if first.endswith(('a', 'ie', 'elle', 'ine', 'lyn', 'ette', 'ann')) and not first.endswith(('ua', 'ya', 'ka', 'el', 'ian', 'ran')):
            return 'F'
        return 'M'

    class Meta:
        app_label = 'core'
        db_table = 'tblcs_profile'

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.username} ({self.role})'
