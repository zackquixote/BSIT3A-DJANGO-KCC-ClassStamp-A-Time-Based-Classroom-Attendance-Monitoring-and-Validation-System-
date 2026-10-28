"""Production settings.

Hardened configuration used when DJANGO_ENV=production. Secrets and hosts MUST
be provided through the environment; the app refuses to start insecurely.
Follows the checklist in docs/02_SECURITY.md.
"""

import os

from .base import *  # noqa: F401,F403

DEBUG = False

# Fail loudly rather than silently running insecurely.
if not SECRET_KEY:  # noqa: F405
    raise RuntimeError('DJANGO_SECRET_KEY must be set in the environment for production.')
if not ALLOWED_HOSTS:  # noqa: F405
    raise RuntimeError('DJANGO_ALLOWED_HOSTS must be set in the environment for production.')

# CSRF trusted origins for HTTPS in production (Django 4+)
CSRF_TRUSTED_ORIGINS = [
    f"https://{h.strip()}"
    for h in os.environ.get('DJANGO_ALLOWED_HOSTS', '').split(',')
    if h.strip()
]

# HTTPS / transport security.
SECURE_SSL_REDIRECT = os.environ.get('DJANGO_SECURE_SSL_REDIRECT', 'True') == 'True'
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
# Trust the X-Forwarded-Proto header set by the reverse proxy / load balancer.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Security headers.
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'

# Cookies.
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

# Real SMTP delivery in production (configure the credentials via environment).
EMAIL_BACKEND = os.environ.get(
    'DJANGO_EMAIL_BACKEND',
    'django.core.mail.backends.smtp.EmailBackend',
)
