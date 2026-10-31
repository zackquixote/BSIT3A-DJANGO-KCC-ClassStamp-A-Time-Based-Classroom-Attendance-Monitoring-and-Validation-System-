# KCC ClassStamp — System-Wide Audit

**Date:** 2026-10-31
**Baseline:** `main` @ `3411ef5` + uncommitted working-tree changes (see §9)
**Auditor role:** Senior architecture / full-stack / QA / security / database review
**Scope:** Entire Django project (`apps/core`, `apps/users`, `apps/info`, `mysite`, templates,
static assets, migrations, SQL schema), runtime behavior, tests, and security posture.

> **Status labels**
> - **CONFIRMED** — directly proven by source, schema, or configuration inspection.
> - **REPRODUCED** — observed at runtime with a command, test, or HTTP response.
> - **SUSPECTED** — plausible, evidence incomplete.
> - **NOT TESTED** — identified but not validated at runtime.
>
> **Severity:** CRITICAL → HIGH → MEDIUM → LOW.
> **Remediation:** Fixed findings include dated evidence below; execution status is tracked in
> `docs/DEVELOPMENT_TODO.md`.

---

## 1. Executive summary

The system is broadly functional and well tested on the happy path, but it has three
release-blocking problems:

1. **Schema integrity is not reproducible.** The live MariaDB carries 17 triggers and 21 named
   CHECK constraints, but the migration chain provisions only 4 triggers. Tests run on SQLite,
   where none of the business constraints exist. The database is therefore *less protected* on
   any fresh build (CI, new environment, production rebuild) than on this developer machine.
2. **The user-management app writes profiles that the live database rejects.** Creating a
   TEACHER/ADMIN sets `approval_status='APPROVED'`, which violates `chk_cs_profile_shape`; editing
   a role violates the `trg_cs_profile_bu` immutability trigger. User and profile writes are not
   atomic, so failures can leave partial account changes.
3. **Stored XSS in the roster enlistment modal.** Student names and IDs are concatenated into
   `innerHTML` without escaping on an admin page.

A further HIGH item is a **confirmed, reproduced functional break**: the teacher excuse-slip
Approve/Reject buttons build `/teacher/excuse-slips/0/review/<id>/review/`, which resolves to 404.

**Fixes applied on 2026-10-31:** AUD-03, AUD-07, AUD-10, AUD-11, AUD-12, AUD-15, AUD-18,
and AUD-19 are marked `FIXED` in their findings. The verified zero-risk Batch A cleanup under
AUD-26 is also complete. The final gate passed **422/422 tests on MariaDB (569.5 s)** and
**422/422 on SQLite (14.5 s)**, with clean Django and migration-drift checks. Everything else
remains open and, where noted, requires approval.

| Severity | Count | IDs |
|----------|-------|-----|
| CRITICAL | 3 | AUD-01, AUD-02, AUD-03 |
| HIGH | 7 | AUD-04 … AUD-10 |
| MEDIUM | 14 | AUD-11 … AUD-24 |
| LOW | 5 | AUD-25 … AUD-29 |

---

## 2. Verification baseline

All checks below were executed in this environment (Django 4.2.30, Python 3.11, MariaDB 10.4.32,
mysqlclient 2.2.8).

| Check | Result | Evidence |
|-------|--------|----------|
| Test methods in project | **422** | 411 at audit start + 11 regression tests added during remediation |
| Full suite on SQLite (temp settings) | **422 passed** | 14.5 s (final gate) |
| Full suite on MariaDB/XAMPP | **422 passed** | 569.5 s (final gate) |
| Coverage | **84 % at baseline** | 10,067 statements, 1,596 missed (411-test baseline; not re-measured after the 6 added tests) |
| `manage.py check` | **0 issues** | clean |
| `manage.py check --deploy` | Only **W009** (dev SECRET_KEY) | run with a test key; production key not exercised |
| `makemigrations --check` | No changes detected | model state matches migrations |
| Template URL-name resolution | **104/104 resolve, 0 missing** | recursive namespace walk over templates |
| Pending migrations | **`core.0011` only** | `showmigrations core` |
| HTTP smoke | `/` 200, `/dashboard/` 302, `/register/` 200, `/validation/` 302 | unauthenticated `runserver` |
| Live DB triggers | **17** | `information_schema.triggers` |
| Live DB named CHECKs | **21** | `information_schema.check_constraints` |
| Triggers provisioned by migrations | **4** | `0007_core_audit_review_triggers.py` (audit/review only) |

