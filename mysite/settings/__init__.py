"""Settings package for the mysite project.

The active module is chosen by the ``DJANGO_ENV`` environment variable so the
same ``DJANGO_SETTINGS_MODULE = 'mysite.settings'`` reference keeps working in
``manage.py``/``wsgi.py``:

    DJANGO_ENV=development (default) -> mysite.settings.dev
    DJANGO_ENV=production            -> mysite.settings.prod

You can also point ``DJANGO_SETTINGS_MODULE`` straight at ``mysite.settings.dev``
or ``mysite.settings.prod`` to be explicit.
"""

import os

_DJANGO_ENV = os.environ.get('DJANGO_ENV', 'development').strip().lower()

if _DJANGO_ENV in ('production', 'prod'):
    from .prod import *  # noqa: F401,F403
else:
    from .dev import *  # noqa: F401,F403
