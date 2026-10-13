"""
# // ==============================================================================
# // KCC CLASSSTAMP - IDENTITY & CREDENTIAL PROOF VALIDATORS
# // ==============================================================================
# // Subsystem: Identity Verification & Upload Security
# // Description: Validators for student ID format and uploaded proof file
# //   extension/size security.
# // ==============================================================================
"""

import os
import re

from django.core.exceptions import ValidationError

ALLOWED_PROOF_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png', '.webp'}
MAX_PROOF_FILE_SIZE_MB = 5
MAX_PROOF_FILE_SIZE_BYTES = MAX_PROOF_FILE_SIZE_MB * 1024 * 1024


def validate_student_id(value: str):
    """
    // Validates that a student ID conforms to institutional format rules:
    // Allows standard hyphenated cohorts (e.g. 2024-0001) or alphanumeric IDs (4–30 chars).
    """
    if not value or not str(value).strip():
        raise ValidationError('Student ID number cannot be empty.')

    cleaned = str(value).strip()
    if not re.match(r'^[A-Za-z0-9\-_]{4,30}$', cleaned):
        raise ValidationError(
            'Student ID must be 4–30 characters long and contain only letters, numbers, hyphens, or underscores.'
        )


def validate_proof_file_size(file_obj):
    """
    // Guards against Denial-of-Service via oversized multipart file uploads.
    // Enforces a strict 5 MB cap on registration credential proofs.
    """
    if file_obj and hasattr(file_obj, 'size'):
        if file_obj.size > MAX_PROOF_FILE_SIZE_BYTES:
            raise ValidationError(
                f'Uploaded file exceeds maximum limit of {MAX_PROOF_FILE_SIZE_MB}MB '
                f'(current size: {round(file_obj.size / (1024 * 1024), 2)}MB).'
            )


def validate_proof_file_extension(file_obj):
    """
    // Ensures only safe, renderable documents (PDFs and common image formats)
    // are accepted as registration proof, preventing executable upload exploits.
    """
    if file_obj and hasattr(file_obj, 'name'):
        ext = os.path.splitext(file_obj.name)[1].lower()
        if ext not in ALLOWED_PROOF_EXTENSIONS:
            allowed_list = ', '.join(sorted(ALLOWED_PROOF_EXTENSIONS))
            raise ValidationError(
                f'Unsupported file type "{ext}". Allowed formats: {allowed_list}.'
            )
