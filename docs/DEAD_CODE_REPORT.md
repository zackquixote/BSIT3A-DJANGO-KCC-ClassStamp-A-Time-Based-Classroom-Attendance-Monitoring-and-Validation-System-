# KCC ClassStamp — Dead Code & Duplication Report

**Date:** 2026-10-31
**Scope:** Working tree at commit `3411ef5` plus all uncommitted changes
**Method:** AST symbol inventory of `apps/` and `mysite/`; reference tracing across Python,
templates, `static/js`, URL configuration, management-command discovery, admin registration,
and settings. Claims below were re-verified with targeted `grep`/read where marked.
**Constraint:** Only the verified zero-risk Batch A items have been removed. Routed endpoints,
models, and product/legal items remain untouched pending the approvals recorded below.

> Status legend
> - **CONFIRMED** — no reference found after full trace; safe to retire.
> - **POTENTIAL** — no reference found, but product/legal/compliance intent is unclear.
> - **DUPLICATE** — reachable code that re-implements an existing canonical path.
> - **LIVE** — initially suspected dead but verified in use; must not be removed.

---

## 1. Confirmed dead code

| ID | Symbol / file | Location | Evidence | Recommendation | Removal risk |
|----|---------------|----------|----------|----------------|--------------|
| DC-01 | `program_students_per_year` duplicate view | `apps/core/admin.py:33-64` | `apps/core/urls.py:65` routes to `views.program_students_per_year` (`apps/core/views/program_views.py:193`). The admin-module copy has zero imports/callers and returns a plain `dict`, so it could never serve an HTTP response. | Delete function and now-unused imports (`Count`, `path`, `login_required`, `role_required`, `Department`). Keep `ProgramAdmin`. | Low — module-local only |
| DC-02 | `subject_lookup_json` | `apps/core/views/subject_views.py:289-302`, route `apps/core/urls.py:138`, exports `views/__init__.py:162,343` | No `{% url %}`, `reverse()`, `fetch()`, test, or docs reference anywhere. | Remove route + view; `serialize_subject_summary` then loses its last caller. | **Medium** — removes a URL; confirm no external client before deleting |
| DC-03 | `admin_reset_teacher_password` | `apps/core/views/teacher_views.py:315-356`, route `apps/core/urls.py:82` | No template/JS/test reference. Teacher UI posts to `/admin/users/<id>/reset-password/` (`static/js/core/app_password_reset.js:83`); bulk reset uses `teacher_service.reset_teacher_password`. Also lacks `AuditEvent` and returns the new password in JSON. | Remove route + view. Canonical resets already live elsewhere. | **Medium** — endpoint removal |
| DC-04 | `templates/core/admin/validation_queue.html` | 364 lines | Not rendered by any view; the `validation_queue` URL name maps to `validation_hub` (`apps/core/views/validation_views.py:169`, `urls.py:33`). `validation_hub.html` is the live template. | Delete template and its two JS assets (`queue_filters.js`, `queue_actions.js`) after confirming no direct `/validation/` fallback render. | Low |
| DC-05 | `templates/theme/footer.html`, `templates/theme/settings.html` | 2 and 4 lines | No `{% include %}`/`{% extends %}` anywhere. `theme/base.html` includes only `favicons.html` and `sidebar.html`. | Delete both. | Low |
| DC-06 | `static/js/app.js` (legacy namespace shim), `static/js/student_directory/addstudent.js` | — | `app.js` is not loaded by any project template (only a vendored signature-pad demo references a local `js/app.js`). `addstudent.js` targets `addStudentBtn`/`addStudentDept`/`addStudentProgram`, none of which exist in `student_directory.html`. | Delete both. | Low |
| DC-07 | `DepartmentForm`, `ProgramForm`, `UserForm` | `apps/core/forms/academic_forms.py:17,66`; `apps/users/forms.py:5` | Only imports are package `__init__` re-exports; views hand-parse POST or call services. | Delete forms and their `__init__` exports. | Low |
| DC-08 | Academic/identity validators | `validators/academic_validators.py:16,34,46`; `validators/identity_validators.py:23` (`validate_academic_year_code`, `validate_program_duration`, `validate_class_section_code`, `validate_student_id`) | Zero references outside `validators/__init__.py`. Services inline the same rules (`academic_service.py:181-183,496-503`). | Prefer consolidating service checks onto these validators rather than deleting — see duplication DUP-04. | Low if deleted; better used |
| DC-09 | Unused serializers | `serializers/academic_serializers.py:29,63,151`; `serializers/audit_serializers.py:12` | Only listed in `serializers/__init__.py`; no view/test caller. | Delete or reuse. | Low |
| DC-10 | `mysite/views.py::home` | `mysite/views.py:3` | Renders `index.html`, which does not exist; no import or route. | Delete file. | Low |
| DC-11 | Unused image assets | `static/img/background.jpg`, `favicon-16x16.png`, `favicon-32x32.png`, `favicon.png`, `kcc_favicon.ico`, `kcc_logo.jpg`, `logo.jpg`, `apple-touch-icon.png` | Reference scan: not linked by templates/CSS/JS. Used counterparts: `favicon.ico`, `kcc_favicon_16/32.png`, `kcc_apple_touch.png`, `kcc_logo.png`. | Delete unused images. | Low |
| DC-12 | `Profile.privacy_notice_version` | `apps/core/models/profile.py:170` | Never read or written in code/templates. | **Do not drop** without legal/compliance sign-off; keep as placeholder. | High if deleted |

