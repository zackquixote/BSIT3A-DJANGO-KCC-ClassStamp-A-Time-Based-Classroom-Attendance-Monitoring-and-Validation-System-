"""
# // ==============================================================================
# // KCC CLASSSTAMP - ACADEMIC DOMAIN VALIDATORS
# // ==============================================================================
# // Subsystem: Academic Integrity Rules
# // Description: Validators for academic year spans, degree program durations,
# //   and class section code conventions.
# // ==============================================================================
"""

import re

from django.core.exceptions import ValidationError


def validate_academic_year_code(value: str):
    """
    // Validates that an academic year code conforms to YYYY-YYYY format
    // and that the second year is consecutive to the first (e.g. '2025-2026').
    """
    cleaned = str(value).strip()
    match = re.match(r'^(\d{4})-(\d{4})$', cleaned)
    if not match:
        raise ValidationError('Academic year must be formatted as YYYY-YYYY (e.g. 2025-2026).')

    start_yr = int(match.group(1))
    end_yr = int(match.group(2))
    if end_yr != start_yr + 1:
        raise ValidationError(
            f'Invalid academic year span "{cleaned}". End year must be consecutive to start year ({start_yr}-{start_yr + 1}).'
        )


def validate_program_duration(years: int):
    """
    // Enforces accredited collegiate program duration limits (1 to 8 years).
    """
    try:
        y = int(years)
        if y < 1 or y > 8:
            raise ValueError()
    except (ValueError, TypeError):
        raise ValidationError('Program duration must be between 1 and 8 years.')


def validate_class_section_code(value: str):
    """
    // Validates class section code format (e.g. 'BSIT-3A', 'CCS-101', 'IT-2B').
    """
    cleaned = str(value).strip().upper()
    if not cleaned:
        raise ValidationError('Class section code cannot be empty.')

    if not re.match(r'^[A-Z0-9\-_]{2,20}$', cleaned):
        raise ValidationError(
            'Section code must be 2–20 characters and contain only uppercase letters, numbers, and hyphens (e.g. BSIT-3A).'
        )
