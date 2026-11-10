# Production Readiness Checklist (plan task 6.4)

Verified on **2026-11-10** against the repository state that satisfies
Requirements 1–20. Each item lists what ships, how it was verified, and what the
deployer must still do by hand. Where an item is environment-owned (HTTPS,
secrets, scheduler) the application-side behaviour is verified and the operator
step is spelled out.

## 1. HTTPS, secure cookies, HSTS

**Shipped.** `mysite/settings/prod.py` (used when `DJANGO_ENV=production`):

| Setting | Value |
| --- | --- |
| `SECURE_SSL_REDIRECT` | `True` (override with `DJANGO_SECURE_SSL_REDIRECT=False` behind a plain-HTTP proxy) |
| `SESSION_COOKIE_SECURE` | `True` |
| `CSRF_COOKIE_SECURE` | `True` |
| `SECURE_HSTS_SECONDS` | `31536000` with `INCLUDE_SUBDOMAINS` and `PRELOAD` |
| `SECURE_PROXY_SSL_HEADER` | `('HTTP_X_FORWARDED_PROTO', 'https')` |
| `SESSION_COOKIE_HTTPONLY` / `SAMESITE` | `True` / `Lax` |
| `CSRF_COOKIE_HTTPONLY` | `True` |

Development keeps `SESSION_COOKIE_SECURE=False` so `http://127.0.0.1:8000`
works. Production startup fails fast when `DJANGO_SECRET_KEY` or
`DJANGO_ALLOWED_HOSTS` is missing.

**Operator step.** Terminate TLS at the proxy/web server and forward
`X-Forwarded-Proto: https`.

## 2. Shared cache for rate limiting and anti-replay

**Shipped.** Rate limits and anti-replay token consumption live in the Django
cache. Production defaults to `DatabaseCache` (`classstamp_cache`) unless
`DJANGO_CACHE_BACKEND` is set, because `LocMemCache` is per-process and would
silently weaken both controls across workers.

**Operator step.**

```bash
python pmanage.py createcachetable
# optional: DJANGO_CACHE_BACKEND=django.core.cache.backends.redis.RedisCache
#           DJANGO_CACHE_LOCATION=redis://127.0.0.1:6379/1
```

## 3. VAPID keys as deployment secrets

**Shipped.** `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` and `VAPID_ADMIN_EMAIL` are
read from the environment only; no key is generated at startup. The base
template and `PushNotificationService` read the same public key. With keys
missing, delivery is skipped and audited (`PUSH_NOTIFICATION_SKIPPED — VAPID
keys not configured`) while in-app notifications still work.

**Operator step.**

```bash
pip install pywebpush
python -c "from pywebpush import webpush; v = webpush.generate_vapid_keys(); print(v['private_key']); print(v['public_key'])"
# store both in the secret store / environment, never in git
```

## 4. Daily at-risk command

**Shipped.** `apps/core/management/commands/notify_at_risk.py` runs the whole
Req 9 workflow (`--dry-run`, `--threshold`), reuses the canonical absence-radar
threshold, deduplicates one OPEN flag per student/class/academic year, and
resolves flags when the rate drops.

**Operator step (Windows/XAMPP):**

```bat
schtasks /create /tn "ClassStamp At-Risk" /tr "python C:\xampp\htdocs\ClassStamp\pmanage.py notify_at_risk" /sc daily /st 06:00
```

Linux cron:

```cron
0 6 * * * cd /path/to/ClassStamp && python pmanage.py notify_at_risk >> backups/at_risk.log 2>&1
```

Add `--dry-run` to a first manual run and check the audit log before enabling
the schedule.

## 5. Content Security Policy

**Shipped.** `CSP_ENFORCE = True`: responses carry `Content-Security-Policy`
with a per-request nonce on `script-src`, `'unsafe-inline'` only for styles,
`frame-ancestors 'none'`, and `report-uri /api/csp-report/` (bounded, audited as
`CSP_VIOLATION`).

**Verified.** Report-only ran first; every portal page was walked by role with
zero remaining violations, and a rendered-HTML sweep of 40 routes found no
inline `<script>` without a nonce and no inline `on*=` handlers. See
`docs/07_BROWSER_VERIFICATION_2026-11-10.md`.

**Operator step.** Watch `AuditEvent` for `CSP_VIOLATION` after any frontend
change; a new inline script needs `nonce="{{ request.csp_nonce }}"`.

## 6. Migrations applied and backup taken

**Verified 2026-11-10.**

- SQLite: `makemigrations --check --dry-run` → "No changes detected";
  `migrate --check` → exit 0.
- MySQL (`bsitcrud`): `mysqldump` backup written to
  `backups/backup_bsitcrud_20261110_101804.sql` (git-ignored) **before**
  `migrate`; `core.0030_password_history` and `core.0031_anomaly_at_risk_fields`
  applied, `migrate --check` → exit 0.

**Operator step.** Export the database immediately before running `migrate` in
each new environment (`mysqldump` for MySQL, file copy of `db.sqlite3` for
SQLite).

## 7. No secrets in source control

**Verified.** Only `.env.example` is tracked (`.env`, `*.env`, `backups/` and
`*.log` are ignored). No `VAPID_PRIVATE_KEY`, SMTP password or Django secret key
is committed; `DJANGO_SECRET_KEY` and `DB_PASSWORD` are blank placeholders.

## 8. Full automated suite green

The complete SQLite suite must be green in the deployed commit; the run recorded
in `tasks.md` task 6.2 (899 tests) plus the enforced-CSP re-run satisfy this.

## Sign-off summary

| Area | Owner | Status |
| --- | --- | --- |
| Application code and data model | dev team | ready |
| Security defaults (cookies, CSP, rate limits, password policy) | dev team | ready |
| TLS termination, host names, secret store | operator | pending deployment |
| Scheduler entry for at-risk run | operator | pending deployment |
| Database backup + `migrate` on the server | operator | pending deployment |
