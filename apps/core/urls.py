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

    # // Admin: account validation queue (kept off reserved `admin/` Django prefix)
    path('validation/', views.validation_queue, name='validation_queue'),
    path('validation/<str:student_number>/', views.validation_detail, name='validation_detail'),
    path('validation/approve/<str:student_number>/', views.approve_student, name='approve_student'),
    path('validation/reject/<str:student_number>/', views.reject_student, name='reject_student'),

    # // Admin: Student Directory & Masterlist
    path('students/', views.student_directory, name='student_directory'),
    path('students/export-csv/', views.student_directory_export_csv, name='student_directory_export_csv'),
    path('students/import/', views.student_directory_import_csv, name='student_directory_import_csv'),
    path('students/import/sample-template/', views.student_import_sample_csv, name='student_import_sample_csv'),

    # // Admin: Academic Organisation (Departments & Programs)
    path('departments/', views.department_list, name='department_list'),
    path('departments/save/', views.department_save, name='department_save'),
    path('departments/delete/<int:pk>/', views.department_delete, name='department_delete'),

    path('programs/', views.program_list, name='program_list'),
    path('programs/save/', views.program_save, name='program_save'),
    path('programs/delete/<int:pk>/', views.program_delete, name='program_delete'),
]

