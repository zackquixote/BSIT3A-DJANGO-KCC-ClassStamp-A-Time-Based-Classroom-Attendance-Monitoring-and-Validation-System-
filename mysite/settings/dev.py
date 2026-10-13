"""Development settings.

Convenient, insecure-by-default configuration for local work. Do not use in
production. Selected when DJANGO_ENV is unset or 'development'.
"""

from .base import *  # noqa: F401,F403

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# Development-only fallback so the app boots without a .env present. Production
# must supply DJANGO_SECRET_KEY via the environment (see prod.py).
if not SECRET_KEY:  # noqa: F405
    SECRET_KEY = 'django-insecure-development-only-key-do-not-use-in-production'

# Print emails to the console during development.
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
