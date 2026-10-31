"""
URL configuration for mysite project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
import os
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.http import FileResponse

def favicon_view(request):
    favicon_path = os.path.join(settings.BASE_DIR, 'static', 'img', 'favicon.ico')
    return FileResponse(open(favicon_path, 'rb'), content_type='image/x-icon')

urlpatterns = [
    path('favicon.ico', favicon_view, name='favicon'),
    path('', include('apps.core.urls')),
    path('admin/', admin.site.urls),
    path('users/', include('apps.users.urls')),
    path('info/', include('apps.info.urls')),
]

# Uploaded identity documents are intentionally NOT routed through MEDIA_URL.
# They are served only by the permission-checked views in apps/core/urls.py.