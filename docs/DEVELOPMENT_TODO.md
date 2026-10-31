# KCC ClassStamp — Development TODO

**Date:** 2026-10-31
**Source of truth for defects:** `docs/SYSTEM_AUDIT.md` (AUD-xx)
**Source of truth for dead code:** `docs/DEAD_CODE_REPORT.md` (DC/PU/DUP-xx)
**Feature backlog:** `docs/09_MASTER_IMPROVEMENTS_ROADMAP.md` (A-xx/T-xx/B-xx)
**Prior phase plan:** `docs/task.md` — its Phase 1 items map to TODO-P0-05…10 and TODO-P1-08…12;
this file supersedes it for status tracking.

> **Status legend**
> - `TODO` — scoped, ready to implement, no approval needed.
> - `NEEDS APPROVAL` — changes behavior, schema, deployment, or removes functionality.
> - `BLOCKED` — depends on an external change (e.g. database upgrade).
> - `DONE` — implemented **and** verified; requires linked evidence.
>
> No item is `DONE` without linked evidence in §8. The five P0 safe fixes
> (TODO-P0-01/02/03/04/11), three P1 corrections (TODO-P1-01/02/05), and Batch A cleanup
> (TODO-P2-01) are done. Every other item remains open.

---

## 1. Working rules

1. One item per change set; do not opportunistically refactor unrelated files.
2. Preserve UI/UX and business behavior unless the item explicitly changes it.
3. No database structure change without a backup, a tested migration plan, and approval.
4. No deletion without a reference trace recorded in `DEAD_CODE_REPORT.md`.
5. Never mark an item done without both the targeted test and the full suite on SQLite **and**
   MariaDB (when the change touches DB behavior).
6. If a test fails, fix or report it; do not skip or suppress it.
7. Keep `docs/SYSTEM_AUDIT.md`, `docs/DEAD_CODE_REPORT.md`, and this file synchronized in the
   same change set that alters a finding.

---

## 2. P0 — Release blockers

### TODO-P0-01 — Escape roster modal output (stored XSS)
- **Audit ref:** AUD-03 · **Status:** `DONE` (2026-10-31) · **Priority:** P0
- **Problem:** Student names/IDs/program and error text are concatenated into `innerHTML`.
- **Files:** `static/js/classes/roster_modal.js:115,128-129,141`; optional server escape helper.
- **Root cause:** string-built HTML with no output encoding; CSP allows inline scripts.
- **Solution:** build options/rows with `document.createElement` + `textContent`, or apply one
  strict `escapeHtml()` to every interpolated value (including error messages). Do not rely on
  name blocklists.
- **Dependencies:** none.
- **Expected result:** crafted names render as literal text; no script executes in the admin session.
- **Test method:** create a student named `<img src=x onerror="window.__xss=1">`; open the roster
  modal in a browser; assert `window.__xss === undefined` and the literal name is visible; add a
  test that asserts the JS file contains no raw `student_name` concatenation.
- **Verification evidence:** `escapeHtml()` applied to all server-supplied fields in
  `roster_modal.js`; `RosterModalEscapingTests` passes; Node spot-check renders the payload
  encoded; full suite 417/417 on MariaDB and SQLite. Browser click-through not performed.

### TODO-P0-02 — Fix teacher excuse-slip Approve/Reject URL
- **Audit ref:** AUD-07 (reproduced) · **Status:** `DONE` (2026-10-31) · **Priority:** P0
- **Problem:** composed request URL is `/teacher/excuse-slips/0/review/<id>/review/` → 404.
- **Files:** `templates/core/teacher/excuse_slips.html:21`,
  `static/js/teacher/excuse_review.js:38-48`.
- **Root cause:** template emits a full URL with id `0`; JS strips only a trailing `0`.
- **Solution:** set the data prefix to `/teacher/excuse-slips/` or strip `/0/review/$`; keep URL
  construction in one place. Add a test for the composed URL.
- **Dependencies:** none.
- **Expected result:** approve/reject returns 200 JSON and updates the slip status.
- **Test method:** teacher login → click Approve on a pending slip; assert DB status and response;
  `resolve()` test for the composed URL.
