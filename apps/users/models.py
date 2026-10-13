"""
// ==============================================================================
// KCC CLASSSTAMP - USERS APP MODELS ARCHITECTURE
// ==============================================================================
// Description: The users application utilizes Django's core authentication model
// (django.contrib.auth.models.User) as the identity provider. User personas,
// institutional affiliations, and RBAC permissions are extended via OneToOne
// relationship in `apps.core.models.Profile` (tblcs_profile).
// References: docs/04_MODELS_REFERENCE.md | apps/core/models.py
// ==============================================================================
"""

from django.db import models

# // Primary user persona models are defined in apps.core.models.Profile
# // to maintain unified constraints with academic entities and MySQL triggers.
