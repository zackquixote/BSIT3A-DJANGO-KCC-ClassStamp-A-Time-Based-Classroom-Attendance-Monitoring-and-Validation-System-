# Deploy to PythonAnywhere — 15 November 2026

The security work is on GitHub (`e705739`). This is the order that gets it live
**without** taking the site down.

The new settings **refuse to start** without a secret key and a real host. Set
the environment **before** you pull and reload.

---

## 0. What you need

- PythonAnywhere **Bash console** (Web tab → the console, or a new Bash)
- The project folder (the one with `manage.py` / `pmanage.py`)
- The virtualenv the web app uses (Web tab → *Virtualenv* section)

Everything below is paste-able. Replace `YOUR_PASSWORD_HERE` when you generate
the secret.

---

## 1. Set the environment FIRST

In the Bash console, `cd` into the project folder, then create `.env`
(loaded automatically by `python-dotenv`; this file is git-ignored):

```bash
cd ~/kccclassstamp.pythonanywhere.com   # or your project folder — the one with manage.py

python3 - <<'PY'
from pathlib import Path
secret = __import__('secrets').token_urlsafe(50)
Path('.env').write_text('\n'.join([
    'DJANGO_ENV=production',
    f'DJANGO_SECRET_KEY={secret}',
    'DJANGO_ALLOWED_HOSTS=kccclassstamp.pythonanywhere.com',
    'DJANGO_SITE_URL=https://kccclassstamp.pythonanywhere.com',
    'DJANGO_SECURE_SSL_REDIRECT=True',
    '',
]), encoding='utf-8')
print('wrote .env')
PY
```

Do **not** commit `.env`. Confirm:

```bash
ls -la .env
git check-ignore .env && echo "ignored — good"
```

If you already have a `.env` (email, MySQL), **append** these lines instead of
overwriting the file.

---

## 2. Pull the code

```bash
git status --short          # should be clean or only .env
git pull origin main
git log --oneline -1        # expect e705739 security(auth, settings): ...
```

If you have local edits on PA, stash them first: `git stash && git pull && git stash pop`.

---

## 3. Install dependencies (the same virtualenv as the web app)

Find the virtualenv on the **Web** tab (e.g. `/home/YOU/.virtualenvs/venv`):

```bash
# adjust if your virtualenv path is different
source /home/$USER/.virtualenvs/venv/bin/activate

pip install -r requirements-pa.txt --upgrade
# If this environment also runs predictive analytics, use requirements.txt instead.
```

`requirements-pa.txt` is the slim PA file (no numpy/scikit-learn). Pillow is now
**13.0.0**; python-dotenv **1.2.2**; `django-sslserver` is gone.

---

## 4. Database: backup, migrate, cache table

```bash
# backup first (SQLite is the PA default)
cp db.sqlite3 "backups/db.sqlite3.$(date +%Y%m%d_%H%M)" 2>/dev/null || cp db.sqlite3 backups/db.sqlite3.bak

python pmanage.py migrate --check    # should exit 0 if already current
python pmanage.py migrate            # apply anything pending
python pmanage.py createcachetable   # REQUIRED: prod uses DatabaseCache
```

If you use MySQL on PA instead of SQLite, export with `mysqldump` before
`migrate`, and set `DB_HOST` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` in `.env`
so the app does not fall back to SQLite.

---

## 5. WSGI file (only if you do not use `.env`)

If you prefer environment variables in the WSGI file instead of `.env`, open

```
/var/www/kccclassstamp_pythonanywhere_com_wsgi.py
```

and put this **above** `get_wsgi_application()`:

```python
import os
os.environ['DJANGO_ENV'] = 'production'
os.environ['DJANGO_SECRET_KEY'] = 'PASTE_THE_SAME_SECRET_AS_IN_ENV'
os.environ['DJANGO_ALLOWED_HOSTS'] = 'kccclassstamp.pythonanywhere.com'
os.environ['DJANGO_SITE_URL'] = 'https://kccclassstamp.pythonanywhere.com'
```

`.env` **and** WSGI both work. Do not set conflicting secrets in both places.

---

## 6. Reload and verify

Web tab → **Reload**.

Then check, in order (any fail → look at the error log before the next step):

| Check | Expected |
| :--- | :--- |
| `GET /` | 200, sign-in page |
| `GET /this-page-does-not-exist/` | **small** 404 (not the 34 KB debug page) |
| Response headers | `Strict-Transport-Security` present |
| Cookies | `csrftoken` has `Secure` |
| `GET /robots.txt` | 200, `Disallow: /admin/` |
| `GET /.well-known/security.txt` | 200 |
| `GET /api/notifications/unread/` | `401` JSON |
| `GET /static/css/classstamp.bundle.css` | 200 (if 404: fix the static mapping on the Web tab) |

```bash
curl -sI https://kccclassstamp.pythonanywhere.com/robots.txt | head -5
curl -sI https://kccclassstamp.pythonanywhere.com/this-page-does-not-exist/ | head -5
curl -s https://kccclassstamp.pythonanywhere.com/robots.txt
```

A 34 KB 404 still means `DEBUG=True` — stop and re-check `.env` / WSGI / reload.

---

## 7. After the reload (optional, not required to go live)

```bash
# Password-reset email (else reset links only print to the log)
# DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
# EMAIL_HOST=smtp.gmail.com
# EMAIL_PORT=587
# EMAIL_USE_TLS=True
# EMAIL_HOST_USER=classstamp.kcc@gmail.com
# EMAIL_HOST_PASSWORD=<gmail app password>
# DEFAULT_FROM_EMAIL=classstamp.kcc@gmail.com

# Push notifications (optional; in-app notifications work without them)
# VAPID_PRIVATE_KEY=...
# VAPID_PUBLIC_KEY=...
```

At-risk daily run (Linux cron on PA):

```cron
0 6 * * * cd /home/YOU/kccclassstamp.pythonanywhere.com && python pmanage.py notify_at_risk >> backups/at_risk.log 2>&1
```

---

## 8. If the site is down after reload

1. Web tab → *Error log* (last 50 lines).
2. `RuntimeError: DJANGO_SECRET_KEY must be set` → `.env` / WSGI was not picked up.
3. `Table 'classstamp_cache' doesn't exist` → you skipped `createcachetable`.
4. Static 404s → Web tab → *Static files* mapping must point at the project
   `static/` folder (`/static/` → `/home/YOU/.../static`).
5. Still debug 404 → the web app did not reload, or `.env` is in the wrong folder.

Rollback if needed:

```bash
git log --oneline -5
git checkout 5199114 -- .
# reload the web app
```

---

## 9. What must NOT go to production

Do **not** run `tools/pentest/attacks.py` or `tools/pentest/sweep.py` against
the live URL. They are for the local throwaway database. `tools/dep_audit.py`
is safe anywhere (it only reads `requirements*.txt`).