- **Verification evidence:** JS strips `/0/review/$`; `ExcuseReviewUrlContractTests` confirms the
  composed `/teacher/excuse-slips/<id>/review/` resolves; Node check returns
  `/teacher/excuse-slips/5/review/`; full suite 417/417 on both backends. Browser click-through
  not performed.

### TODO-P0-03 — Repair `views.__all__` (latent star-import failure)
- **Audit ref:** AUD-19 · **Status:** `DONE` (2026-10-31) · **Priority:** P0
- **Problem:** `program_students_csv_export` appears twice; one entry is an object, not a string.
- **Files:** `apps/core/views/__init__.py:310-311`.
- **Solution:** deduplicate and quote both entries; consider generating `__all__` from the
  explicit imports to prevent drift.
- **Dependencies:** none.
- **Expected result:** `from apps.core.views import *` succeeds; imports remain unchanged.
- **Test method:** `python -c "from apps.core.views import *"`; full suite.
- **Verification evidence:** `__all__` has 115 unique strings, zero non-string entries;
  `ViewPackageExportTests` executes a star import; full suite 417/417 on both backends.

### TODO-P0-04 — Close the CSV formula-injection newline gap
- **Audit ref:** AUD-18 · **Status:** `DONE` (2026-10-31) · **Priority:** P0
- **Problem:** `'\n'` is missing from `FORMULA_TRIGGER_PREFIXES`.
- **Files:** `apps/core/services/export_service.py:28`; `apps/core/tests/test_export_safety.py`.
- **Solution:** add `'\n'`; keep numeric/negative handling unchanged; add a unit test.
- **Dependencies:** none.
- **Expected result:** newline-leading text is prefixed with `'`, numbers stay numeric.
- **Test method:** `python manage.py test apps.core.tests.test_export_safety`.
- **Verification evidence:** `'\n'` added to `FORMULA_TRIGGER_PREFIXES`;
  `test_control_prefixes_are_neutralised` covers it; full suite 417/417 on both backends.

### TODO-P0-05 — Apply and commit migration 0011 (upload validators)
- **Audit ref:** AUD-09 · **Status:** `NEEDS APPROVAL` · **Priority:** P0
- **Problem:** upload validators are not in the applied schema; the migration is untracked.
- **Files:** `apps/core/migrations/0011_alter_excuseslip_attachment_and_more.py`,
  `apps/core/validators/identity_validators.py`.
- **Solution:** review the migration (Python-state only, no DDL), commit it, run `migrate`, and
  test oversize/executable uploads.
- **Dependencies:** approval to apply a migration.
- **Expected result:** both `FileField`s carry `validate_uploaded_document`; invalid uploads 400.
- **Test method:** `manage.py migrate`; upload >5 MB, `.svg`, and a fake PDF; assert rejection;
  upload a valid PDF/JPEG; assert success. Full suite on both backends.
- **Verification evidence:** _pending_

### TODO-P0-06 — Make user-management writes legal and atomic
- **Audit ref:** AUD-02 · **Status:** `NEEDS APPROVAL` · **Priority:** P0
- **Problem:** teacher/admin creation violates `chk_cs_profile_shape`; role edits violate the
  immutability trigger; `User` and `Profile` writes are not atomic; passwords are unvalidated.
- **Files:** `apps/users/views.py:318-400`; `apps/core/models/profile.py`; provisioning services.
- **Root cause:** generic CRUD written without the live profile shape/trigger policy; SQLite tests
  do not enforce either.
- **Solution (preferred):** wrap in `transaction.atomic()`; stop direct role mutation — either
  reject role changes with an explicit 400 or implement an audited “archive old profile, create
  new profile” service; set `approval_status=NULL` and clear student-only fields for
  TEACHER/ADMIN; route provisioning through `auth_service`/`teacher_service`; validate passwords.
- **Dependencies:** **approval** of the role-change policy; coordinate with TODO-P0-07 so a fresh
  DB enforces the same rules.
- **Expected result:** create/edit operations return 2xx only when the resulting row satisfies the
  profile shape; failures roll back completely and are audited.
- **Test method:** MariaDB integration tests for: create teacher, create admin, edit role, failed
  profile insert rollback; assert `Profile` shape and `AuditEvent`. Add the same to SQLite via
  Django constraints (TODO-P1-10).
