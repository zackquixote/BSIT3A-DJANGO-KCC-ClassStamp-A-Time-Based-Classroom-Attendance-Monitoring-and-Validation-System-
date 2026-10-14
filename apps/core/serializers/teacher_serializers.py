"""
# // ==============================================================================
# // KCC CLASSSTAMP - TEACHER & FACULTY SERIALIZERS
# // ==============================================================================
# // Subsystem: Faculty Domain Data Serialization
# // Description: Transforms Teacher Profile and User model instances into structured
# //   dictionaries for JSON API responses, AJAX forms, and client components.
# // ==============================================================================
"""


def serialize_teacher(profile) -> dict:
    """
    // Serializes a Teacher Profile instance including user data, department,
    // and detailed assigned class sections.
    """
    if not profile or not profile.user:
        return {}

    user = profile.user
    classes = []
    if hasattr(profile, 'taught_classes'):
        for c in profile.taught_classes.select_related('subject', 'academic_year').all():
            classes.append({
                'id': c.id,
                'class_code': c.class_code,
                'subject_code': c.subject.code if c.subject else '—',
                'subject_name': c.subject.name if c.subject else '—',
                'academic_year': c.academic_year.name if c.academic_year else '—',
                'capacity': c.capacity,
                'grace_minutes': c.grace_minutes,
                'is_active': c.is_active,
            })

    return {
        'id': profile.id,
        'user_id': user.id,
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'full_name': user.get_full_name() or user.username,
        'department_id': profile.department_id,
        'department_code': profile.department.code if profile.department else '—',
        'department_name': profile.department.name if profile.department else '—',
        'is_active': user.is_active,
        'class_count': getattr(profile, 'class_count', len(classes)),
        'classes': classes,
        'date_joined': user.date_joined.strftime('%b %d, %Y') if user.date_joined else '—',
        'approved_at': profile.approved_at.strftime('%b %d, %Y') if profile.approved_at else '—',
    }


def serialize_teacher_summary(profile) -> dict:
    """
    // Minimal Teacher serialization for dropdown selections and assign forms.
    """
    if not profile or not profile.user:
        return {}

    user = profile.user
    return {
        'id': profile.id,
        'user_id': user.id,
        'name': user.get_full_name() or user.username,
        'department_code': profile.department.code if profile.department else '',
        'is_active': user.is_active,
    }
