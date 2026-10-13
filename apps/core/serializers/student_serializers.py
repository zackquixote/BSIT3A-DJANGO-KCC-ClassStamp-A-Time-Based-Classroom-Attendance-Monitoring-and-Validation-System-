"""
# // ==============================================================================
# // KCC CLASSSTAMP - STUDENT PROFILE SERIALIZERS
# // ==============================================================================
# // Subsystem: Student Domain Data Serialization
# // Description: Transforms Profile and User model instances for student records
# //   into serializable dictionaries for AJAX tables, modals, and directory APIs.
# // ==============================================================================
"""


def serialize_student_summary(profile) -> dict:
    """
    // Serializes a student Profile for directory listings and search tables.
    """
    if not profile:
        return {}

    user = profile.user
    return {
        'id': profile.id,
        'student_number': profile.student_number,
        'full_name': user.get_full_name() if user else '',
        'first_name': user.first_name if user else '',
        'last_name': user.last_name if user else '',
        'email': user.email if user else '',
        'program_code': profile.program.code if profile.program else None,
        'program_name': profile.program.name if profile.program else None,
        'year_level': profile.year_level,
        'approval_status': profile.approval_status,
        'is_active': user.is_active if user else False,
    }


def serialize_student_detail(profile) -> dict:
    """
    // Full student Profile serialization including approval history and proof URL.
    """
    if not profile:
        return {}

    summary = serialize_student_summary(profile)
    summary.update({
        'approved_by': profile.approved_by.get_full_name() or profile.approved_by.username if profile.approved_by else None,
        'approved_at': profile.approved_at.isoformat() if profile.approved_at else None,
        'approval_note': profile.approval_note,
        'registration_proof_url': profile.registration_proof.url if profile.registration_proof else None,
        'qr_rotated_at': profile.qr_rotated_at.isoformat() if profile.qr_rotated_at else None,
        'created_at': profile.created_at.isoformat() if hasattr(profile, 'created_at') and profile.created_at else None,
    })
    return summary
