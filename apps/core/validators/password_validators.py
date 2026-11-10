"""
# // ==============================================================================
# // KCC CLASSSTAMP - PASSWORD COMPOSITION VALIDATOR
# // ==============================================================================
# // Subsystem: Account Security — Password Policy (task 1.6)
# // Description: Requires a minimum length of 8 plus at least one uppercase
# //   letter, one lowercase letter, one digit, and one special character.
# //   Unmet requirements are reported individually so the user sees exactly
# //   what to fix. Django's CommonPassword, NumericPassword, similarity, and
# //   MinimumLength validators remain in AUTH_PASSWORD_VALIDATORS alongside
# //   this class.
# // ==============================================================================
"""

import re

from django.core.exceptions import ValidationError

MIN_PASSWORD_LENGTH = 8


class CompositionPasswordValidator:
    """
    // Password must mix character classes. Specific unmet rules are returned
    // as separate ValidationError messages.
    """

    def validate(self, password, user=None):
        problems = []
        if not password or len(password) < MIN_PASSWORD_LENGTH:
            problems.append(
                f'Password must be at least {MIN_PASSWORD_LENGTH} characters long.'
            )
        if not re.search(r'[A-Z]', password or ''):
            problems.append('Password must contain at least one uppercase letter.')
        if not re.search(r'[a-z]', password or ''):
            problems.append('Password must contain at least one lowercase letter.')
        if not re.search(r'\d', password or ''):
            problems.append('Password must contain at least one digit.')
        if not re.search(r'[^A-Za-z0-9]', password or ''):
            problems.append('Password must contain at least one special character.')
        if problems:
            raise ValidationError(problems)

    def get_help_text(self):
        return (
            'Your password must be at least 8 characters long and include an '
            'uppercase letter, a lowercase letter, a digit, and a special character.'
        )