- **Verification evidence:** _pending_

### TODO-P0-07 — Provision business triggers and CHECK constraints through migrations
- **Audit ref:** AUD-01, AUD-21, AUD-22 · **Status:** `NEEDS APPROVAL` · **Priority:** P0
- **Problem:** 13 of 17 triggers and 21 CHECK constraints exist only in the live DB/manual dump.
- **Files:** `apps/core/migrations/0007…`, `sql/bsitcrud.sql`, `apps/core/models/*.py`.
- **Root cause:** manual schema application; only append-only triggers were ported.
- **Solution:** create idempotent migrations (or a deploy-invoked command) for the remaining
  triggers and MySQL-compatible CHECKs; add Django `CheckConstraint`s/`clean()` for vendor-neutral
  rules so SQLite tests exercise them; regenerate or mark the SQL dump historical; add a
  schema-inventory test.
- **Dependencies:** **approval** (schema change); MariaDB 10.4 table-rebuild behavior; coordinate
  with TODO-P0-06. Django 5.2 upgrade (B-10) remains separately blocked.
- **Expected result:** a database built from migrations alone rejects the same invalid rows as the
  current live DB; SQLite tests catch single-row violations.
- **Test method:** build a scratch DB from migrations only; attempt each forbidden
  insert/update (role change, wrong approval shape, attendance on closed session, teacher as
  marker, weekday mismatch, capacity overflow, etc.); assert database errors; run full suite on
  both backends. Keep a backup before applying to the live DB.
- **Verification evidence:** _pending_

### TODO-P0-08 — One password policy; remove the shared default
- **Audit ref:** AUD-04 · **Status:** `NEEDS APPROVAL` · **Priority:** P0
- **Problem:** CSV import defaults to `KccStudent2026!`; import/users/teacher creation skip
  `validate_password`; no forced change on first login.
- **Files:** `services/student_service.py:155,207`, `views/student_views.py:347`,
  `users/views.py`, `views/teacher_views.py`, front-end registration/reset rules.
- **Solution:** central password service; unique random temp password per import; validate on every
  path; add `must_change_password` (migration) + forced-change page; align front-end rules with
  backend.
- **Dependencies:** **approval** (behavior + migration).
- **Expected result:** no shared/predictable credentials; all password-setting paths enforce the
  same policy.
- **Test method:** import without password → unique values; submit weak passwords to every endpoint;
  first login redirects to the change page until updated.
- **Verification evidence:** _pending_

### TODO-P0-09 — Enforce credential rotation and session revocation end-to-end
- **Audit ref:** AUD-05, AUD-24 · **Status:** `NEEDS APPROVAL` · **Priority:** P0
- **Problem:** `revoke_sessions=False` by default and never set; deactivation leaves sessions
  alive; QR provisioning bypasses the credential service in eight places.
- **Files:** `services/credential_service.py`, `views/student_views.py:232,301`,
  `approval_service.py:109`, `auth_service.py:82`, `student_service.py:300`,
  `users/views.py:349`, seed commands.
- **Solution:** define policy (admin-forced reset/deactivate ⇒ revoke sessions + unconsumed
  badges); route every provisioning/reset through `rotate_student_credentials`; update seed
  commands to use it; revoke stale badges on re-issue.
- **Dependencies:** **approval** of revocation semantics.
- **Expected result:** after reset/deactivation, old sessions and offline badges are rejected;
  one code path owns QR lifecycle.
- **Test method:** log in → rotate → old session rejected; issue badge → rotate → badge rejected;
  deactivate → session rejected. Run on both backends.
- **Verification evidence:** _pending_

### TODO-P0-10 — Shared cache for limits + validated client IP
- **Audit ref:** AUD-06 · **Status:** `NEEDS APPROVAL` · **Priority:** P0
- **Problem:** LocMem cache is per-process; login lockout is session-local; first XFF value is
  trusted and logged.
- **Files:** `mysite/settings/base.py`/`prod.py`, `views/session_views.py:99-112`,
  `views/helpers/auth_helpers.py:61-110`, `signals/auth_signals.py:28,64`.