**Key limitation of the test baseline:** the SQLite run exercises Python behavior only. The 13
business triggers and 21 CHECK constraints are MySQL-only (`0007` is guarded by
`vendor != 'mysql'`), so the green suite does **not** prove database-level correctness. AUD-02 is
exactly the class of defect this gap hides.

---

## 3. Findings

### 3.1 CRITICAL

#### AUD-01 — Database integrity rules exist only in a stale SQL dump
- **Status:** CONFIRMED (live schema + migration chain inspected)
- **Severity:** CRITICAL
- **Files:** `apps/core/migrations/0007_core_audit_review_triggers.py`, `sql/bsitcrud.sql`, all models
- **Evidence:** Live `bsitcrud` has 17 triggers (`trg_cs_profile_bi/bu`, `trg_cs_attendance_bi`,
  `trg_cs_session_bi/bu`, `trg_cs_slot_bi/bu`, `trg_cs_class_bi/bu`, `trg_cs_enrollment_bi/bu`,
  `trg_cs_curriculum_bi/bu`, `trg_cs_audit_bu/bd`, `trg_cs_review_bu/bd`) and 21 named
  CHECK constraints (`chk_cs_profile_shape`, `chk_cs_att_*`, `chk_cs_session_*`, …).
  `showmigrations` lists only `0007`, which creates the four audit/review append-only triggers.
  The SQL dump is stale: it contains **zero** occurrences of `tblcs_academic_event`,
  `tblcs_offline_badge`, `tblcs_excuse_slip`, `student_type`, `gender`, or `phone_number`
  (added by migrations 0003/0004/0008).
- **Root cause:** constraints were applied manually through the dump; only append-only triggers
  were later ported to migrations. No test enumerates expected DB objects.
- **Impact:** Any database built from migrations (CI, a new developer, a rebuilt production
  instance) silently loses role shape, attendance, session, slot, enrollment, and curriculum
  invariants. Data corruption that the live DB blocks becomes possible elsewhere.
- **Recommended remediation:** add idempotent migrations (or one management command invoked by
  deploy) for the remaining 13 triggers and the CHECK constraints that MySQL 10.4 can enforce;
  mirror critical invariants with Django `CheckConstraint`/`clean()` so SQLite tests exercise
  them; regenerate or clearly mark `sql/bsitcrud.sql` as historical; add a schema-inventory test.
- **Dependencies:** schema change → **requires approval**; MariaDB 10.4 CHECK handling needs care
  (ADD CONSTRAINT may rebuild tables).
- **Test method:** create a database from migrations only, attempt each forbidden insert/update,
  and assert a database error; run the same on SQLite via Django constraints.

#### AUD-02 — User-management writes violate live profile constraints (non-atomic, partial updates)
- **Status:** CONFIRMED by source + live schema; runtime reproduction not attempted (write guard)
- **Severity:** CRITICAL
- **Files:** `apps/users/views.py:318-400` (create/save), `apps/users/views.py:368-370` (role change)
- **Evidence:**
  - `chk_cs_profile_shape` requires, for TEACHER/ADMIN, `approval_status IS NULL`, and
    `student_number/program_id/year_level/qr_secret IS NULL`, `department_id` populated for
    TEACHER and NULL for ADMIN. The view creates TEACHER/ADMIN profiles with
    `approval_status=APPROVED` plus `approved_by/approved_at`
    (`apps/users/views.py:352-365`), which the CHECK rejects.
  - `trg_cs_profile_bu` raises `SQLSTATE 45000` when `OLD.role <> NEW.role`. The view assigns
    `profile.role = role` at `apps/users/views.py:368-370`, so any role edit fails.
  - `user.save()` runs before profile creation/update with no `transaction.atomic()`, so a
    profile failure leaves the `User` row changed without a profile/audit entry.
  - `user_save_ajax` also does not call `validate_password` for new/updated passwords
    (contrast `user_reset_password_ajax`, which does).
- **Root cause:** the users app was written against generic CRUD assumptions and never
  reconciled with the live profile shape/trigger policy; the SQLite test DB lacks both.
- **Impact:** on the live DB, creating a teacher/admin through `/users/ajax/save/` fails; role
  edits return an integrity error after mutating the User row; no audit trail is written on
  failure. This is both a functional and an integrity defect.
