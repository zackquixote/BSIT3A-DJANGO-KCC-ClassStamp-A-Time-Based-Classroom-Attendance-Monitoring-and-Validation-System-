"""
WSGI config for mysite project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

# PythonAnywhere: this file is /var/www/<user>_pythonanywhere_com_wsgi.py.
# Required environment (see docs/11_DEPLOY_PYTHONANYWHERE.md):
#   DJANGO_ENV=production
#   DJANGO_SECRET_KEY=<50+ random chars — rotate any key that was ever committed>
#   DJANGO_ALLOWED_HOSTS=<your host>
# Prefer a git-ignored .env next to manage.py (loaded by python-dotenv) so the
# secret is not pasted here. The app refuses to start in production without
# DJANGO_SECRET_KEY and DJANGO_ALLOWED_HOSTS.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')

application = get_wsgi_application()

