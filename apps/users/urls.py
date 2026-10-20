from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    # Page
    path('', views.user_list_page, name='user_list'),
    # AJAX Actions
    path('ajax/list/', views.user_list_ajax, name='user_list_ajax'),
    path('ajax/get/<int:pk>/', views.user_get_ajax, name='user_get_ajax'),
    path('ajax/save/', views.user_save_ajax, name='user_save_ajax'),
    path('ajax/delete/<int:pk>/', views.user_delete_ajax, name='user_delete_ajax'),
    path('ajax/toggle-status/<int:pk>/', views.user_toggle_status_ajax, name='user_toggle_status_ajax'),
    path('ajax/reset-password/<int:pk>/', views.user_reset_password_ajax, name='user_reset_password_ajax'),
    # Export
    path('export-csv/', views.user_export_csv, name='user_export_csv'),
]