- **Recommended remediation:** wrap the whole operation in `transaction.atomic()`; stop mutating
  `role` (block it with a clear 400, or implement an explicit, audited role-transition service
  that deletes/recreates the profile); set non-student profiles to `approval_status=NULL` and
  clear student-only fields; route provisioning through the existing services; validate
  passwords centrally.
- **Dependencies:** product decision on role changes → **requires approval**.
- **Test method:** on MariaDB, create a teacher and an admin via the endpoint, edit a role, and
  assert 2xx + correct profile shape; inject a profile failure and assert full rollback. Add a
  regression test that runs against MySQL (not only SQLite).

#### AUD-03 — Stored XSS in roster enlistment modal
- **Status:** CONFIRMED by source; browser reproduction not performed
- **Severity:** CRITICAL
- **Files:** `static/js/classes/roster_modal.js:115,128-129,141`;
  `apps/core/views/class_views.py` roster endpoints (~415/453/529)
- **Evidence:** the modal concatenates server data into `innerHTML`:
  `'<option …>' + s.student_name + ' (' + s.student_id …`, and enrolled rows use
  `+ en.student_name +`, `+ en.student_id +`, `+ en.program +`. Error text is also injected.
  Roster serializers emit `user.get_full_name() or username` unescaped. Names are only
  `.strip()`-validated on registration (`registration_form.py`), so `<img onerror=…>` survives.
- **Root cause:** string-built HTML with no output encoding; CSP allows `'unsafe-inline'`, so the
  policy will not neutralize an injected handler.
- **Impact:** a student can register a crafted name, then execute script in an administrator's
  session when the roster modal is opened — account/session takeover, unauthorized enrollment or
  data exfiltration.
- **Recommended remediation:** build nodes with `textContent`/`createElement` (or add a strict
  escape helper and use it for every interpolation, including errors). Do not rely on
  server-side name blocklists alone.
- **Dependencies:** none for the JS fix.
- **Test method:** seed a student named `<img src=x onerror="window.__xss=1">`, open the roster as
  admin in a browser, assert `window.__xss` is undefined and the literal name renders as text.
- **Remediation:** **FIXED 2026-10-31.** Added `escapeHtml()` and applied it to every
  server-supplied field (`student_name`, `student_id`, `program`, `enrolled_at`,
  `enrollment_id`, `profile_id`, error text) in `roster_modal.js`.
  `RosterModalEscapingTests.test_roster_modal_escapes_interpolated_student_fields` passes; Node
  spot-check confirms `<img …>` is emitted encoded. Browser click-through not performed.

---

### 3.2 HIGH

#### AUD-04 — Predictable default password and inconsistent password validation
- **Status:** CONFIRMED
- **Severity:** HIGH
- **Files:** `apps/core/services/student_service.py:155,207`; `apps/core/views/student_views.py:347`;
  `apps/users/views.py` (`user_save_ajax`); `apps/core/views/teacher_views.py` create path
- **Evidence:** CSV import defaults to the shared literal `KccStudent2026!`; the import service
  sets passwords without `validate_password`; the users-app create path and teacher provisioning
  do not validate; only `user_reset_password_ajax` and self-registration call Django validators.
- **Impact:** every imported account without a password shares one known credential; weak
  admin-set passwords bypass policy; no forced-rotation mechanism exists.
- **Recommended remediation:** generate a unique random temporary password per imported account,
  add a `must_change_password` flag (migration) and forced-change flow, and route all
  password-setting paths through one validated service.
- **Dependencies:** migration/business change → **requires approval**.
- **Test method:** import a CSV row without a password and assert uniqueness; submit `123456` to
  every password-setting endpoint and assert rejection; first login forces change.

#### AUD-05 — Credential rotation does not revoke sessions or all derived badges
- **Status:** CONFIRMED
- **Severity:** HIGH
- **Files:** `apps/core/services/credential_service.py:47-116`;
  `apps/core/views/student_views.py:232,301`; `apps/core/services/approval_service.py:109`;
  `apps/core/services/auth_service.py:82`; `apps/core/services/student_service.py:300`;
  `apps/users/views.py:349`
- **Evidence:** `rotate_student_credentials(..., revoke_sessions=False)` defaults to **not**
  revoking sessions and no caller passes `True`. Deactivation toggles `is_active` without
  touching sessions. QR secrets are still generated directly in at least eight places, and
  approval provisioning sets `qr_secret` without deleting unconsumed offline badges.
- **Impact:** after an alleged credential compromise or account deactivation, an attacker's
  existing session and previously issued offline badges remain valid; “reset QR” means different
  things depending on the entry point.
