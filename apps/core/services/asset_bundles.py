"""Build the single CSS and JS bundles the templates load.

PythonAnywhere answers one request in ~0.8 s, so the twenty-six render-blocking
stylesheets and scripts used to cost ~4 s before a page was usable. Order is
preserved, so the CSS cascade and script execution order are unchanged.
FontAwesome stays out: its url() paths are relative to its own folder, so
inlining it would break every icon.

`build_if_stale()` runs from CoreConfig.ready() and, under DEBUG, from the
{% bundle_static %} tag, so editing a source file is enough — there is no build
step to remember. `build_assets` exists only to force a rebuild or report
freshness.
"""

import os
import re
from pathlib import Path

from django.conf import settings

# Order copied from templates/theme/base.html — do not reorder.
CSS_SOURCES = [
    'css/fonts.css',
    'css/variables.css',
    'css/base.css',
    'css/sidebar.css',
    'css/components.css',
    'css/auth.css',
    'css/login.css',
    'css/register.css',
    'css/validation.css',
    'css/dashboard.css',
    'css/app.css',
    # Last: the refinement layer that enforces the visual system.
    'css/refine.css',
    # Presentation/demo overlay — stays last so it wins the cascade.
    'css/present-mode.css',
]

JS_SOURCES = [
    'js/core/app_toasts.js',
    'js/core/app_buttons.js',
    'js/core/app_modals.js',
    'js/core/app_confirm.js',
    'js/core/app_audio.js',
    'js/core/app_table_search.js',
    'js/core/app_action_dropdowns.js',
    'js/core/app_session_guard.js',
    'js/core/app_navigation.js',
    'js/core/app_shortcuts.js',
    'js/core/app_password_reset.js',
    'js/core/app_lightbox.js',
    'js/core/app_responsive_tables.js',
    'js/core/service_worker.js',
    'js/core/push_notifications.js',
    'js/core/app_desktop_alerts.js',
]

CSS_OUT = 'css/classstamp.bundle.css'
JS_OUT = 'js/classstamp.core.bundle.js'

BUNDLED_CSS_NAMES = {Path(rel).name for rel in CSS_SOURCES}


class BundleError(Exception):
    pass


def static_dir():
    return settings.BASE_DIR / 'static'


def _css_part(text):
    # The @import-ed modules are already inlined by the bundle; leaving the
    # statements would make the browser re-fetch each one and undo the bundling.
    def keep(line):
        found = re.match(r"\s*@import\s+url\(['\"]?([^'\")]+)", line)
        return not found or Path(found.group(1)).name not in BUNDLED_CSS_NAMES

    return '\n'.join(line for line in text.splitlines() if keep(line))


def _assemble(base, sources, out_rel, transform):
    parts = [f'/* KCC ClassStamp bundle — generated from {len(sources)} sources.'
             f'\n   Sources: {", ".join(sources)} */']
    for rel in sources:
        src = base / rel
        if not src.exists():
            raise BundleError(f'missing bundle source: static/{rel}')
        parts.append(f'/* ---- static/{rel} ---- */\n{transform(src.read_text(encoding="utf-8"))}')
    out = base / out_rel
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + '.tmp')
    tmp.write_text('\n'.join(parts) + '\n', encoding='utf-8')
    # Atomic so a request that renders while this runs never serves a
    # half-written stylesheet.
    os.replace(tmp, out)
    return out


def _is_stale(base, sources, out):
    if not out.exists():
        return True
    out_mtime = out.stat().st_mtime
    return any((base / rel).exists() and (base / rel).stat().st_mtime > out_mtime
               for rel in sources)


_BUNDLES = (
    (CSS_SOURCES, CSS_OUT, _css_part),
    (JS_SOURCES, JS_OUT, lambda text: text),
)


def stale_outputs():
    """Names of the bundles whose sources are newer than the bundle."""
    base = static_dir()
    return [out_rel for sources, out_rel, _ in _BUNDLES
            if _is_stale(base, sources, base / out_rel)]


def build_if_stale():
    """Rebuild only the bundles whose sources changed. Returns the rebuilt names."""
    base = static_dir()
    rebuilt = []
    for sources, out_rel, transform in _BUNDLES:
        out = base / out_rel
        if _is_stale(base, sources, out):
            _assemble(base, sources, out_rel, transform)
            rebuilt.append(out_rel)
    return rebuilt


def build_all():
    """Rebuild both bundles regardless of mtimes. Returns {output: bytes}."""
    base = static_dir()
    written = {}
    for sources, out_rel, transform in _BUNDLES:
        out = _assemble(base, sources, out_rel, transform)
        written[out] = out.stat().st_size
    return written
