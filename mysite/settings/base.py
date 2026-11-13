"""Base settings shared by every environment.

Environment-specific values (secret key, database credentials, hosts) are read
from the process environment, optionally loaded from a local, git-ignored
``.env`` file. See ``.env.example`` for the full list of variables.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Project root: mysite/settings/base.py -> mysite/ -> project root
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load variables from a local .env file (never committed) if present.
load_dotenv(BASE_DIR / '.env')


def _env_list(name, default=''):
    """Return a list built from a comma-separated environment variable."""
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(',') if item.strip()]


# SECURITY WARNING: keep the secret key used in production secret!
# Provided via the DJANGO_SECRET_KEY environment variable (see .env.example).
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '')

DEBUG = False  # overridden per-environment (dev.py / prod.py)

ALLOWED_HOSTS = _env_list('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1')

# Web Push Notifications (VAPID keys) — single source of truth (task 4.1).
# Generate VAPID keys with: python -c "from pywebpush import webpush; print(webpush.generate_vapid_keys())"
# Or use the CLI: vapid --gen
# These are deployment secrets: never generate the private key at application
# startup, and never commit real keys to source control.
VAPID_PRIVATE_KEY = os.environ.get('VAPID_PRIVATE_KEY', '')
VAPID_PUBLIC_KEY = os.environ.get('VAPID_PUBLIC_KEY', '')
VAPID_ADMIN_EMAIL = os.environ.get('VAPID_ADMIN_EMAIL', 'admin@classstamp.local')


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'apps.core',
    'apps.users',
    'apps.info',
]

MIDDLEWARE = [
    'apps.core.middleware.RequestCorrelationIdMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    # NEW: Role-based access control enforced before view decorators
    # (defense in depth). Actual portal prefixes: /admin/, /teacher/, /student/.
    'apps.core.middleware.RoleBasedAccessMiddleware',
    # NEW: Approval status checking for student portal access.
    'apps.core.middleware.ApprovalCheckMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'apps.core.middleware.AttachProfileMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.core.middleware.DisableBrowserCacheMiddleware',
    'apps.core.middleware.SessionInactivityTimeoutMiddleware',
    'apps.core.middleware.SecurityHeadersMiddleware',
    # NEW: API-wide fixed-window rate limiting (last; fail-safe).
    'apps.core.middleware.RateLimitMiddleware',
]

ROOT_URLCONF = 'mysite.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.core.context_processors.pending_approval_count',
            ],
        },
    },
]

WSGI_APPLICATION = 'mysite.wsgi.application'


# Database
# Values come from the environment (see .env.example). Defaults match a local
# XAMPP/MySQL development setup.

_is_pa = 'PYTHONANYWHERE_DOMAIN' in os.environ or 'PYTHONANYWHERE_SITE' in os.environ
_env_sqlite = os.environ.get('USE_SQLITE', '').lower() in ('true', '1', 'yes')
USE_SQLITE = _env_sqlite or (_is_pa and 'DB_HOST' not in os.environ)

if USE_SQLITE:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.environ.get('DB_NAME', 'bsitcrud'),
            'USER': os.environ.get('DB_USER', 'root'),
            'PASSWORD': os.environ.get('DB_PASSWORD', ''),
            # 'localhost' resolves to ::1 first and XAMPP's mysqld listens only on
            # 127.0.0.1, so the handshake waits on the refused attempt: measured
            # 2.05s via localhost vs 0.001s via 127.0.0.1.
            'HOST': os.environ.get('DB_HOST', '127.0.0.1'),
            'PORT': os.environ.get('DB_PORT', '3306'),
            # Reuse the connection so the handshake cost above is not paid again on
            # every request, thread, or worker.
            'CONN_MAX_AGE': int(os.environ.get('DB_CONN_MAX_AGE', '600')),
            'CONN_HEALTH_CHECKS': True,
        }
    }


# Password validation

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 8},
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
    {
        'NAME': 'apps.core.validators.password_validators.CompositionPasswordValidator',
    },
]


# Internationalization

LANGUAGE_CODE = 'en-us'

# KCC ClassStamp operates in the Philippines; attendance timing (present /
# late / absent windows) must be evaluated in local time, not UTC.
TIME_ZONE = 'Asia/Manila'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)

STATIC_URL = '/static/'

STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Collect target for production (populated by `manage.py collectstatic`).
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Uploaded identity documents (COR/ID proofs, excuse attachments) live here.
# This directory must never be served directly by Django or the web server;
# access goes through the permission-checked document views instead.
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# // Auth redirects: the project's login route lives at the site root ('login').
# // LOGIN_URL must be a path (not a name) because SessionInactivityTimeoutMiddleware
# // interpolates it into a query string ("<LOGIN_URL>?next=...").
LOGIN_URL = '/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'

DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'no-reply@classstamp.local')

# // Outbound mail transport.
# // Empty in development, where the console backend is used. Point these at Gmail
# // (or any SMTP relay) to deliver real password-reset links:
# //   EMAIL_HOST=smtp.gmail.com  EMAIL_PORT=587  EMAIL_USE_TLS=True
# //   EMAIL_HOST_USER=<full gmail address>  EMAIL_HOST_PASSWORD=<16-char app password>
# // Gmail requires 2-Step Verification before it will issue an App Password, and
# // rewrites the From address unless it matches the authenticated account.
EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_USE_SSL = os.environ.get('EMAIL_USE_SSL', 'False') == 'True'
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_TIMEOUT = int(os.environ.get('EMAIL_TIMEOUT', '10'))

# Campus Kiosk Security: Inactivity timeout in seconds (30 minutes)
SESSION_INACTIVITY_TIMEOUT = 1800


# Content Security Policy (CSP)
# Protects against XSS and code injection attacks.
# These tuples are the single source of truth consumed by
# SecurityHeadersMiddleware.
# CSP_ENFORCE=True sends Content-Security-Policy; setting it to False ships the
# same policy as Content-Security-Policy-Report-Only (staged rollouts).
# Browser verification (task 6.3, 2026-11-10) found no inline-script violations
# once every portal page had a per-request nonce, so the policy is enforced; it
# still reports violations to /api/csp-report/ so regressions stay auditable.
CSP_ENABLED = True
CSP_ENFORCE = True
CSP_REPORTING = True
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'",)  # Per-request nonce added by middleware; no 'unsafe-inline'
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")  # Inline styles: Django admin + legacy blocks
CSP_IMG_SRC = ("'self'", "data:", "blob:", "https:")
CSP_FONT_SRC = ("'self'", "data:")
CSP_CONNECT_SRC = ("'self'",)
CSP_FRAME_ANCESTORS = ("'none'",)
CSP_BASE_URI = ("'self'",)
CSP_FORM_ACTION = ("'self'",)

# Rate Limiting (RateLimitMiddleware)
# Fixed-window limits per minute on /api/ (including /api/attendance/scan/).
# The stricter per-operator/per-IP scan throttle in session_views stays as an
# additional layer. Production must use a shared cache backend.
RATE_LIMIT_ENABLE = True
RATE_LIMIT_AUTHENTICATED = 100  # requests per minute for authenticated users
RATE_LIMIT_ANONYMOUS = 20  # requests per minute for anonymous users

# Session Security
# Hardened session cookie settings to prevent hijacking
SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript access to session cookie
SESSION_COOKIE_SECURE = False  # Set to True in production (requires HTTPS)
SESSION_COOKIE_SAMESITE = 'Lax'  # Prevent CSRF attacks
SESSION_COOKIE_AGE = 14400  # 4 hours automatic timeout
# Persists the session (and re-sends the cookie) on every request. This does
# NOT rotate the session key. Login-time rotation lives in auth_views
# (cycle_key before the 2FA park and after login()). Do not treat this flag
# as a session-fixation defense.
SESSION_SAVE_EVERY_REQUEST = True

# CSRF Security
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = False  # Set to True in production (requires HTTPS)
CSRF_COOKIE_SAMESITE = 'Lax'

# Stale sign-in/registration pages (common on phones) get a retry redirect
# instead of Django's bare 403 page. See apps.core.views.csrf_failure.
CSRF_FAILURE_VIEW = 'apps.core.views.csrf_failure'

# Clickjacking Protection
X_FRAME_OPTIONS = 'DENY'

# Content Type Sniffing Protection
SECURE_CONTENT_TYPE_NOSNIFF = True

# Browser XSS Protection
SECURE_BROWSER_XSS_FILTER = True

# Referrer Policy
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# Permissions Policy (formerly Feature Policy)
PERMISSIONS_POLICY = {
    'geolocation': [],
    'microphone': [],
    'camera': [],
}

# Notifications
NOTIFICATIONS_ENABLED = os.environ.get('NOTIFICATIONS_ENABLED', 'True').lower() in ('true', '1', 'yes')

# Middleware exemptions
# ROLE_EXEMPT_PREFIXES: paths that skip RoleBasedAccessMiddleware portal gates.
# The root path '/' is always an exact-match exemption (a startswith '/'
# would exempt every URL). Django's /admin/ is NOT exempt: it requires the
# ADMIN role or superuser/staff (Django admin still enforces its own auth).
ROLE_EXEMPT_PREFIXES = [
    '/login/',
    '/logout/',
    '/static/',
    '/media/',
    '/service-worker.js',
    '/favicon.ico',
    '/info/',
    '/users/',
]

# APPROVAL_EXEMPT_PREFIXES: paths that skip ApprovalCheckMiddleware.
APPROVAL_EXEMPT_PREFIXES = [
    '/login/',
    '/logout/',
    '/static/',
    '/media/',
    '/service-worker.js',
    '/favicon.ico',
    '/student/approval-waiting/',
    '/admin/',
]


# Cache
# Anti-replay token consumption and scan throttling are stored in the cache, so
# production must point every worker at the same backend. Development defaults to
# the in-process cache, which is only correct for a single process.
_CACHE_BACKEND = os.environ.get('DJANGO_CACHE_BACKEND', '').strip()
_CACHE_LOCATION = os.environ.get('DJANGO_CACHE_LOCATION', 'classstamp').strip() or 'classstamp'

if _CACHE_BACKEND:
    CACHES = {
        'default': {
            'BACKEND': _CACHE_BACKEND,
            'LOCATION': _CACHE_LOCATION,
            'TIMEOUT': 300,
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': _CACHE_LOCATION,
            'TIMEOUT': 300,
        }
    }