- **Recommended remediation:** define policy (admin-forced reset/deactivation ⇒ revoke sessions
  and unconsumed badges), make `revoke_sessions=True` the default for those flows, and route all
  provisioning/resets through `credential_service`.
- **Dependencies:** behavior change → **requires approval**.
- **Test method:** log in, rotate credentials, assert the old session is rejected and an
  unconsumed badge fails validation; deactivate and assert the same.

#### AUD-06 — Rate limiting and login lockout are process-local / session-local; proxy IP is trusted
- **Status:** CONFIRMED by config/source; exploitation not tested
- **Severity:** HIGH
- **Files:** `mysite/settings/base.py` (no `CACHES`), `apps/core/views/session_views.py:99-112`,
  `apps/core/views/helpers/auth_helpers.py:61-110`, `apps/core/signals/auth_signals.py:28,64`
- **Evidence:** no `CACHES` setting → Django LocMemCache, which is per-process and resets on
  restart. Scan rate limits and TOTP replay tokens use that cache. Login lockout is stored in
  the signed session, so deleting the cookie resets it; the lock is not account-level. Both
  `_client_ip()` and the audit signal take the **first** `X-Forwarded-For` value without
  validating a trusted proxy.
- **Impact:** with more than one worker, scan/replay limits are effectively multiplied; a client
  can bypass lockouts by clearing cookies; audit records can be poisoned with arbitrary IPs.
- **Recommended remediation:** configure a shared cache in production (Redis or database cache),
  add per-account throttling, and gate XFF trust behind an explicit proxy configuration
  (`USE_X_FORWARDED_HOST`-style flag / trusted proxy count).
- **Dependencies:** deployment configuration decision → **requires approval**.
- **Test method:** run two workers and confirm a shared counter; spoof XFF with no proxy and
  assert the recorded IP remains `REMOTE_ADDR`; clear cookies and confirm the account throttle
  still applies.

#### AUD-07 — Teacher excuse-slip Approve/Reject URI is malformed (404)
- **Status:** REPRODUCED
- **Severity:** HIGH
- **Files:** `templates/core/teacher/excuse_slips.html:21`;
  `static/js/teacher/excuse_review.js:38-48`; `apps/core/urls.py:24`
- **Evidence:** the template renders `{% url 'excuse_slip_review_ajax' 0 %}` =
  `/teacher/excuse-slips/0/review/`. JS strips only a trailing `0`/`0/` (`/0\/?$/`), which does
  not match the string ending in `/review/`, so it appends the slip id to the full URL:
  `/teacher/excuse-slips/0/review/1/review/`. Verified with `django.urls.resolve`:
  `…/0/review/1/review/ → 404`, while `/teacher/excuse-slips/1/review/` resolves to
  `excuse_slip_review_ajax`.
- **Impact:** teachers cannot approve or reject excuse slips from the UI.
- **Recommended remediation:** set the data prefix to `/teacher/excuse-slips/` (or have JS strip
  `/0/review/$`). Add a route-composition test.
- **Dependencies:** none.
- **Test method:** browser click on Approve/Reject; assert the slip status changes and a 200 JSON
  response is returned; add a unit test that composes the URL.
- **Remediation:** **FIXED 2026-10-31.** JS now strips the placeholder with
  `/0\/review\/?$/`; Node and `ExcuseReviewUrlContractTests` confirm
  `/teacher/excuse-slips/0/review/` → `/teacher/excuse-slips/<id>/review/` and the composed URL
  resolves to `excuse_slip_review_ajax`. Full suite passes; browser click-through not performed.

#### AUD-08 — Term-scoped export hard-codes 9/18 meetings
- **Status:** CONFIRMED
- **Severity:** HIGH
- **Files:** `apps/core/views/session_views.py:1370-1415`
- **Evidence:** `range_limits = {'midterm': 9, 'finals': 18}` slices sessions by count, not by the
  academic calendar; a term with a different number of meetings produces wrong totals, and
  “finals” appears to include the midterm meetings unless cumulative output is intended.
- **Impact:** attendance reports used for grading/decisions can be wrong for holidays, suspensions,
  makeup classes, or non-standard schedules.
- **Recommended remediation:** derive the boundary from term dates/calendar events or a
  configurable meetings-per-term value; state explicitly whether finals are cumulative; include
  the session count in the export header.
