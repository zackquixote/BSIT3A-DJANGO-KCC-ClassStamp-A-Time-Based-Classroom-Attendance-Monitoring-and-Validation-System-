from django.contrib import admin
from django.db.models import Count, Q
from apps.core.models.academic import Program
from apps.core.models.attendance import RoomVerification
from apps.core.models.notifications import PushSubscription
from apps.core.models.profile import Profile
from apps.core.models.messaging import Message


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

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.annotate(
            profile_count=Count(
                'profiles',
                filter=Q(
                    profiles__role=Profile.ROLE_STUDENT,
                    profiles__approval_status=Profile.APPROVAL_APPROVED,
                ),
            )
        )

    def student_count(self, obj):
        """Return count of approved students enrolled in this program."""
        return obj.profiles.filter(
            role=Profile.ROLE_STUDENT,
            approval_status=Profile.APPROVAL_APPROVED,
        ).count()
    student_count.short_description = 'Approved Students'
    student_count.admin_order_field = 'profile_count'


@admin.register(RoomVerification)
class RoomVerificationAdmin(admin.ModelAdmin):
    list_display = ('session', 'room', 'verified_by', 'verified_at')
    list_filter = ('verified_at',)
    search_fields = ('room', 'session__slot__class_obj__class_code')
    readonly_fields = ('session', 'room', 'verified_by', 'verified_at')

    def has_add_permission(self, request):
        return False


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'short_endpoint', 'updated_at', 'user_agent')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'endpoint')
    readonly_fields = ('user', 'endpoint', 'p256dh', 'auth', 'endpoint_hash', 'user_agent', 'created_at', 'updated_at')

    @admin.display(description='Endpoint')
    def short_endpoint(self, obj):
        return f'{obj.endpoint[:60]}...' if len(obj.endpoint) > 60 else obj.endpoint

    def has_add_permission(self, request):
        return False


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """
    Admin interface for internal messaging system.
    Displays message details with sender, recipient, and read status.
    """
    list_display = ('subject', 'sender', 'recipient', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('subject', 'body', 'sender__username', 'sender__first_name', 'sender__last_name', 
                     'recipient__username', 'recipient__first_name', 'recipient__last_name')
    readonly_fields = ('sender', 'recipient', 'created_at', 'updated_at', 'read_at')
    ordering = ('-created_at',)
    list_per_page = 50
    
    fieldsets = (
        ('Message Details', {
            'fields': ('sender', 'recipient', 'subject', 'body')
        }),
        ('Status', {
            'fields': ('is_read', 'read_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def has_add_permission(self, request):
        # Messages should be created through the messaging interface, not admin
        return False

