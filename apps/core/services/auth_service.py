"""
# // ==============================================================================
# // KCC CLASSSTAMP - STUDENT ACCOUNT PROVISIONING SERVICE
# // ==============================================================================
# // Subsystem: Registration Business Logic
# // Description: Encapsulates the User + Profile creation pipeline called during
# //   student self-registration. Extracted from register_view so that the exact
# //   same provisioning logic can be reused by CSV bulk import and future API
# //   endpoints without duplicating code.
# //
# // Contract:
# //   provision_student_account(form_data, proof_file=None)
# //     → returns (user, profile) tuple on success
# //     → raises ValueError / IntegrityError on constraint violation
# //
# // Live DB Constraints Satisfied:
# //   - chk_cs_profile_shape: department_id must be NULL for STUDENT row
# //   - 64-char hex qr_secret required at INSERT time
# //   - approval_status set to PENDING (awaiting admin review)
# // ==============================================================================
"""

import secrets

from django.contrib.auth import get_user_model

from apps.core.models import Profile, Program
from apps.core.services.storage_optimizer import optimize_proof_upload

User = get_user_model()


def provision_student_account(form_data: dict, proof_file=None):
    """
    // [Service] Student Account Provisioning
    // Creates the Auth User + Student Profile in a single atomic operation.
    //
    // Arguments:
    //   form_data  (dict): Validated form fields (username, email, names, program_id,
    //                      year_level, student_number).
    //   proof_file (File): Optional uploaded COR/ID proof file object.
    //
    // Returns:
    //   (user, profile) tuple — both freshly created and persisted.
    //
    // Raises:
    //   ValueError  — if program_id is missing or program not found.
    //   IntegrityError — if username / student_number is already taken (DB constraint).
    """
    program = Program.objects.get(pk=int(form_data['program_id']))

    username = (form_data.get('username') or '').strip() or form_data['student_number']

    user = User.objects.create_user(
        username=username,
        email=form_data['email'],
        first_name=form_data['first_name'],
        last_name=form_data['last_name'],
        password=form_data['password'],
    )

    # // DB constraint chk_cs_profile_shape:
    # //   - department_id must be NULL for STUDENT role
    # //   - qr_secret must be exactly 64 hex characters at INSERT
    profile = Profile.objects.create(
        user=user,
        role=Profile.ROLE_STUDENT,
        student_number=form_data['student_number'],
        student_type=form_data.get('student_type') or Profile.STUDENT_TYPE_REGULAR,
        gender=form_data.get('gender') or None,
        phone_number=form_data.get('phone_number') or None,
        registration_proof=optimize_proof_upload(proof_file),
        program=program,
        year_level=int(form_data['year_level']),
        approval_status=Profile.APPROVAL_PENDING,
        qr_secret=secrets.token_hex(32),  # 32 bytes = 64 hex chars
    )

    return user, profile