- **Dependencies:** product decision on term definition.
- **Test method:** seed 12 sessions in a term, export midterm/finals, and assert expected counts;
  add a test with a cancelled session and a holiday.

#### AUD-09 — Migration 0011 (upload validators) is uncommitted and unapplied
- **Status:** CONFIRMED
- **Severity:** HIGH
- **Files:** `apps/core/migrations/0011_alter_excuseslip_attachment_and_more.py` (untracked)
- **Evidence:** `showmigrations core` shows `[ ] 0011`; the migration alters
  `ExcuseSlip.attachment` and `Profile.registration_proof` to use `validate_uploaded_document`.
  The migration is Python-state only (no DDL), but until applied the validators are not part of
  the recorded schema, and a fresh checkout without the file loses them from migration history.
- **Impact:** oversized/executable uploads are accepted on the current DB; a new environment built
  from the repository may not include the migration at all.
- **Recommended remediation:** review, commit, and apply the migration; add tests for size,
  extension, magic bytes, and filename sanitization.
- **Dependencies:** **requires approval** to apply a migration.
- **Test method:** `manage.py migrate`; upload oversize/`.svg`/fake-PDF and assert 400.

#### AUD-10 — Open redirect via `Referer` on validation decisions
- **Status:** CONFIRMED code; exploitability SUSPECTED
- **Severity:** HIGH
- **Files:** `apps/core/views/validation_views.py:416-418,458-460,468-470`
- **Evidence:** after approve/reject, the view does
  `if referer and '/validation/' in referer: return redirect(referer)`. A URL such as
  `https://evil.example/validation/` satisfies the substring test.
- **Impact:** a crafted link can send an administrator to an attacker-controlled site immediately
  after a trusted action (phishing/credential capture).
- **Recommended remediation:** validate with
  `django.utils.http.url_has_allowed_host_and_scheme` or redirect only to known internal URL
  names; ignore external `Referer` values.
- **Dependencies:** none.
- **Test method:** POST approve/reject with `Referer: https://evil.example/validation/` and assert
  redirect stays on the local fallback.
- **Remediation:** **FIXED 2026-10-31.** All three decision branches now call
  `_redirect_after_validation()`, which requires a local `/validation/` path and an allowed host.
  `ValidationRedirectSafetyTests` covers external, scheme-relative, and local Referers.

---

### 3.3 MEDIUM

#### AUD-11 — Attendance matrix denominator includes cancelled/closed-invalid sessions
- **Status:** CONFIRMED · **Files:** `apps/core/services/attendance_service.py:27-32`
- Sessions are filtered only by class; no status filter. Cancelled sessions inflate the
  denominator and depress attendance percentages. Fix: include only sessions that count toward
  attendance (at least exclude `CANCELLED`), and state the rule in code. Test with a cancelled
  session fixture.
- **Remediation:** **FIXED 2026-10-31.** Cancelled meetings are excluded before matrix totals and
  rates are calculated. `test_cancelled_sessions_do_not_dilute_attendance_rate` verifies that a
  cancelled meeting does not reduce a 100% attendance rate; the final 422-test suites pass on both
  backends.

#### AUD-12 — Timetable conflict detection ignores academic year and class activity
- **Status:** CONFIRMED · **Files:** `apps/core/services/schedule_service.py:34-74`
- Overlap queries filter weekday/`is_active` only. Archived classes from other academic years
  can produce false teacher/room conflicts. Fix: join `class_obj` and filter active academic year
  / class status. Test with a prior-year slot at the same time.
- **Remediation:** **FIXED 2026-10-31.** Conflict detection now excludes inactive classes and,
  when an academic year is supplied, restricts overlaps to that year. Legacy slot creation and
  wizard save/dry-run paths supply the selected year. Regression tests cover inactive classes and
  prior-year conflicts; the final 422-test suites pass on both backends. Browser dry-run not performed.

#### AUD-13 — Batch promotion is global and non-idempotent
- **Status:** CONFIRMED · **Files:** `apps/core/services/academic_service.py:575-600`
- `promote_students` advances **every** approved student, capped at `years_total`, with no
  academic-year scope, preview, or idempotency guard. A second click can advance students twice
  (until the cap). Fix: scope to the active AY and a batch, add a preview/dry-run and a marker;
  record promoted/skipped counts. **Business decision required.**

