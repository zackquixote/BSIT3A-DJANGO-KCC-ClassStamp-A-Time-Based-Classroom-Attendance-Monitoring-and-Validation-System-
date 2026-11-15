# Security Audit — 2026-11-14

Four checks were run against the working tree and the live deployment
(`kccclassstamp.pythonanywhere.com`): the deployment check, a dependency CVE
scan, and the two footgun greps. This records what each check reported, the
evidence behind it, and the order of remediation.

The headline: **the production settings module is hardened correctly, but the
live site is not using it.** Everything else is downstream of that.

---

## 1. `manage.py check --deploy`

Run twice — once with production settings, once with development settings as a
control, so "no issues" could be told apart from "the checks did not run".

| Environment | Command | Result |
| :--- | :--- | :--- |
| `DJANGO_ENV=production` | `python manage.py check --deploy` | **0 issues** |
| `DJANGO_ENV=development` | same | 6 warnings: `security.W004` (no HSTS), `W008` (no SSL redirect), `W009` (weak/insecure `SECRET_KEY`), `W012` (no secure session cookie), `W016` (no secure CSRF cookie), `W018` (DEBUG=True) |

So `mysite/settings/prod.py` passes Django's own deployment checklist. The
problem is that production is not loading it.

### Finding 1 — CRITICAL: the live site runs the development settings module

`mysite/settings/__init__.py` selects the module from `DJANGO_ENV` and **defaults
to `development`**:

```python
_DJANGO_ENV = os.environ.get('DJANGO_ENV', 'development').strip().lower()
if _DJANGO_ENV in ('production', 'prod'):
    from .prod import *
else:
    from .dev import *          # DEBUG = True, ALLOWED_HOSTS = ['*']
```

Nothing on the server sets `DJANGO_ENV`, so `mysite/settings/dev.py` is active:
`DEBUG = True`, `ALLOWED_HOSTS = ['*']`, a committed fallback `SECRET_KEY`, and the
console email backend.

Evidence from the live host (read-only requests):

| Probe | Response | What it proves |
| :--- | :--- | :--- |
| `GET /__no_such_path_9f3a__/` | `404`, **34,309 bytes**, body contains `DEBUG = True`, `Page not found at /…`, `Using the URLconf defined in mysite.urls`, `Django tried these URL patterns` | Django's technical 404 renders only when `DEBUG = True` |
| `GET /` | `Set-Cookie: csrftoken=…; HttpOnly; SameSite=Lax` — **no `Secure`** | `CSRF_COOKIE_SECURE = True` (prod) is not in force |
| `GET /` | **no `Strict-Transport-Security`** | `SECURE_HSTS_SECONDS = 31536000` (prod) is not in force |
| `GET /` | `X-Request-ID`, `Permissions-Policy: camera=(self)`, project CSP with `report-uri /api/csp-report/` | It is this codebase, not a stale build |

Consequences, in order of severity:

1. **Any unhandled exception returns a full technical 500 page** — traceback with
   local variables, settings, SQL, and the request environment. That is a
   credential- and schema-disclosure path, not just an information leak.
2. **`SECRET_KEY` may be the committed development key.**
   `dev.py` falls back to `'django-insecure-development-only-key-do-not-use-in-production'`
   whenever `DJANGO_SECRET_KEY` is absent. Password-reset tokens are
   `django.core.signing` payloads salted `RESET_SALT`
   (`apps/core/services/password_reset_service.py:61`), so a known key lets
   anyone mint a valid reset link for any account, admin included, without
   touching email. Confirm by checking whether `DJANGO_SECRET_KEY` exists in the
   PythonAnywhere environment — do not test it by minting a token.
3. **Password-reset mail likely goes to the console.** `dev.py` defaults
   `EMAIL_BACKEND` to the console backend, so reset links land in the server log
   instead of the student's inbox (and tokens sit in logs).
4. `ALLOWED_HOSTS = ['*']` disables host-header validation.
5. Any `500` also breaks the "friendly error page" contract the UI assumes.

### Remediation (in this order)

```python
# /var/www/kccclassstamp_pythonanywhere_com_wsgi.py  — before get_wsgi_application()
import os
os.environ['DJANGO_ENV'] = 'production'
os.environ['DJANGO_SECRET_KEY'] = '<50+ random chars — python -c "import secrets;print(secrets.token_urlsafe(50))">'
os.environ['DJANGO_ALLOWED_HOSTS'] = 'kccclassstamp.pythonanywhere.com'
```

An uncommitted `.env` next to `manage.py` works too (`base.py` loads it via
`python-dotenv`; `.env` is git-ignored). Then:

1. **`python manage.py createcachetable`** — `prod.py` switches `CACHES` to
   `DatabaseCache`; without the table, every cache write raises and login
   lockout, scan anti-replay, and CSP reporting degrade or 500.
