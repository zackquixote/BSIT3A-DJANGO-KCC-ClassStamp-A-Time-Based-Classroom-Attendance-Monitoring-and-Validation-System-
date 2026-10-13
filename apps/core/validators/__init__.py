"""
# // ==============================================================================
# // KCC CLASSSTAMP - DOMAIN VALIDATORS PACKAGE INITIALISER
# // ==============================================================================
# // Subsystem: Input Sanitization & Domain Rules Validation
# // Description: Re-exports all domain validators and upload security limits
# //   for clean, modular import access across forms, models, and serializers:
# //
# //       from apps.core.validators import (
# //           validate_student_id,
# //           validate_proof_file_size,
# //           validate_proof_file_extension,
# //           validate_academic_year_code,
# //           validate_program_duration,
# //           validate_class_section_code,
# //       )
# //
# // Module layout:
# //   identity_validators.py — Student ID & proof document upload constraints
# //   academic_validators.py — Academic year, program duration & section codes
# // ==============================================================================
"""

from .academic_validators import (
    validate_academic_year_code,
    validate_class_section_code,
    validate_program_duration,
)
from .identity_validators import (
    ALLOWED_PROOF_EXTENSIONS,
    MAX_PROOF_FILE_SIZE_BYTES,
    MAX_PROOF_FILE_SIZE_MB,
    validate_proof_file_extension,
    validate_proof_file_size,
    validate_student_id,
)

__all__ = [
    'ALLOWED_PROOF_EXTENSIONS',
    'MAX_PROOF_FILE_SIZE_MB',
    'MAX_PROOF_FILE_SIZE_BYTES',
    'validate_student_id',
    'validate_proof_file_size',
    'validate_proof_file_extension',
    'validate_academic_year_code',
    'validate_program_duration',
    'validate_class_section_code',
]