#### AUD-14 — Dashboard KPIs use inconsistent query scoping
- **Status:** CONFIRMED inconsistency · **Files:** `apps/core/views/helpers/dashboard_helpers.py`
- Different cards apply different role/approval/year/date filters (e.g. lines ~52-228 vs
  ~414-583 vs ~645+). Numbers can disagree across cards for the same concept. Fix: centralize
  scope helpers and add fixture-based assertions comparing each KPI to a direct ORM query.

#### AUD-15 — Subject toggle contradicts its documented live-class guard and writes no audit
- **Status:** CONFIRMED · **Files:** `apps/core/views/subject_views.py:199-218`
- The docstring promises deactivation is blocked while classes are live and that deactivation is
  reversible; the code flips `is_active` unconditionally and emits no `AuditEvent`. Fix: explicit
  activate/deactivate actions, live-class guard, audit entry with actor/reason. Test both states.
- **Remediation:** **FIXED 2026-10-31.** Deactivation is rejected with HTTP 400 when active
  sections exist in the active academic year. Successful transitions write `SUBJECT_ACTIVATED` or
  `SUBJECT_DEACTIVATED` audit events with old/new values. Regression tests cover the live-class
  guard and both transitions; the final 422-test suites pass on both backends.

#### AUD-16 — Opening a session silently reopens closed sessions and fabricates schedule slots
- **Status:** CONFIRMED · **Files:** `apps/core/views/session_views.py:228-290`
- When no slot exists for today, an ad-hoc `ClassSlot` is created with `room='Assigned Room'`;
  when a session already exists in any non-open state it is reopened in place (audited as
  `REOPEN_CLASS_SESSION`, but with no reason or time limit). Fix: require an explicit reopen
  action with reason and policy limits; mark ad-hoc slots distinctly and avoid placeholder room
  values that later pollute conflict detection. **Behavior decision required.**

#### AUD-17 — TOTP acceptance window and replay TTL are broader than the token period
- **Status:** CONFIRMED values; risk SUSPECTED · **Files:** `apps/core/views/session_views.py:649`,
  `:94-97`
- `valid_window=1` accepts ±30 s; consumed tokens are cached for 120 s. This is a deliberate
  tolerance but should be documented and reviewed against the clock-sync assumptions of student
  devices. Fix: document policy; consider `valid_window=0` with a clock-skew warning if devices
  are managed.

#### AUD-18 — CSV formula guard misses newline-leading cells
- **Status:** CONFIRMED · **Files:** `apps/core/services/export_service.py:28`
- `FORMULA_TRIGGER_PREFIXES = ('=', '+', '@', '\t', '\r')` omits `'\n'`, which some spreadsheet
  versions treat as a formula lead-in. Add `'\n'` and a regression test in
  `apps/core/tests/test_export_safety.py`.
- **Remediation:** **FIXED 2026-10-31.** `'\n'` added to the tuple;
  `SafeSpreadsheetCellTests.test_control_prefixes_are_neutralised` now covers it.

#### AUD-19 — `views.__all__` contains duplicate bare identifiers (latent `TypeError`)
- **Status:** CONFIRMED · **Files:** `apps/core/views/__init__.py:310-311`
- `program_students_csv_export` appears twice, the second time as an object rather than a string.
  Any future `from apps.core.views import *` would fail. Deduplicate and quote.
- **Remediation:** **FIXED 2026-10-31.** The duplicate bare identifier was removed; `__all__` now
  has 115 unique strings. `ViewPackageExportTests` asserts string/unique entries and executes a
  star import.

#### AUD-20 — CSP allows inline scripts; deploy hardening not exercised with production values
- **Status:** CONFIRMED config; residual risk SUSPECTED · **Files:**
  `apps/core/middleware/security.py:18-20`, `mysite/settings/prod.py`
- `script-src` includes `'unsafe-inline'`, which weakens XSS mitigation (and directly affects
  AUD-03). The only `check --deploy` run used a development/test key and reported W009. Long-term:
  move inline handlers to files or nonce-based CSP; validate production settings in CI.

#### AUD-21 — Model-level invariants absent; SQLite tests bypass database shape
- **Status:** CONFIRMED · **Files:** `apps/core/models/profile.py` (no `clean()`/constraints),
  SQL-only rules
- The `Profile` model has no `CheckConstraint` mirroring `chk_cs_profile_shape` or approver rules,
  so the SQLite suite cannot catch violations. Fix alongside AUD-01: add Django constraints for
  vendor-neutral rules and keep MySQL triggers for cross-row rules.