**Batch A remediation (2026-10-31):** DC-01, DC-05, DC-06, DC-07, DC-09, DC-10, and DC-11
were removed, including package exports and the verified unused imports in §5. DC-08 validators
were intentionally retained for possible consolidation. DC-02/03/04 and DC-12 remain untouched.

### 1.1 Latent defect (fix, do not delete feature)

`apps/core/views/__init__.py:310-311` lists `program_students_csv_export` twice as **bare
identifiers instead of strings**:

```python
'program_students_csv_export',   # duplicate string
program_students_csv_export,     # <-- object, not a string
```

Any future `from apps.core.views import *` raises `TypeError: Item in __all__ must be str`.
No star-import exists today, so the bug is latent. **Fixed 2026-10-31:** the duplicate bare
identifier was removed; `__all__` now holds 115 unique strings and `ViewPackageExportTests`
exercises a star import. Tracked as **AUD-19** in the audit.

---

## 2. Potentially unused (needs product decision)

| ID | Item | Location | Finding |
|----|------|----------|---------|
| PU-01 | `RegistrationForm` | `apps/core/forms/registration_form.py:24` | Runtime registration uses `_validate_registration_data` (`views/helpers/auth_helpers.py:116`); only tests reference the form. Form also lacks current `gender`/`phone_number`/`student_type` fields. Either retire with its tests or make it the single validation source (DUP-03). |
| PU-02 | `seed_kcc_data`, `seed_demo_roster` commands | `apps/core/management/commands/` | Reachable via `manage.py` but invoke nothing. `seed_all_roles` (229 lines) covers departments/programs/accounts. Documented in `docs/05_ARCHITECTURE_BLUEPRINT.md:97-98`. |
| PU-03 | `Profile.privacy_consent_at` | `apps/core/models/profile.py:166` | Read once in `validation_views.py:365`, never written — registration collects no consent. Compliance gap rather than dead code. |
| PU-04 | Vendored libraries | `static/libs/*` | Only `chartjs` and `fullcalendar` are referenced (`dashboard.html:1221`, `calendar.html:517`). 19 other packages (~1,000 files: apexcharts, hugerte, tom-select, imask, plyr, etc.) are unreferenced. Remove only after confirming no runtime dynamic loader. |
| PU-05 | Stale CSS blocks | `static/css/validation.css:113-380`, `dashboard.css`, `components.css` | ~46 dashboard selectors and ~68 component selectors have no matching class in current templates. Some classes may be generated at runtime; verify with browser devtools before pruning. |

---

## 3. Duplicate implementations (all LIVE, consolidation candidates)

| ID | Duplication | Locations | Canonical target |
|----|-------------|-----------|------------------|
| DUP-01 | Password reset has four paths | `auth_views.py:281` (`admin_reset_user_password`), `users/views.py:494` (`user_reset_password_ajax`), `teacher_views.py:315` (dead), `teacher_service.py:233` (`reset_teacher_password`) | One service that validates, audits, optionally revokes sessions |
| DUP-02 | QR secret generation repeated | `approval_service.py:109`, `auth_service.py:82`, `student_service.py:300`, `users/views.py:349`, `seed_all_roles.py:196,207`, `seed_demo_roster.py:84,132` | `credential_service.rotate_student_credentials` |
| DUP-03 | Registration validation duplicated | `helpers/auth_helpers.py:116-220` vs `forms/registration_form.py` clean methods | One validator module; form and view both call it |
| DUP-04 | Academic validation duplicated | `academic_service.py:181-183,496-503` vs unused `academic_validators.py` | Adopt the validators module |
| DUP-05 | Attendance-matrix CSV export | `class_views.py:1034-1056` and `session_views.py:1521-1546` share identical headers/rows | Extract into `attendance_service`/`export_service` |
| DUP-06 | Validation queue UI | `validation_hub.html` vs routed `pending_registrations.html` and `recently_reviewed.html` (linked from `dashboard.html:974`, `validation_detail.html:12`) | Keep one UI; backend already shared |
| DUP-07 | Account provisioning | `users/views.py:339-400` creates `User` + `Profile` (including QR secret) directly | `auth_service.provision_student_account` / `teacher_service.provision_teacher_account` |

