
"""
# // ==============================================================================
# // KCC CLASSSTAMP - PHYSICAL CLASSROOM & LABORATORY FACILITY MODELS
# // ==============================================================================
# // Subsystem: Facilities & Scheduling Infrastructure
# // Description: First-class CRUD entity for physical classrooms, computer
# //   laboratories, building-specific rooms, and specialized instruction spaces.
# //   - Room: Physical space with code, name, capacity, room_type, and active status.
# // References: docs/04_MODELS_REFERENCE.md § Facilities & Classroom Infrastructure
# // ==============================================================================
"""

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class FacilityType(models.Model):
    """
    // [Model] Campus Facility Type
    // Registrar-managed lookup for room classifications (lecture room, computer
    // laboratory, HS room, ELEM room, ...). Rooms store the code string so
    // existing slot/conflict queries keep working; the label is resolved from
    // this table instead of a frozen choices list.
    """
    code = models.CharField(
        max_length=20,
        unique=True,
        help_text="// Short canonical code, e.g. LECTURE, LABORATORY, HSB",
    )
    name = models.CharField(
        max_length=60,
        help_text="// Display label, e.g. Lecture Room, HS Building Room",
    )
    sort_order = models.PositiveSmallIntegerField(
        default=100,
        help_text="// Lower numbers appear first in pickers",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        db_table = 'tblcs_facility_type'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return f'{self.code} - {self.name}'

    def clean(self):
        if self.code:
            self.code = self.code.strip().upper()
        if self.name:
            self.name = self.name.strip()

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class Room(models.Model):
    """
    // [Model] Campus Room / Instructional Space
    // Represents a physical classroom, computer laboratory, or instructional facility.
    // Slots in a weekly class schedule reference a Room foreign key for conflict
    // detection, capacity validation, and lab equipment alignment.
    """
    ROOM_TYPE_LECTURE = 'LECTURE'
    ROOM_TYPE_LABORATORY = 'LABORATORY'
    ROOM_TYPE_HS = 'HS'
    ROOM_TYPE_ELEM = 'ELEM'
    ROOM_TYPE_OTHER = 'OTHER'

    ROOM_TYPE_CHOICES = [
        (ROOM_TYPE_LECTURE, 'Lecture Room'),
        (ROOM_TYPE_LABORATORY, 'Computer Laboratory'),
        (ROOM_TYPE_HS, 'HS Room'),
        (ROOM_TYPE_ELEM, 'Elem Room'),
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
        help_text="// Functional classification (LECTURE, LABORATORY, HS, ELEM, OTHER)"
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

    def get_room_type_display(self):
        """
        // Resolve the registrar-managed label first, then fall back to the
        // built-in choice list for rows that predate the lookup table.
        """
        label = (
            FacilityType.objects
            .filter(code=self.room_type)
            .values_list('name', flat=True)
            .first()
        )
        if label:
            return label
        return dict(self.ROOM_TYPE_CHOICES).get(self.room_type, self.room_type)

    @property
    def is_lab(self) -> bool:
        return self.room_type == self.ROOM_TYPE_LABORATORY

    @property
    def is_lecture(self) -> bool:
        return self.room_type == self.ROOM_TYPE_LECTURE
