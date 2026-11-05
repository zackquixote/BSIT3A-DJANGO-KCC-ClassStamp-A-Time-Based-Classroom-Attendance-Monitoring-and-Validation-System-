"""Asset URL helpers.

`bundle_static` replaces the hand-maintained `?v=` strings: the version is the
bundle's modification time and size, so a rebuilt bundle is a new URL and
browsers cannot keep serving the stale one.
"""

from pathlib import Path

from django import template
from django.conf import settings
from django.templatetags.static import static

register = template.Library()

_versions = {}


@register.simple_tag
def bundle_static(path):
    if settings.DEBUG:
        # runserver's reloader ignores .css and .js edits, so this is what makes
        # an edit show up without a restart or a build command. It stats the
        # sources and writes only when one is newer.
        from apps.core.services import asset_bundles
        asset_bundles.build_if_stale()
    return f'{static(path)}?v={_version(path)}'


def _version(path):
    info = (Path(settings.BASE_DIR) / 'static' / path).stat()
    token = f'{int(info.st_mtime):x}{info.st_size:x}'
    if settings.DEBUG:
        return token
    if path not in _versions:
        _versions[path] = token
    return _versions[path]