#### AUD-22 — `sql/bsitcrud.sql` is stale and misleading
- **Status:** CONFIRMED · **Files:** `sql/bsitcrud.sql`
- The dump lacks `tblcs_academic_event`, `tblcs_offline_badge`, `tblcs_excuse_slip`, and profile
  columns `student_type`, `gender`, `phone_number`. It cannot be used to rebuild the current
  schema. Regenerate from the live schema or delete/mark as historical.

#### AUD-23 — Registration validation is duplicated and the form is stale
- **Status:** CONFIRMED · **Files:** `apps/core/forms/registration_form.py`,
  `apps/core/views/helpers/auth_helpers.py:116-220`
- The form is only used by tests and lacks current fields; the view helper holds the real rules.
  Consolidate on one validation function to avoid drift. See `DEAD_CODE_REPORT.md` DUP-03.

#### AUD-24 — QR provisioning is duplicated across entry points
- **Status:** CONFIRMED · **Files:** see `DEAD_CODE_REPORT.md` DUP-02
- Eight call sites generate `qr_secret` directly instead of using the credential service. This is
  the root cause behind AUD-05 and makes revocation behavior inconsistent.

---

### 3.4 LOW

#### AUD-25 — Dead teacher password-reset endpoint returns the new password and swallows errors
- **Status:** CONFIRMED · **Files:** `apps/core/views/teacher_views.py:315-356`
- Unreferenced by UI/JS/tests; returns `new_password` in JSON, writes no `AuditEvent`, catches
  `Exception` broadly and prints a traceback. See `DEAD_CODE_REPORT.md` DC-03. Removal requires
  endpoint-removal approval.

#### AUD-26 — Confirmed dead code and unused assets
- **Status:** CONFIRMED · **Files:** see `docs/DEAD_CODE_REPORT.md` §1-2
- Unreferenced templates, legacy JS, unused forms/serializers/validators, unused images, and
  ~1,000 vendored files. No functional impact; cleanup reduces maintenance surface.
- **Remediation:** **BATCH A COMPLETED 2026-10-31.** Removed DC-01, DC-05, DC-06, DC-07, DC-09,
  DC-10, and DC-11 plus unused imports/exports. Post-cleanup reference scans found no remaining
  Python references to removed symbols or project references to removed assets. Full 422-test
  suites pass on both backends. Endpoint, validator-consolidation, vendor/CSS, and product/legal
  candidates remain open.

#### AUD-27 — Privacy consent fields are collected nowhere
- **Status:** CONFIRMED · **Files:** `apps/core/models/profile.py:166,170`
- `privacy_consent_at` is read once; `privacy_notice_version` is never used. This is a
  compliance gap rather than dead code — decide the policy before changing the schema.

#### AUD-28 — Vendor and CSS bloat
- **Status:** CONFIRMED · **Files:** `static/libs/*`, `static/css/*`
- Only Chart.js and FullCalendar are referenced; many selectors are stale. Low performance/maintenance
  impact; verify dynamic class generation before pruning.

#### AUD-29 — Documentation status drift
- **Status:** CONFIRMED · **Files:** `docs/09_MASTER_IMPROVEMENTS_ROADMAP.md`, `docs/task.md`
- Roadmap “Done” statuses describe feature delivery, not regression-tested correctness; e.g.
  session integrity is partially implemented while AUD-16 remains. This audit is the current
  defect source of truth; `DEVELOPMENT_TODO.md` is the execution source of truth.

---

## 4. Verified working surfaces

These were checked and are **not** reported as defects:

- **Authentication/RBAC:** `role_required` and `approved_required` are applied to administrative
  and teacher routes; unauthenticated requests to `/dashboard/` and `/validation/` return 302 to
  login (reproduced via HTTP smoke). Superusers satisfy ADMIN checks.
- **Protected document delivery:** `/media/` is not routed; registration proofs and excuse
  attachments are served only through permission-checked views with `Cache-Control: private,
  no-store` and `nosniff` (`apps/core/views/document_views.py`). URL routing was verified.
- **CSV/Excel injection guard** covers `=`, `+`, `@`, tab, CR, newline, and numeric negatives
  (newline added 2026-10-31, AUD-18). Tests exist in `test_export_safety.py`.
- **Upload validation logic** exists (extension allowlist, 5 MB cap, PDF magic bytes, Pillow
  verify, filename sanitization); activation is pending AUD-09.
- **Session slot weekday integrity guard:** a supplied slot must belong to today’s weekday
  (`session_views.py:200-222`) — this roadmap item is implemented.
