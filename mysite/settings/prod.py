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

# Absolute origin for password-reset emails. Never derived from the request
# Host header: a forged Host plus an open ALLOWED_HOSTS is account takeover.
if not SITE_URL:  # noqa: F405
    real_hosts = [
        h.strip() for h in ALLOWED_HOSTS  # noqa: F405
        if h.strip() and h.strip() not in ('*', 'localhost', '127.0.0.1')
    ]
    if real_hosts:
        SITE_URL = f'https://{real_hosts[0]}'  # noqa: F405
    else:
        raise RuntimeError(
            'DJANGO_SITE_URL or a real DJANGO_ALLOWED_HOSTS entry is required '
            'in production (reset emails must not follow the Host header).'
        )

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

# Anti-replay and scan throttling live in the cache. LocMem is per-process, which
# silently weakens both as soon as the app runs more than one worker — so
# production defaults to the shared database cache unless a real backend is set.
# Run `python manage.py createcachetable` once per environment.
if not os.environ.get('DJANGO_CACHE_BACKEND', '').strip():
    CACHES = {  # noqa: F405
        'default': {
            'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
            'LOCATION': 'classstamp_cache',
            'TIMEOUT': 300,
        }
    }