- **Solution:** configure a shared cache in production (Redis or database cache); add per-account
  login throttling; introduce a trusted-proxy setting and only honor XFF when explicitly enabled;
  log `REMOTE_ADDR` plus validated client IP.
- **Dependencies:** **deployment decision/approval** (new infrastructure or DB cache table).
- **Expected result:** limits hold across workers; lockout survives cookie clearing; audit IPs
  cannot be trivially spoofed.
- **Test method:** two-worker counter test; spoofed XFF test; account lockout test with a fresh
  session.
- **Verification evidence:** _pending_

### TODO-P0-11 — Remove the `Referer` open redirect
- **Audit ref:** AUD-10 · **Status:** `DONE` (2026-10-31) · **Priority:** P0
- **Problem:** any `Referer` containing `/validation/` is used as a redirect target.
- **Files:** `views/validation_views.py:416-418,458-460,468-470`.
- **Solution:** use `url_has_allowed_host_and_scheme` or redirect only to named internal routes.
- **Dependencies:** none.
- **Expected result:** external `Referer` values fall back to the local queue.
- **Test method:** POST with `Referer: https://evil.example/validation/`; assert local redirect.
- **Verification evidence:** `_redirect_after_validation()` enforces a local `/validation/` path
  and allowed host; `ValidationRedirectSafetyTests` covers external, scheme-relative, and local
  Referers; full suite 417/417 on both backends.

### TODO-P0-12 — Make term-scoped export counts data-driven
- **Audit ref:** AUD-08 · **Status:** `NEEDS APPROVAL` · **Priority:** P0
- **Problem:** `{'midterm': 9, 'finals': 18}` fixed counts.
- **Files:** `views/session_views.py:1370-1415`.
- **Solution:** define the term boundary from calendar/term settings or a configurable meeting
  count; clarify whether finals include midterm; include the count in the export header.
- **Dependencies:** **product decision** on term semantics.
- **Expected result:** exports match the actual number of counted meetings.
- **Test method:** seed 12 sessions and a cancelled session; export both ranges; assert counts.
- **Verification evidence:** _pending_

---

## 3. P1 — Data and workflow correctness

### TODO-P1-01 — Exclude non-counting sessions from the attendance matrix
- **Audit ref:** AUD-11 · **Status:** `DONE` (2026-10-31)
- **Files:** `services/attendance_service.py:27-32`
- **Solution/test:** filter to sessions that count (at minimum exclude `CANCELLED`); test with a
  cancelled fixture; document the rule in the service docstring.
- **Verification evidence:** cancelled sessions are excluded before matrix aggregation;
  `test_cancelled_sessions_do_not_dilute_attendance_rate` passes; targeted 128/128 and full
  422/422 suites pass on MariaDB and SQLite.

### TODO-P1-02 — Scope timetable conflicts to the active academic year
- **Audit ref:** AUD-12 · **Status:** `DONE` (2026-10-31)
- **Files:** `services/schedule_service.py:34-74`
- **Solution/test:** join `class_obj` and filter active year/class; test with a prior-year slot and
  an archived class; assert no false conflict.
- **Verification evidence:** inactive classes are always excluded; create/edit and wizard checks
  pass the selected academic year into conflict detection; both new conflict-scope tests pass;
  targeted 128/128 and full 422/422 suites pass on MariaDB and SQLite.

### TODO-P1-03 — Make promotion scoped, previewable, idempotent
- **Audit ref:** AUD-13 · **Status:** `NEEDS APPROVAL`
- **Files:** `services/academic_service.py:575-600`, promotion UI/route
- **Solution/test:** scope to active AY/program, add preview + idempotency marker, audit
  promoted/skipped counts; test double-click and final-year students.

### TODO-P1-04 — Unify dashboard KPI scoping
- **Audit ref:** AUD-14 · **Status:** `TODO`
- **Files:** `views/helpers/dashboard_helpers.py`
- **Solution/test:** central scope helpers; fixture test comparing each KPI to a direct ORM query.