- **Section creation has a single path:** `class_save` is edit-only; `class_wizard_save` creates.
- **Offline badge lifecycle:** SHA-256 hashed, single-use, consumed atomically; unconsumed badges
  are revoked by the credential service (but not by every provisioning path — AUD-05).
- **Test suite:** 422 tests pass on both SQLite and MariaDB after remediation; coverage was 84 %
  at the original 411-test baseline and was not re-measured.
- **Migrations:** model state and migration files agree (`makemigrations --check` clean); the only
  pending object is AUD-09.
- **Templates:** all 104 referenced URL names resolve.

---

## 5. Not tested / limitations

- **Multi-worker/concurrent deployment** (relevant to AUD-06) — not exercised.
- **Browser end-to-end** for the full admin/teacher/student UI — only unauthenticated HTTP smoke
  plus Django tests; authenticated browser automation was not authorized in this pass. AUD-03,
  AUD-07, and the AUD-12 wizard dry-run still deserve browser confirmation.
- **MySQL-only behaviors** on SQLite — triggers/CHECKs are not exercised by the 422-test suite.
- **Email delivery** (password reset/teacher email) — no SMTP configured; the dead endpoint’s
  email path is commented out.
- **Backup/restore and storage optimizer end-to-end** — not executed.
- **MariaDB 10.5+/MySQL 8 upgrade path** — Django 5.2 remains blocked (roadmap B-10); not retested.
- **Load/performance, mobile layout, accessibility** — out of scope for this pass.
- **Role-access matrix** — decorators and sampled HTTP responses were verified, not every
  route/role combination exhaustively.

---

## 6. Evidence appendix

```text
# Schema inventory (live MariaDB)
SELECT trigger_name FROM information_schema.triggers WHERE trigger_schema='bsitcrud';
-- 17 rows
SELECT constraint_name FROM information_schema.table_constraints
 WHERE constraint_schema='bsitcrud' AND constraint_type='CHECK';
-- 21 named chk_cs_* constraints

# Profile shape (abridged)
chk_cs_profile_shape:
  STUDENT: approval_status IN (PENDING,APPROVED,REJECTED) AND student fields NOT NULL …
  TEACHER: department_id NOT NULL AND approval_status IS NULL AND student fields NULL …
  ADMIN:   approval_status IS NULL AND all academic fields NULL …

# Role immutability (abridged)
trg_cs_profile_bu: IF OLD.role <> NEW.role THEN SIGNAL SQLSTATE '45000'
                   'A profile role cannot be changed';

# Migration state
core: 0001 … 0010 applied, 0011 pending.
0007 creates only trg_cs_audit_bu/bd and trg_cs_review_bu/bd.

# Excuse review URL (reproduced)
resolve('/teacher/excuse-slips/0/review/1/review/')  -> Resolver404
resolve('/teacher/excuse-slips/1/review/')           -> excuse_slip_review_ajax
```

---

## 7. Working-tree changes covered by this audit

Modified: settings/base.py, urls.py, registration_form.py, rotate_qr_seeds.py, excuse.py,
profile.py, student_serializers.py, services/__init__.py, auth_service.py, export_service.py,
tests/__init__.py, test_auto_close_sessions.py, urls.py, validators, views/* (audit, auth, class,
excuse, session, student), users/views.py, users/tests.py, docs/02_SECURITY.md, several templates
and JS files.

New (untracked): `core/migrations/0011…`, `services/credential_service.py`,
`views/document_views.py`, `tests/test_export_safety.py`, `tests/test_security_hardening.py`,
`tests/test_session_integrity.py`, `docs/task.md`.

The 411-test baseline includes these changes. Uncommitted work is therefore tested but not yet
reviewed/committed; AUD-09 is the only migration not applied.

---

## 8. Change log

| Date | Change |
|------|--------|
| 2026-10-31 | Initial audit; 29 findings; baseline 411/411 tests on SQLite and MariaDB, 84 % coverage |
| 2026-10-31 | Safe fixes applied and verified: AUD-03 (roster XSS), AUD-07 (excuse review URL), AUD-10 (open redirect), AUD-18 (CSV newline), AUD-19 (`__all__`). 417/417 tests pass on both backends; 6 regression tests added |
| 2026-10-31 | AUD-11, AUD-12, and AUD-15 fixed; AUD-26 Batch A cleanup completed. Final gate: 422/422 tests on MariaDB (569.5 s) and SQLite (14.5 s), clean checks and migration-drift scan |
