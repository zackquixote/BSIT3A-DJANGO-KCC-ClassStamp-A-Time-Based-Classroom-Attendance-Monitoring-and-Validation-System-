
"""
# // ==============================================================================
# // KCC CLASSSTAMP - PHYSICAL CLASSROOM & LABORATORY FACILITY MODELS
# // ==============================================================================
# // Subsystem: Facilities & Scheduling Infrastructure
# // Description: First-class CRUD entity for physical classrooms, computer
# //   laboratories, AVRs, and specialized instruction spaces.
# //   - Room: Physical space with code, name, capacity, room_type, and active status.
# // References: docs/04_MODELS_REFERENCE.md § Facilities & Classroom Infrastructure
# // ==============================================================================
"""

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Room(models.Model):
    """
    // [Model] Campus Room / Instructional Space
    // Represents a physical classroom, computer laboratory, or instructional facility.
    // Slots in a weekly class schedule reference a Room foreign key for conflict
    // detection, capacity validation, and lab equipment alignment.
    """
    ROOM_TYPE_LECTURE = 'LECTURE'
    ROOM_TYPE_LABORATORY = 'LABORATORY'
    ROOM_TYPE_AVR = 'AVR'
    ROOM_TYPE_OTHER = 'OTHER'

    ROOM_TYPE_CHOICES = [
        (ROOM_TYPE_LECTURE, 'Lecture Room'),
        (ROOM_TYPE_LABORATORY, 'Computer Laboratory'),
        (ROOM_TYPE_AVR, 'Audio-Visual Room (AVR)'),
        (ROOM_TYPE_OTHER, 'Other / Special Room'),
    ]

    code = models.CharField(
        max_length=30,
        unique=True,
        db_index=True,
        help_text="// Canonical room identifier, e.g. LAB-1, RM-101, RM-201"
    )
    name = models.CharField(
        max_length=100,
        help_text="// Descriptive room name, e.g. Computer Laboratory 1"
    )
    room_type = models.CharField(
        max_length=20,
        choices=ROOM_TYPE_CHOICES,
        default=ROOM_TYPE_LECTURE,
        db_index=True,
        help_text="// Functional classification (LECTURE, LABORATORY, AVR, OTHER)"
    )
    capacity = models.PositiveIntegerField(
        default=40,
        validators=[MinValueValidator(1), MaxValueValidator(500)],
        help_text="// Maximum student workstation or seating capacity"
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="// Active rooms are available for scheduling new slots"
    )
    notes = models.TextField(
        blank=True,
        default='',
        help_text="// Equipment notes, maintenance info, or restrictions"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        db_table = 'tblcs_room'
        ordering = ['room_type', 'code']

    def __str__(self):
        return f"{self.code} - {self.name} ({self.get_room_type_display()})"

    def clean(self):
        if self.code:
            self.code = self.code.strip().upper()
        if self.name:
            self.name = self.name.strip()

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    @property
    def is_lab(self) -> bool:
        return self.room_type == self.ROOM_TYPE_LABORATORY

    @property
    def is_lecture(self) -> bool:
        return self.room_type == self.ROOM_TYPE_LECTURE