### TODO-P1-05 — Explicit subject activation with live-class guard and audit
- **Audit ref:** AUD-15 · **Status:** `DONE` (2026-10-31)
- **Files:** `views/subject_views.py:199-218`
- **Solution/test:** explicit actions, guard, `AuditEvent`; test both transitions and a live class.
- **Verification evidence:** deactivation returns HTTP 400 while the subject has active classes in
  the active academic year; successful activation/deactivation writes old/new values and actor
  audit events. Both new subject-toggle tests pass; targeted 128/128 and full 422/422 suites pass
  on MariaDB and SQLite.

### TODO-P1-06 — Explicit session reopen and honest ad-hoc slots
- **Audit ref:** AUD-16 · **Status:** `NEEDS APPROVAL`
- **Files:** `views/session_views.py:228-290`
- **Solution/test:** require a reason/time limit for reopen; distinguish ad-hoc slots and avoid
  placeholder rooms; test reopen audit and duplicate-open prevention.

### TODO-P1-07 — Document/validate TOTP tolerance policy
- **Audit ref:** AUD-17 · **Status:** `TODO`
- **Files:** `views/session_views.py:94-97,649`; `docs/02_SECURITY.md`
- **Solution/test:** document ±30 s and 120 s replay TTL; decide whether to use `valid_window=0`;
  test a token at the edge of the window and a replay after TTL.

### TODO-P1-08 — Consolidate registration validation
- **Audit ref:** AUD-23, DUP-03 · **Status:** `TODO`
- **Files:** `forms/registration_form.py`, `views/helpers/auth_helpers.py:116-220`
- **Solution/test:** one validator function; update the form to current fields or retire it; test
  each rule once.

### TODO-P1-09 — Mirror profile invariants as Django constraints
- **Audit ref:** AUD-21 · **Status:** `NEEDS APPROVAL` (pairs with TODO-P0-07)
- **Files:** `models/profile.py`
- **Solution/test:** add `CheckConstraint`s for single-row rules (role/field shape, year level
  bounds where expressible); keep cross-row/approver rules in triggers; assert on SQLite.

### TODO-P1-10 — Regenerate or retire `sql/bsitcrud.sql`
- **Audit ref:** AUD-22 · **Status:** `TODO`
- **Files:** `sql/bsitcrud.sql`
- **Solution/test:** regenerate from the migrated schema or add a header marking it historical;
  verify table/column inventory against migrations.

### TODO-P1-11 — Nonce/inline-script CSP hardening
- **Audit ref:** AUD-20 · **Status:** `NEEDS APPROVAL`
- **Files:** `middleware/security.py`, inline templates
- **Solution/test:** move inline handlers to JS, then drop `'unsafe-inline'` or adopt nonces;
  validate with `check --deploy` under production-like env; browser smoke after the change.

---

## 4. P2 — Dead code cleanup (no behavior change)

| ID | Batch | Items | Approval | Status |
|----|-------|-------|----------|--------|
| TODO-P2-01 | Zero functional risk | DC-05, DC-06, DC-10, DC-11; DC-01 duplicate + imports; DC-07/DC-09; unused imports; AUD-19 | No | **DONE** (2026-10-31) |
| TODO-P2-02 | Endpoint removal | DC-02 (`subject_lookup_json`), DC-03 (`admin_reset_teacher_password`), DC-04 (`validation_queue.html`) | **Yes** | NEEDS APPROVAL |
| TODO-P2-03 | Product/legal | DC-12, PU-01…PU-05, DUP-01/02/04/05/06/07 consolidation | **Yes** | NEEDS APPROVAL |

Details and verified reference traces: `docs/DEAD_CODE_REPORT.md` §1-6.

---

## 5. P3 — Feature backlog (already tracked)

Do not duplicate these here; update their status in `docs/09_MASTER_IMPROVEMENTS_ROADMAP.md`.
Only items that interact with audit findings are listed.

| Roadmap ID | Item | Interaction |
|------------|------|-------------|
| B-11 | Shared cache backend | Same work as TODO-P0-10; implement once |
| B-06 | Environment validation | Should also validate trusted-proxy and cache settings (TODO-P0-10) |
| B-02 | Split `session_views` | Do after AUD-07/08/16 fixes to avoid conflicts |
| B-04 | N+1 query cleanup | Re-measure after TODO-P1-04 |
| B-10 | Django 5.2 upgrade | **BLOCKED** on MariaDB 10.5+ (XAMPP ships 10.4.32) |
| A-11, A-14, A-17, T-08, T-09, T-10, T-11, B-05 | Not built per roadmap | Unchanged by this audit |

