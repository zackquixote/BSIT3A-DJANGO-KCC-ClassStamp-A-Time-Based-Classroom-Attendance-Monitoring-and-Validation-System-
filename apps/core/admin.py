from django.contrib import admin
from django.db.models import Count
from django.urls import path
from django.contrib.auth.decorators import login_required
from apps.core.decorators.rbac import role_required

from apps.core.models.academic import Program, Department
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


@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def program_students_per_year(request, program_id):
    """
    Returns a list of students grouped by year level for the given program.
    Used by the admin detail view when clicking on a program name.
    """
    program = Program.objects.get(id=program_id)

    # Group approved students by year level
    students_by_year = (
        Profile.objects
        .filter(role=Profile.ROLE_STUDENT, program=program, approval_status=Profile.APPROVAL_APPROVED)
        .values('year_level')
        .annotate(count=Count('id'))
        .order_by('year_level')
    )

    # Get student names per year for display
    students_detail = (
        Profile.objects
        .filter(role=Profile.ROLE_STUDENT, program=program, approval_status=Profile.APPROVAL_APPROVED, year_level__isnull=False)
        .values('year_level', 'user__first_name', 'user__last_name', 'user__username', 'student_number')
        .order_by('year_level', 'user__first_name')
    )

    return {
        'program': program,
        'students_by_year': students_by_year,
        'students_detail': students_detail,
        'total_students': sum(s['count'] for s in students_by_year),
    }