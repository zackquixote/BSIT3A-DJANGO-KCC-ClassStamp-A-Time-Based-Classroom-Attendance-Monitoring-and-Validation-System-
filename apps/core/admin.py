from django.contrib import admin

from apps.core.models.academic import Program
from apps.core.models.profile import Profile


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    """
    Admin interface for Degree Programs.
    Displays program details with student count and quick stats.
    """
    list_display = ('code', 'name', 'department', 'years_total', 'is_active', 'student_count')
    list_filter = ('is_active', 'department')
    search_fields = ('code', 'name', 'department__name')
    ordering = ('code',)
    list_per_page = 25

    def student_count(self, obj):
        """Return count of approved students enrolled in this program."""
        return obj.profiles.filter(
            role=Profile.ROLE_STUDENT,
            approval_status=Profile.APPROVAL_APPROVED,
        ).count()
    student_count.short_description = 'Approved Students'
    student_count.admin_order_field = 'profile_count'
