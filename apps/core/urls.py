from django.urls import path
from . import views

urlpatterns = [
    # // Auth routes
    path('', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('session/keepalive/', views.session_keepalive, name='session_keepalive'),
    path('register/', views.register_view, name='register'),
    path('register/check-availability/', views.check_registration_availability, name='check_registration_availability'),

    # // Smart role-aware dispatcher (redirects to correct role dashboard URL)
    path('dashboard/', views.dashboard_redirect, name='dashboard'),

    # // Role-specific dashboard pages
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('teacher/dashboard/', views.teacher_dashboard, name='teacher_dashboard'),
    path('student/dashboard/', views.student_dashboard, name='student_dashboard'),

    # // Admin: account validation hub & dedicated pending/reviewed pages
    path('validation/', views.validation_hub, name='validation_queue'),
    path('validation/hub/', views.validation_hub, name='validation_hub'),
    path('validation/pending/', views.validation_pending_queue, name='validation_pending_queue'),
    path('validation/reviewed/', views.recently_reviewed_list, name='recently_reviewed_list'),
    path('validation/<str:student_number>/', views.validation_detail, name='validation_detail'),
    path('validation/approve/<str:student_number>/', views.approve_student, name='approve_student'),
    path('validation/reject/<str:student_number>/', views.reject_student, name='reject_student'),
    path('validation/batch/', views.batch_validation_action, name='batch_validation_action'),

    # // Admin: Student Directory & Masterlist
    path('students/', views.student_directory, name='student_directory'),
    path('students/export-csv/', views.student_directory_export_csv, name='student_directory_export_csv'),
    path('students/import/', views.student_directory_import_csv, name='student_directory_import_csv'),
    path('students/import/sample-template/', views.student_import_sample_csv, name='student_import_sample_csv'),

    # // Admin: Academic Organisation — Departments & Programs
    path('departments/', views.department_list, name='department_list'),
    path('departments/save/', views.department_save, name='department_save'),
    path('departments/delete/<int:pk>/', views.department_delete, name='department_delete'),

    path('programs/', views.program_list, name='program_list'),
    path('programs/save/', views.program_save, name='program_save'),
    path('programs/delete/<int:pk>/', views.program_delete, name='program_delete'),
    path('programs/<int:program_id>/students/', views.program_students_per_year, name='program_students_per_year'),
    path('programs/export-csv/<int:program_id>/', views.program_students_csv_export, name='program_students_csv_export'),

    # // Admin: Subject & Curriculum Management
    path('subjects/', views.subject_list, name='subject_list'),
    path('subjects/save/', views.subject_save, name='subject_save'),
    path('subjects/delete/<int:pk>/', views.subject_delete, name='subject_delete'),
    path('subjects/get/<int:pk>/', views.subject_get, name='subject_get'),
    path('subjects/<int:pk>/curriculum/', views.subject_curriculum_list, name='subject_curriculum_list'),
    path('subjects/curriculum/assign/', views.subject_curriculum_assign, name='subject_curriculum_assign'),
    path('subjects/curriculum/remove/<int:pk>/', views.subject_curriculum_remove, name='subject_curriculum_remove'),

    # // Admin: Teacher & Faculty Management
    path('teachers/', views.teacher_list, name='teacher_list'),
    path('teachers/create/', views.teacher_create, name='teacher_create'),
    path('teachers/update/<int:pk>/', views.teacher_update, name='teacher_update'),
    path('teachers/toggle/<int:pk>/', views.teacher_toggle, name='teacher_toggle'),
    path('teachers/delete/<int:pk>/', views.teacher_delete, name='teacher_delete'),
    path('teachers/get/<int:pk>/', views.teacher_get, name='teacher_get'),
    path('teachers/<int:pk>/assign-class/', views.teacher_assign_class_ajax, name='teacher_assign_class_ajax'),
    path('teachers/<int:pk>/unassign-class/<int:class_id>/', views.teacher_unassign_class_ajax, name='teacher_unassign_class_ajax'),
    path('teachers/<int:pk>/analytics/', views.teacher_analytics_json, name='teacher_analytics_json'),

    # // Admin: Academic Year & Term Management
    path('academic-years/', views.academic_year_list, name='academic_year_list'),
    path('academic-years/save/', views.academic_year_save, name='academic_year_save'),
    path('academic-years/set-active/<int:pk>/', views.academic_year_set_active, name='academic_year_set_active'),
    path('academic-years/delete/<int:pk>/', views.academic_year_delete, name='academic_year_delete'),
    path('academic-years/get/<int:pk>/', views.academic_year_get, name='academic_year_get'),

    # // Admin: Class Sections, Schedules & Roster Enrollment
    path('classes/', views.class_list, name='class_list'),
    path('classes/save/', views.class_save, name='class_save'),
    path('classes/toggle/<int:pk>/', views.class_toggle, name='class_toggle'),
    path('classes/<int:class_id>/slot/save/', views.class_slot_save, name='class_slot_save'),
    path('classes/slot/delete/<int:slot_id>/', views.class_slot_delete, name='class_slot_delete'),
    path('classes/<int:class_id>/roster/', views.class_roster_get, name='class_roster_get'),
    path('classes/<int:class_id>/roster/enroll/', views.class_roster_enroll, name='class_roster_enroll'),
    path('classes/roster/remove/<int:enrollment_id>/', views.class_roster_remove, name='class_roster_remove'),
    path('classes/<int:class_id>/matrix/', views.class_attendance_matrix, name='class_attendance_matrix'),

    # // Admin: Security Intelligence & Anomaly Adjudication
    path('admin/anomalies/', views.anomaly_list, name='anomaly_list'),
    path('admin/anomalies/<int:pk>/adjudicate/', views.anomaly_adjudicate, name='anomaly_adjudicate'),
    path('admin/anomalies/bulk/', views.anomaly_bulk_action, name='anomaly_bulk_action'),

    # // Admin: User Account Management
    path('admin/users/<int:user_id>/reset-password/', views.admin_reset_user_password, name='admin_reset_user_password'),

    # // Admin: Audit Log & AJAX API Endpoints
    path('admin/live-stream/', views.admin_live_stream, name='admin_live_stream'),
    path('admin/audit-log/', views.admin_audit_log, name='admin_audit_log'),
    path('admin/audit-log/export-csv/', views.admin_audit_log_export_csv, name='admin_audit_log_export_csv'),
    path('api/admin/activity-feed/', views.admin_activity_feed_json, name='admin_activity_feed_json'),
    path('api/admin/pending-count/', views.admin_pending_count_json, name='admin_pending_count_json'),
    path('api/admin/attendance-chart/', views.admin_attendance_chart_json, name='admin_attendance_chart_json'),
    path('api/subjects/lookup/', views.subject_lookup_json, name='subject_lookup_json'),
    # // Teacher: Classroom Attendance Sessions & Live QR Scanner
    path('teacher/session/open/', views.teacher_session_open, name='teacher_session_open'),
    path('teacher/session/<int:session_id>/scan/', views.teacher_session_scan, name='teacher_session_scan'),
    path('teacher/session/<int:session_id>/close/', views.teacher_session_close, name='teacher_session_close'),
    path('teacher/session/<int:session_id>/summary/', views.teacher_session_summary, name='teacher_session_summary'),
    path('teacher/session/<int:session_id>/override/', views.teacher_manual_override_ajax, name='teacher_manual_override_ajax'),
    path('api/attendance/scan/', views.attendance_scan_api, name='attendance_scan_api'),
]
