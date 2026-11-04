"""
# // ==============================================================================
# // KCC CLASSSTAMP - ACADEMIC ORGANISATION MODELS
# // ==============================================================================
# // Subsystem: Academic Hierarchy (Department → Program → Subject → Curriculum)
# // Description: Defines the foundational institutional structure.
# //   - Department: Top-level college division (e.g., College of Computer Studies).
# //   - Program:    Degree course offered by a department (e.g., BSIT, BSCS).
# //   - Subject:    Discrete course/subject offering (e.g., IT311 - Web Dev).
# //   - Curriculum: M2M mapping of subjects to programs across year levels.
# //   - AcademicYear: Semester/school-year validity window governing sessions.
# // References: docs/04_MODELS_REFERENCE.md § Academic Organisation
# // ==============================================================================
"""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


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
        app_label = 'core'
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
        app_label = 'core'
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
    units = models.PositiveSmallIntegerField(
        default=3,
        validators=[MinValueValidator(1)],
        help_text="// Credit units; 1 unit = 1 class hour per week",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        db_table = 'tblcs_subject'
        ordering = ['code']

    def __str__(self):
        return f'{self.code} - {self.name}'


class CurriculumVersion(models.Model):
    """
    // [Model] Curriculum Version
    // A reviewable snapshot of a program's curriculum. Only a DRAFT version may
    // be edited; exactly one APPROVED version should be effective at a time.
    """
    STATUS_DRAFT = 'DRAFT'
    STATUS_APPROVED = 'APPROVED'
    STATUS_ARCHIVED = 'ARCHIVED'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_ARCHIVED, 'Archived'),
    ]

    program = models.ForeignKey(
        Program,
        on_delete=models.RESTRICT,
        related_name='curriculum_versions',
        help_text="// Program whose curriculum this version describes",
    )
    version_number = models.PositiveIntegerField(
        help_text="// Incrementing version number within the program",
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        db_index=True,
        help_text="// Draft versions are editable; approved versions are read-only",
    )
    effective_from = models.ForeignKey(
        'AcademicYear',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='curriculum_versions',
        help_text="// First term in which this approved version applies",
    )
    notes = models.TextField(
        blank=True,
        default='',
        help_text="// Reviewer notes describing what changed in this version",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_curriculum_versions',
        help_text="// User who created this draft",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_curriculum_versions',
        help_text="// User who approved this curriculum version",
    )
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="// When this version was approved",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        db_table = 'tblcs_curriculum_version'
        unique_together = [('program', 'version_number')]
        ordering = ['program__code', '-version_number']

    def __str__(self):
        return f'{self.program.code} curriculum v{self.version_number} ({self.status})'


class Curriculum(models.Model):
    """
    // [Model] Curriculum Matrix
    // Maps which subjects a program offers across designated year levels and
    // semesters (1st / 2nd / Summer), powering the program-centric Year x Semester grid.
    """
    SEMESTER_CHOICES = [
        (1, '1st Semester'),
        (2, '2nd Semester'),
        (3, 'Summer'),
    ]

    program = models.ForeignKey(
        Program,
        on_delete=models.RESTRICT,
        related_name='curriculum_entries',
        help_text="// Program this curriculum belongs to"
    )
    version = models.ForeignKey(
        CurriculumVersion,
        on_delete=models.CASCADE,
        related_name='entries',
        null=True,
        blank=True,
        help_text="// Version snapshot this entry belongs to (legacy rows may be blank)",
    )
    year_level = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)],
        help_text="// Standing year level (1 = 1st Year, etc.)"
    )
    semester = models.PositiveSmallIntegerField(
        choices=SEMESTER_CHOICES,
        default=1,
        help_text="// Academic period within the year level"
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.RESTRICT,
        related_name='curriculum_entries',
        help_text="// Subject included in program prospectus"
    )
    is_major = models.BooleanField(
        default=False,
        help_text="// Whether this subject is part of the program's major field",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        db_table = 'tblcs_curriculum'
        unique_together = [('version', 'year_level', 'semester', 'subject')]

    def __str__(self):
        return f'{self.program.code} Y{self.year_level} S{self.semester} - {self.subject.code}'


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
        app_label = 'core'
        db_table = 'tblcs_academic_year'
        ordering = ['-starts_on']

    def __str__(self):
        return self.name
