"""
# // ==============================================================================
# // KCC CLASSSTAMP - AUDIT EVENT SERIALIZERS
# // ==============================================================================
# // Subsystem: Audit & Compliance Data Serialization
# // Description: Converts AuditEvent records into serialized formats for activity
# //   timelines, system monitoring dashboards, and export reports.
# // ==============================================================================
"""


def serialize_audit_event(event) -> dict:
    """
    // Serializes an AuditEvent record for activity timeline UI or audit logs.
    """
    if not event:
        return {}

    actor = event.actor
    return {
        'id': event.id,
        'actor_id': actor.id if actor else None,
        'actor_name': (actor.get_full_name() or actor.username) if actor else 'System',
        'action': event.action,
        'object_type': event.object_type,
        'object_id': event.object_id,
        'old_value': event.old_value,
        'new_value': event.new_value,
        'reason': event.reason,
        'ip_address': event.ip_address,
        'created_at': event.created_at.isoformat() if hasattr(event, 'created_at') and event.created_at else None,
    }