2. Reload the web app, then verify: `Strict-Transport-Security` present, the
   random-path 404 is a small page (not the technical one), `csrftoken` carries
   `Secure`, and `/static/…` still serves (with `DEBUG = False` the app no longer
   serves static files itself — PythonAnywhere's static mapping must be right).
3. Re-run the password-reset flow end to end.

**Hardening so this cannot recur — applied.** `mysite/settings/__init__.py` no
longer defaults to development everywhere. An unset `DJANGO_ENV` now follows the
host: PythonAnywhere is treated as a deployment and loads `prod`, local machines
load `dev`, and an unrecognised value (`productionn`) raises instead of silently
downgrading:

```python
_DJANGO_ENV = os.environ.get('DJANGO_ENV', '').strip().lower()
if not _DJANGO_ENV:
    _DJANGO_ENV = 'production' if _IS_PYTHONANYWHERE else 'development'
```

Because `prod.py` raises when `DJANGO_SECRET_KEY` or `DJANGO_ALLOWED_HOSTS` is
missing, the next deploy on PythonAnywhere **will not start** until those exist.
Set them first, run `createcachetable`, then deploy. `.env.example` no longer
ships `DJANGO_ENV=development` as a copyable line, so copying it to a server no
longer pins debug mode.

---

## 2. Dependency CVEs

`python -m pip_audit` fails at import on this machine: the bundled Python ships
neither `venv` nor `ensurepip`, and pip-audit imports `venv` to subclass
`EnvBuilder`. It also builds a throwaway environment to resolve a requirements
file that is not fully pinned, which the missing module makes impossible.

`tools/dep_audit.py` works around both without weakening the result. It resolves
the file with `pip install --dry-run --report` — the same tree a fresh deploy
would install, transitive dependencies included — pins that set to a temporary
lock file, and runs pip-audit against it on the static path:

```
$ python tools/dep_audit.py
resolved 22 packages from requirements.txt (transitive dependencies included)
...
Found 74 known vulnerabilities in 3 packages        # exit code 1
```

74 OSV records collapse to **52 unique advisories** once GHSA/PYSEC duplicates
are grouped by CVE alias. The six dependencies the file does not name (scipy,
joblib, cloudpickle, narwhals, charset-normalizer, threadpoolctl) came back
clean, so nothing hides behind the transitive tree.

| Package | Pinned | Advisories | Fixed in | Exposure here |
| :--- | :--- | :--- | :--- | :--- |
| Django | 4.2.30 | **8** (10 OSV records) | 5.2.15 / 5.2.16 / 5.2.17 / 6.0.6–6.1.1 — **no 4.2.x** | Framework is out of security support |
| Pillow | 12.3.0 | **43** (62 OSV records) | 13.0.0 | **Direct** — parses every uploaded COR/ID photo |
| python-dotenv | 1.1.1 | 1 (`CVE-2026-28684`) | 1.2.2 | Low — local attacker, `set_key()` only |
| asgiref, sqlparse, openpyxl, reportlab, qrcode, PyOTP, mysqlclient, colorama, et_xmlfile, tzdata, django-sslserver | — | 0 | — | — |
| numpy, scikit-learn | ranges (`>=1.26,<3`, `>=1.4,<2`) | not auditable as written; installed 2.5.4 / 1.9.1 clean | — | Pin them |

### Django 4.2.30 — unsupported, not merely behind

Every advisory lists 5.2.x / 6.0.x fixes; there is no 4.2.x release to move to.
Most are not reachable in this app (no GeoDjango/GDAL, no `UpdateCacheMiddleware`
or `CacheMiddleware` in `MIDDLEWARE`, no `DomainNameValidator` fields), so the
practical argument is not the eight CVE records — **it is that the next Django
vulnerability will not be fixed for 4.2 at all.** Plan a 5.2 LTS upgrade (schema
and middleware are already 4.2-shaped; the test suite gives a regression net).

### Pillow 12.3.0 — the one with a live attack surface

43 advisories, all closed by 13.0.0, and the app feeds Pillow untrusted input by
design:

- `apps/core/validators/identity_validators.py:98` — `Image.open(file_obj)` +
  `verify()` on the uploaded proof;
- `apps/core/services/storage_optimizer.py:43` — `Image.open(...).load()` then
  `convert('RGB')` on the same file.

The list includes decompression-bomb bypasses, TIFF/JPEG heap overflows, and an
EPS/Ghostscript argument-injection path to RCE. A crafted image uploaded as a
registration proof is enough to reach them. `pillow==13.0.0` in both
`requirements.txt` and `requirements-pa.txt`, then re-run the upload tests.

### Housekeeping

- `django-sslserver==0.22` is a development HTTPS server, unmaintained since
  2017, imported nowhere in the tree, and has no place in a production
  requirements file — dropped from both files.
- `requirements-pa.txt` still lists `mysqlclient` although the settings switch to
  SQLite on PythonAnywhere; harmless if it installs, noise if it fails.

---

## 3. Footgun greps

| Pattern | Hits | Verdict |
| :--- | :--- | :--- |
| `DEBUG\s*=\s*True` | `mysite/settings/dev.py:10` only | Correct for a dev module — but it is the default module (Finding 1) |
| `SECRET_KEY\s*=` | `base.py:28` (env, default `''`), `dev.py:15` (committed fallback), `auth_views.py:401` (a session key name, not a secret) | Pattern is right; `prod.py` raises when unset. Only the fallback is dangerous, and only when dev settings are live |
| `\.raw\(\|\.extra\(\|cursor\.execute` | **0** | No hand-written SQL anywhere in the app |
| `mark_safe` | `classstamp_icons.py:74` | Safe — interpolates a static `_ICONS` dict and a template-literal class name |
| `\|safe` | 6 | 1 benign (Django's own `help_text`); 5 JSON islands, see below |

### Finding 4 — LOW: `|safe` JSON islands that do not escape `</`

Five templates inject JSON into `<script type="application/json">` with `|safe`,
which turns off autoescaping. `json.dumps` escapes quotes but **not** the
`</script>` sequence, so a value containing `</script><script>…` closes the block.

`apps/core/views/helpers/admin_dashboard.py:239,251` tried to handle this with
`json.dumps(...).replace('</', '<\\')` — **which is itself wrong**: `'<\\'` is a
two-character string, so it substituted `<\` and dropped the slash, turning
`</script>` into `<\script>`. That is not valid JSON (`\s` is not an escape), so
any admin-entered value containing `</` would have made the chart/calendar
islands fail to parse. These had no escaping at all:

- `apps/core/views/class_views.py:382-384` — `departments_json`, `programs_json`,
  `years_json`
- `apps/core/views/class_views.py:2158-2188` — `programs_json`,
  `departments_json`, `existing_rooms_json`

Input is admin-entered (program codes, room names), so this is a stored-XSS
gadget against admin sessions rather than a student-facing hole.

**Fixed** — one serializer now owns the escape, `apps/core/views/helpers/script_json.py`:

```python
def script_json(payload) -> str:
    return json.dumps(payload).replace('</', '<\\/')   # `</` -> `<\/`
```

The wizard's three islands and the dashboard's two both route through it, so the
broken variant is gone rather than copied. `apps/core/tests/test_script_island_escaping.py`
pins the behaviour: no `</script` survives, the payload still round-trips through
`json.loads`, and a program named `</script><script>alert(1)</script>` renders
inside the island instead of closing it.

---

## 4. Priority

1. **Load production settings on PythonAnywhere**, `createcachetable`, verify the
   three header/page checks. (Finding 1 — everything else is minor next to a
   debug page and a possibly-public `SECRET_KEY`.)
2. **`pillow==13.0.0`** and re-run the upload/validation tests. (43 advisories on
   a user-reachable code path.)
3. **Plan Django 5.2 LTS.** 4.2 no longer receives fixes.
4. Pin `numpy` and `scikit-learn`; drop `django-sslserver`; bump `python-dotenv`
   to 1.2.2 for local hygiene.
5. Escape `</` in the `class_views` JSON islands.
6. Harden `mysite/settings/__init__.py` to fail closed on PythonAnywhere.

## 5. Status (2026-11-14)

Applied in the working tree:

| Fix | Where |
| :--- | :--- |
| JSON islands escaped, shared serializer, broken escape corrected | `apps/core/views/helpers/script_json.py`, `class_views.py`, `admin_dashboard.py` |
| Regression tests for the escape (unit + rendered wizard) | `apps/core/tests/test_script_island_escaping.py` |
| Pillow 12.3.0 → **13.0.0** (43 advisories), dotenv → 1.2.2 | `requirements.txt`, `requirements-pa.txt` |
| `numpy` / `scikit-learn` pinned to 2.5.4 / 1.9.1 instead of ranges | `requirements.txt` |
| Settings fail closed on a server; typo'd `DJANGO_ENV` rejected | `mysite/settings/__init__.py`, `.env.example` |
| Tests for all four selection paths (local, unset on PA, explicit prod, typo) | `apps/core/tests/test_settings_environment.py` |

Verified: 67 tests across the wizard, calendar and upload modules pass; the
upload/registration suite (47 tests) also passes against **Pillow 13.0.0** in
isolation, so the decoder bump does not change behaviour the app relies on.

Still open, in priority order:

1. **Environment variables on PythonAnywhere**, then `createcachetable`, then
   deploy — the new settings default means the app refuses to start there until
   `DJANGO_SECRET_KEY` and `DJANGO_ALLOWED_HOSTS` exist.
2. **Django 5.2 LTS migration.** 4.2 receives no further fixes.
3. Full dependency lock (`pip-compile`) so `-r` is reproducible byte-for-byte.

Reproduce with:

```powershell
$env:DJANGO_ENV='production'; python manage.py check --deploy
python tools/dep_audit.py        # pip-audit via the venv-less wrapper; exit 1 on findings
rg -n "DEBUG\s*=\s*True" -g "*.py"
rg -n "SECRET_KEY\s*=" -g "*.py"
rg -n "\.raw\(|\.extra\(|cursor\.execute" -g "*.py"
rg -n "mark_safe|\|\s*safe\b" -g "*.py" -g "*.html"
```
