"""
# // ==============================================================================
# // KCC CLASSSTAMP - ATTENDANCE POLICY (BANDS & THRESHOLDS)
# // ==============================================================================
# // Subsystem: Policy layer shared by the radar, the student summary and the
# //   admin policy screen.
# // Description:
# //   The CHED 20% rule is institution policy, not a constant of the codebase.
# //   The threshold resolves in this order:
# //     1. SystemPolicy.absence_threshold_percent (set by an administrator)
# //     2. DEFAULT_ABSENCE_THRESHOLD (the CHED baseline)
# //   Bands are derived from the threshold so a 15% policy moves both edges:
# //     SAFE  < threshold/2   |   WATCH < threshold   |   CRITICAL >= threshold
# // References: apps/core/views/helpers/absence_radar.py | docs/02_SECURITY.md
# // ==============================================================================
"""

BAND_SAFE = 'SAFE'
BAND_WATCH = 'WATCH'
BAND_CRITICAL = 'CRITICAL'

BAND_DISPLAY = {
    BAND_SAFE: 'Safe',
    BAND_WATCH: 'Watchlist',
    BAND_CRITICAL: 'FDA Risk',
}

# CHED baseline: a student fails due to absences at 20% unexcused absence.
DEFAULT_ABSENCE_THRESHOLD = 20.0


def absence_threshold_percent():
    """Effective absence threshold, honouring an administrator override."""
    return policy_value('absence_threshold_percent', DEFAULT_ABSENCE_THRESHOLD)


def policy_value(field, default):
    """
    // Resolve a policy field, falling back to the documented default.
    // An absent row (fresh install, test database) means "all defaults", so this
    // must never raise when the table is empty.
    """
    # Imported lazily so this module stays importable during app loading.
    from apps.core.models import SystemPolicy

    try:
        policy = SystemPolicy.objects.first()
    except Exception:
        return default

    if policy is None:
        return default

    value = getattr(policy, field, None)
    if value in (None, ''):
        return default
    return value


def classify_absence_rate(rate, threshold=None):
    """
    // Map an absence percentage to a radar band.
    // Pass `threshold` explicitly when classifying a whole class in a loop, so
    // the policy lookup happens once instead of once per student.
    """
    if threshold is None:
        threshold = absence_threshold_percent()
    threshold = float(threshold)

    if rate < threshold / 2:
        return BAND_SAFE
    if rate < threshold:
        return BAND_WATCH
    return BAND_CRITICAL