---

## 6. Verification protocol

**Before any fix**
1. Record the failing evidence (test, HTTP response, or SQL error) in the item.
2. For DB work: back up `bsitcrud`, then rehearse on a scratch database.

**After each fix**
```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test apps -v 1                  # MariaDB
# SQLite fallback: use a temporary settings module that imports dev and swaps
# DATABASES to a file SQLite DB with an MD5 hasher and temp MEDIA/STATIC roots.
python manage.py test apps -v 1 --settings=<temp_sqlite_settings>
coverage run manage.py test apps && coverage report
```
Plus the item’s targeted test and a browser/HTTP smoke for UI changes.

**Done criteria**
- Targeted test exists and passes.
- Full suite passes on both backends (or the DB-specific reason for skipping is documented).
- No new `check`/`makemigrations` warnings.
- Docs (`SYSTEM_AUDIT.md`, `DEAD_CODE_REPORT.md`, this file) updated in the same change set.
- Evidence link/recorded output attached to the item.

---

## 7. Approval queue

| # | Decision needed | Related |
|---|-----------------|---------|
| 1 | Schema strategy for 13 triggers + CHECK constraints (migration vs deploy command; SQLite mirroring) | TODO-P0-07, P1-09, P1-10 |
| 2 | Role-change policy in Users (block vs archive/recreate) and non-student profile defaults | TODO-P0-06 |
| 3 | Password policy: remove shared default, forced-change flag migration, front-end rules | TODO-P0-08 |
| 4 | Revocation semantics: which admin actions revoke sessions/badges | TODO-P0-09 |
| 5 | Shared cache backend (Redis vs database cache) and trusted-proxy configuration | TODO-P0-10 |
| 6 | Term export semantics (meetings per term; finals cumulative or final-only) | TODO-P0-12 |
| 7 | Session reopen policy and ad-hoc slot rules | TODO-P1-06 |
| 8 | Promotion scope/preview/idempotency semantics | TODO-P1-03 |
| 9 | Removal of dead endpoints and templates | TODO-P2-02 |
| 10 | Privacy consent policy (fields DC-12/PU-03) | TODO-P2-03 |

---

## 8. Progress log

| Date | Item | Status | Evidence |
|------|------|--------|----------|
| 2026-10-31 | Audit baseline | 411/411 tests on SQLite and MariaDB; 84 % coverage; 29 findings documented | `docs/SYSTEM_AUDIT.md` §2 |
| 2026-10-31 | TODO-P0-01 roster XSS | DONE | `RosterModalEscapingTests`; Node spot-check; full suite |
| 2026-10-31 | TODO-P0-02 excuse review URL | DONE | `ExcuseReviewUrlContractTests`; Node URL composition |
| 2026-10-31 | TODO-P0-03 `__all__` repair | DONE | `ViewPackageExportTests` (star import) |
| 2026-10-31 | TODO-P0-04 CSV newline guard | DONE | `test_control_prefixes_are_neutralised` |
| 2026-10-31 | TODO-P0-11 open redirect | DONE | `ValidationRedirectSafetyTests` |
| 2026-10-31 | Full-suite gate after safe fixes | 417/417 MariaDB (684 s) and 417/417 SQLite (18.6 s) | final run |
| 2026-10-31 | TODO-P1-01 attendance matrix | DONE | Cancelled-session regression test; 128/128 targeted tests |
| 2026-10-31 | TODO-P1-02 timetable scoping | DONE | Inactive-class and academic-year conflict tests; wizard passes selected year |
| 2026-10-31 | TODO-P1-05 subject toggle | DONE | Live-class guard and activation/deactivation audit tests |
| 2026-10-31 | TODO-P2-01 Batch A cleanup | DONE | DC-01/05/06/07/09/10/11 removed; zero remaining Python/asset references |
| 2026-10-31 | Final verification gate | **422/422 MariaDB (569.5 s), 422/422 SQLite (14.5 s)** | `check` clean; `makemigrations --check --dry-run` clean; `git diff --check` clean |
| — | All remaining TODO items | Not started / needs approval | — |
