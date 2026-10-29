"""
# // ==============================================================================
# // KCC CLASSSTAMP - DATABASE BACKUP CONTROLLER
# // ==============================================================================
# // Subsystem: Disaster Recovery / Operations (A-15)
# // Description: Admin-only streaming download of a full .sql.gz snapshot.
# // ==============================================================================
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import StreamingHttpResponse
from django.shortcuts import redirect
from django.utils import timezone

from apps.core.decorators import role_required
from apps.core.models import AuditEvent, Profile
from apps.core.services import stream_database_backup


# // ==============================================================================
# // VIEW: Download Full Database Snapshot (/admin/database-backup/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def admin_db_backup(request):
    """
    // Streams a gzip-compressed mysqldump snapshot of the default database.
    // The download itself is recorded in the audit trail (DB_BACKUP_DOWNLOAD).
    """
    try:
        chunks = stream_database_backup()
    except FileNotFoundError as exc:
        messages.error(request, str(exc))
        return redirect('admin_dashboard')

    response = StreamingHttpResponse(chunks, content_type='application/gzip')
    timestamp = timezone.localtime().strftime('%Y%m%d_%H%M%S')
    response['Content-Disposition'] = (
        f'attachment; filename="classstamp_backup_{timestamp}.sql.gz"'
    )

    AuditEvent.objects.create(
        actor=request.user,
        action='DB_BACKUP_DOWNLOAD',
        object_type='Database',
        object_id='default',
        reason='Full database snapshot (.sql.gz) requested by administrator (A-15)',
    )
    return response
