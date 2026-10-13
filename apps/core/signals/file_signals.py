"""
# // ==============================================================================
# // KCC CLASSSTAMP - FILE CLEANUP SIGNALS
# // ==============================================================================
# // Subsystem: Storage & Resource Lifecycle Management
# // Description: Hooks into model deletion lifecycle to clean up uploaded Certificate
# //   of Registration / ID proof files from disk, preventing orphaned storage leaks.
# // ==============================================================================
"""

import os

from django.db.models.signals import post_delete
from django.dispatch import receiver

from apps.core.models import Profile


@receiver(post_delete, sender=Profile)
def cleanup_profile_proof_file(sender, instance, **kwargs):
    """
    // [Signal] Post-delete file cleaner: Removes uploaded ID proof files from disk
    // when a student Profile is deleted, preventing storage leakage.
    """
    if instance.registration_proof:
        try:
            if hasattr(instance.registration_proof, 'path') and os.path.isfile(instance.registration_proof.path):
                os.remove(instance.registration_proof.path)
        except (ValueError, OSError):
            pass
