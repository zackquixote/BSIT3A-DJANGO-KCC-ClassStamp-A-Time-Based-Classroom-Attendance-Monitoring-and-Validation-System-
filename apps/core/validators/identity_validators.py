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
IMAGE_PROOF_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
MAX_PROOF_FILE_SIZE_MB = 5
MAX_PROOF_FILE_SIZE_BYTES = MAX_PROOF_FILE_SIZE_MB * 1024 * 1024
PDF_MAGIC_BYTES = b'%PDF-'


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


def validate_proof_file_content(file_obj):
    """
    // Validates the actual bytes of an uploaded document, not just its name.
    // PDFs must begin with the %PDF- signature; raster images must decode as a
    // real image through Pillow. This blocks renamed executables and HTML files
    // disguised as images.
    """
    if not file_obj or not hasattr(file_obj, 'read'):
        return

    name = getattr(file_obj, 'name', '') or ''
    ext = os.path.splitext(name)[1].lower()

    try:
        file_obj.seek(0)
        header = file_obj.read(5)
        file_obj.seek(0)
    except (AttributeError, OSError, ValueError):
        return

    if ext == '.pdf':
        if header != PDF_MAGIC_BYTES:
            raise ValidationError('The uploaded PDF is not a valid PDF document.')
        return

    if ext in IMAGE_PROOF_EXTENSIONS:
        try:
            from PIL import Image
        except ImportError:  # pragma: no cover - Pillow is pinned in requirements.txt
            return

        try:
            file_obj.seek(0)
            with Image.open(file_obj) as image:
                image.verify()
        except Exception:
            # Pillow raises several exception types for malformed images; at this
            # validation boundary they all mean the same thing to the user.
            raise ValidationError('The uploaded image is not a valid image file.')
        finally:
            try:
                file_obj.seek(0)
            except (AttributeError, OSError, ValueError):
                pass


def validate_uploaded_document(file_obj):
    """
    // Combined upload guard used by model fields, forms, and service functions:
    // size cap, extension allowlist, and magic-byte/content verification.
    """
    validate_proof_file_size(file_obj)
    validate_proof_file_extension(file_obj)
    validate_proof_file_content(file_obj)
