from django.urls import path
from . import views

urlpatterns = [
    # // Auth routes
    path('', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
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

    # // Admin: Academic Year & Term Management
    path('academic-years/', views.academic_year_list, name='academic_year_list'),
    path('academic-years/save/', views.academic_year_save, name='academic_year_save'),
    path('academic-years/set-active/<int:pk>/', views.academic_year_set_active, name='academic_year_set_active'),
    path('academic-years/delete/<int:pk>/', views.academic_year_delete, name='academic_year_delete'),
    path('academic-years/get/<int:pk>/', views.academic_year_get, name='academic_year_get'),

    # // Admin: Audit Log & AJAX API Endpoints
    path('admin/audit-log/', views.admin_audit_log, name='admin_audit_log'),
    path('api/admin/activity-feed/', views.admin_activity_feed_json, name='admin_activity_feed_json'),
    path('api/admin/pending-count/', views.admin_pending_count_json, name='admin_pending_count_json'),
    path('api/subjects/lookup/', views.subject_lookup_json, name='subject_lookup_json'),
]