Section creation was checked and is **not** duplicated: `class_save` is edit-only and rejects a
missing `class_id` (`class_views.py:164-167`), while `class_wizard_save` is the sole create path.

---

## 4. Verified live — do not delete

- `class_save` — posted by the edit modal in `classes.html:324`.
- `admin_reset_user_password` — called from `app_password_reset.js:83`; button in `teachers.html:263`.
- `teacher_get`, `subject_get`, `teacher_analytics_json`, `program_curriculum_remove` — hard-coded
  `fetch()`/`data-*` URLs in `edit_teacher.js:27`, `edit_subject.js:32`, `teacher_analytics.js:132`,
  `programs.html:366`.
- `admin_db_backup` (`dashboard.html:777`), `admin_audit_log_export_csv` (`audit_log.html:34`).
- `registration_proof_document` / `excuse_slip_attachment_document` — used by validation and excuse templates.
- `program_students_per_year` view in `program_views.py`, `ProgramAdmin`, `apps/info`, `apps/users` — routed/linked.
- `ClassSession.auto_closed` — written by `management/commands/auto_close_sessions.py:114`.
- `fc-*` selectors in `calendar.css` — emitted at runtime by FullCalendar.
- All 11 project CSS files are reachable (`app.css` `@import`s; auth pages link directly).
- Management commands `auto_close_sessions`, `backfill_anomalies`, `backfill_class_program`,
  `rotate_qr_seeds`, `seed_ph_holidays` — intentional CLI entry points.

---

## 5. Unused imports (safe cleanup)

| File | Lines | Imports |
|------|-------|---------|
| `apps/core/admin.py` | 2-5,7 | `Count`, `path`, `login_required`, `role_required`, `Department` (all tied to DC-01) |
| `apps/core/views/calendar_views.py` | 14,17,19 | `json`, `messages`, `ValidationError` |
| `apps/core/views/dashboard_views.py` | 19 | `redirect` |
| `apps/core/views/department_views.py` | 18 | `get_object_or_404` |
| `apps/core/views/student_views.py` | 20-23 | `Count`, `HttpResponse`, `get_object_or_404`, `timezone` |
| `apps/core/views/teacher_views.py` | 23,323-324 | `ClassSlot`; `send_mail`, `settings` (inside dead reset function) |
| `apps/core/views/validation_views.py` | 13,23,546 | `secrets`, `timezone`, `json as _json` |
| `apps/core/services/academic_service.py` | 26 | `Class` |
| `apps/core/services/teacher_service.py` | 22 | `timezone` |
| `apps/core/management/commands/seed_all_roles.py` | 6 | `ClassSlot` |

Intentional re-exports (`auth_views.LOCK_DURATION`, names in `views/__init__.py`) are excluded.

**Batch A status:** all independently unused imports above were pruned. `send_mail` and `settings`
remain inside retained endpoint DC-03 and will disappear only if that endpoint removal is approved.

---

## 6. Proposed cleanup batches

Each batch must leave the full suite green.

**Batch A — zero functional risk (TODO-P2-01): COMPLETED 2026-10-31.** Deleted DC-05, DC-06,
DC-10, DC-11; removed the DC-01 duplicate and its imports; removed DC-07/DC-09 and exports; pruned
the independently unused imports. Verification: 128/128 targeted tests, 422/422 full tests on
MariaDB (569.5 s) and SQLite (14.5 s), clean `manage.py check`, and no migration drift.

**Batch B — removes endpoints, requires approval (TODO-P2-02):** DC-02, DC-03, DC-04.

**Batch C — product/legal decision (TODO-P2-03):** DC-12, PU-01..PU-05, DUP consolidation.

---

## 7. Method limitations

- Dynamic references were traced manually for `{% url %}`, `reverse()`, `fetch()` strings,
  `data-*` attributes, and admin registration.
- No runtime coverage was collected for templates; a template can be unreachable yet still
  referenced by test code (checked for `validation_queue.html`: no test renders it).
- Third-party vendored code was excluded from symbol analysis.
- Django model fields can be referenced via `getattr`/ORM strings; fields with zero textual
  references were cross-checked against migrations and templates before being listed.

**Cross-reference:** audit findings **AUD-19** (latent `__all__`) and **AUD-25** (dead teacher
reset) are detailed in `docs/SYSTEM_AUDIT.md`; work items live in `docs/DEVELOPMENT_TODO.md`.
