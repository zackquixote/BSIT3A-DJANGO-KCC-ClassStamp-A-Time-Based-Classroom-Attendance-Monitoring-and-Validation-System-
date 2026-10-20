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
    'apps.core.middleware.AttachProfileMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.core.middleware.DisableBrowserCacheMiddleware',
    'apps.core.middleware.SessionInactivityTimeoutMiddleware',
    'apps.core.middleware.SecurityHeadersMiddleware',
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

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('DB_NAME', 'bsitcrud'),
        'USER': os.environ.get('DB_USER', 'root'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '3306'),
    }
}


# Password validation

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
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

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

LOGIN_REDIRECT_URL = '/home/'
LOGOUT_REDIRECT_URL = '/'

DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'no-reply@classstamp.local')

# Campus Kiosk Security: Inactivity timeout in seconds (30 minutes)
SESSION_INACTIVITY_TIMEOUT = 1800
