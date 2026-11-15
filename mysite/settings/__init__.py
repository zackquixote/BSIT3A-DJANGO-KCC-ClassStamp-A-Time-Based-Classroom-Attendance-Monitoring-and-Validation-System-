"""
Settings package for the mysite project.

The active module is chosen by the ``DJANGO_ENV`` environment variable so the
same ``DJANGO_SETTINGS_MODULE = 'mysite.settings'`` reference keeps working in
``manage.py``/``wsgi.py``:

    DJANGO_ENV=development (default off-server) -> mysite.settings.dev
    DJANGO_ENV=production                       -> mysite.settings.prod

You can also point ``DJANGO_SETTINGS_MODULE`` straight at ``mysite.settings.dev``
or ``mysite.settings.prod`` to be explicit.

When ``DJANGO_ENV`` is unset the choice is made by where the code is running, not
by convenience: a PythonAnywhere web app is a deployment, so it gets ``prod``.
That module refuses to start without ``DJANGO_SECRET_KEY`` and
``DJANGO_ALLOWED_HOSTS``, which is the point — the previous default was ``dev``
on every host, so a server with no environment silently served ``DEBUG = True``,
``ALLOWED_HOSTS = ['*']`` and a committed fallback secret key.

An unrecognised value raises instead of falling back, because a typo
(``productionn``) would otherwise downgrade a deployment to the development
module without anyone noticing.
"""

import os

from django.core.exceptions import ImproperlyConfigured

_IS_PYTHONANYWHERE = (
    'PYTHONANYWHERE_DOMAIN' in os.environ or 'PYTHONANYWHERE_SITE' in os.environ
)

_DJANGO_ENV = os.environ.get('DJANGO_ENV', '').strip().lower()
if not _DJANGO_ENV:
    # // Fail closed on a server: no explicit choice there means production.
    _DJANGO_ENV = 'production' if _IS_PYTHONANYWHERE else 'development'

if _DJANGO_ENV in ('production', 'prod'):
    from .prod import *  # noqa: F401,F403
elif _DJANGO_ENV in ('development', 'dev', 'local'):
    from .dev import *  # noqa: F401,F403
else:
    raise ImproperlyConfigured(
        f"DJANGO_ENV={_DJANGO_ENV!r} is not a known environment; "
        "use 'development' or 'production'."
    )
