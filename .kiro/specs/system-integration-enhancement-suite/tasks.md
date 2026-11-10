# System Integration & Enhancement Suite — Deduplicated Implementation Plan

## Purpose

This plan supersedes the previous 47-task sequence. It is based on a source-code audit of the current repository, not on the presence of files or the old task checkboxes.

Use this document to continue implementation in another IDE or session. Work in phases, keep the existing application behavior intact, and mark a task complete only after its implementation and verification steps are finished.

- Audit date: 2026-11-09
- Requirements covered: 1–20
- Requirements 11 and 18 are intentionally consolidated because they describe the same teacher/room conflict service.
- No production code was changed during the audit.

## Current Verified Baseline

### Focused test run

Command:

```bash
USE_SQLITE=True python manage.py test \
  apps.core.tests.test_permission_service \
  apps.core.tests.test_week7 \
  apps.core.tests.test_notifications \
  apps.core.tests.test_middleware \
  apps.core.tests.test_class_join_codes \
  apps.core.tests.test_scan_security --verbosity 1
```

Result:

- 160 tests discovered
- 122 passed
- 5 failed
- 33 errors
- Full suite was not run during the audit.

Primary baseline issues:

1. `apps/core/tests/test_permission_service.py` creates `AcademicYear` with obsolete `year_code` data.
2. Push tests patch `apps.core.services.push_notification_service.webpush`, but the service now imports `webpush` inside the delivery method.
3. Join-code tests expect `PENDING`; the current join flow deliberately auto-activates enrollment.
4. Two Week 7 tests expect a null class program, but `Class.save()` now infers program/year from the section code.

### Implementation snapshot

| Requirement | Current state | Required action |
| --- | --- | --- |
| 1. Curriculum enrollment validation | Curriculum infrastructure exists, but student join/manual roster flows only enforce program/schedule rules | Add shared student-curriculum validation, rejection audit, and manual override |
| 2. Capacity enforcement | Join, single roster enrollment, and batch roster enrollment enforce capacity | Reuse existing flows; add rejection audit and admin override only |
| 3. Holiday auto-cancellation | Holiday advisory and audited manual reopen exist | Add automatic cancellation; do not duplicate reopen logic |
| 4. Web Push | Model, service, APIs, service worker, and tests exist, but delivery is not connected to notification creation | Repair wiring/configuration/tests before adding more UI |
| 5. RBAC middleware | `role_required` decorators exist; no RBAC middleware | Integrate object permissions first, then add middleware with real routes |
| 6. Approval middleware | `approved_required` exists; no waiting route or denial audit | Add actual waiting page and middleware without weakening decorators during migration |
| 7. PermissionService | Four methods exist but views still duplicate authorization | Wire service into existing views and repair its stale tests |
| 8. Internal messaging | Message model/migration only | Add service, authorization, views, URLs, templates, and tests |
| 9. At-risk alerts | Existing command calculates risk and emails students | Extend existing command; add flags, teacher/push delivery, resolution, and audit |
| 10. Portal consolidation | `theme/base.html` plus role-aware `theme/sidebar.html` already shared by extending templates | Do not create `base_portal.html`; requirement goal is already met |
| 11 + 18. Schedule conflicts | Existing function detects conflicts and is used by class creation/wizard | Extend existing function; fix dual-conflict return and save policy |
| 12. Academic-year rollover | Existing rollover activates a new term and optionally promotes students | Add class/slot cloning beside current rollover; do not replace it |
| 13. Bulk excuse approval | Single-slip review exists | Extract/reuse single-review logic and add bulk endpoint/UI |
| 14. PDF export | Attendance matrix supports CSV | Add PDF beside existing CSV path |
| 15. Predictive analytics | AnalyticsService prediction method exists but is unused | Add UI, tests, threshold warning, and algorithm-version audit |
| 16. API rate limiting | Attendance scan has user/IP 429 throttling | Add API-wide limits while preserving stricter scan protection |
| 17. CSP | Basic CSP header exists but allows inline scripts and has no nonce/report audit | Harden existing middleware incrementally |
| 19. Session security | Cookie settings, production Secure flag, and login key rotation exist | Verify with tests; no duplicate implementation |
| 20. Password policy | Django standard validators exist | Add composition and last-five history; reuse all current password entry points |

## Non-Duplication Rules

1. Do not create a second scheduling service. Extend `apps/core/services/schedule_service.py`.
2. Do not replace `rollover_academic_year`. Add class-cloning behavior in `apps/core/services/academic_service.py` and the existing academic-year views/templates.
3. Do not create `base_portal.html`. Keep `templates/theme/base.html` and `templates/theme/sidebar.html`.
4. Do not create a parallel enrollment workflow. Shared validation must be called by:
   - `student_join_class`
   - single roster enrollment
   - batch roster enrollment
5. Do not create a second at-risk command. Extend `apps/core/management/commands/notify_at_risk.py`.
6. Do not maintain two absence-rate formulas. Choose the existing absence-radar/policy calculation as canonical and reuse it from analytics and the command.
7. Do not duplicate single-excuse approval logic in the bulk endpoint. Extract a shared service operation and call it from both paths.
8. Do not add startup-generated VAPID secrets. Configure VAPID keys as deployment secrets.
9. Keep current decorators while middleware coverage is being tested. Remove redundant checks only after route-level tests prove equivalent protection.
10. Tests are required, not optional. A task is not complete while its related tests are red.

---

## Phase 0 — Reconcile the Baseline and Make the Suite Trustworthy

- [x] **0.1 Audit the 20 requirements and replace the stale implementation sequence**
  - Consolidate Requirements 11 and 18.
  - Record existing equivalents and missing acceptance criteria.
  - Record the focused test baseline above.

- [x] **0.2 Repair PermissionService test fixtures**
  - Update `apps/core/tests/test_permission_service.py` to use current `AcademicYear`, `Class`, `Profile`, `ClassSession`, and `ExcuseSlip` fields.
  - Preserve the authorization assertions; do not weaken tests merely to match current behavior.
  - Verify all four permission methods for admin, teacher, student, no-profile, and inactive/completed/withdrawn enrollment cases.
  - Run: `USE_SQLITE=True python manage.py test apps.core.tests.test_permission_service`.

- [x] **0.3 Repair Web Push mocks**
  - Patch `webpush` at its actual import location used by `PushNotificationService.send_push_notification`.
  - Keep coverage for successful delivery, 410 deletion, retryable errors, disabled notifications, payload structure, and subscription hashing.
  - Run: `USE_SQLITE=True python manage.py test apps.core.tests.test_notifications`.

- [x] **0.4 Align join-code tests with the approved current workflow**
  - Retain the current deliberate auto-activation behavior unless a product decision explicitly restores teacher approval.
  - Rename/update tests that still assert legacy `PENDING` behavior.
  - Update the capacity-reservation test to create its precondition explicitly rather than relying on legacy join behavior.
  - Run: `USE_SQLITE=True python manage.py test apps.core.tests.test_class_join_codes`.

- [x] **0.5 Align Week 7 tests with section-code program inference**
  - Update fixtures/assertions to account for `Class.save()` inferring program and year level from codes such as `BSIT-3A`.
  - Use a genuinely non-matching code for tests that intentionally verify null inference.
  - Run: `USE_SQLITE=True python manage.py test apps.core.tests.test_week7`.

- [x] **0.6 Establish a clean baseline**
  - Re-run the focused 160-test command and reach 160/160 passing.
  - Run the complete suite with SQLite.
  - When XAMPP/MySQL is available, run the complete suite against the project’s normal database configuration as well.
  - Record the date, command, test count, and result here before proceeding:
    - SQLite full suite: 2026-11-09 — 749 tests, OK (exit 0), after Phase 0
      repairs and before Phase 1 middleware registration. Command:
      USE_SQLITE=True python pmanage.py test (pmanage.py is a sys.path
      wrapper required by this environment embedded Python).
    - MySQL full suite: NOT RUN at that moment — mysqlclient was missing from
      this Python; XAMPP MySQL was present but the driver was not. Superseded:
      the driver is installed now and the MySQL suite ran green on 2026-11-09
      (see 6.2).

---

## Phase 1 — Authorization and Security Integration

### 1A. Centralize existing authorization before adding middleware

- [x] **1.1 Integrate PermissionService into current views**
  - Use `can_user_access_class` in class detail/matrix/read paths.
  - Use `can_user_modify_session` in session attendance and scan-management paths, replacing duplicate helpers such as `_teacher_can_manage` where equivalent.
  - Use `can_user_approve_excuse` in single excuse review and later bulk review; replace `_can_review_excuse`.
  - Use `can_user_manage_enrollment` in single/batch roster management.
  - Preserve existing superuser behavior and current 403/404 information-disclosure policy.
  - Add view-level tests proving that callers cannot bypass object-level checks by changing IDs.
  - Run PermissionService tests plus class, session, scan-security, excuse, and roster tests.

### 1B. Add route-level defense in depth using actual application routes

- [x] **1.2 Implement RoleBasedAccessMiddleware**
  - Add `apps/core/middleware/rbac.py` and register it after `AuthenticationMiddleware`.
  - Actual portal prefixes are `/admin/`, `/teacher/`, and `/student/`; do not use the obsolete `/admin-portal/` example.
  - Keep Django’s `/admin/` site behavior explicit. Superusers without a profile must not be accidentally locked out by an incorrect exemption/rule interaction.
  - Redirect anonymous users to the real login route; return HTTP 403 for authenticated role mismatches.
  - Use a centralized exemption list for login, logout, static/media, service worker, and other public routes.
  - Test every portal prefix, nested paths, anonymous users, missing profiles, superusers, and exempted routes.

- [x] **1.3 Implement ApprovalCheckMiddleware and waiting page**
  - Add the real `/student/approval-waiting/` route and template using `theme/base.html`.
  - Redirect PENDING/REJECTED students from protected student routes to that page.
  - Skip teachers/admins and explicit exemptions; avoid redirect loops.
  - Write denied access attempts to AuditEvent without logging sensitive request payloads.
  - Test approved, pending, rejected, anonymous, exempted, and non-student requests.

### 1C. Rate limiting

- [x] **1.4 Add API-wide fixed-window throttling**
  - Cover `/api/`, including the real `/api/attendance/scan/` route; do not target obsolete `/student/scan/`.
  - Authenticated default: 100 requests/minute. Anonymous default: 20 requests/minute.
  - Use atomic cache `add`/`incr`, following the existing `_bump_counter` approach rather than race-prone `get`/`set` increments.
  - Return HTTP 429 with an accurate `Retry-After` value.
  - Preserve the existing stricter per-operator/per-IP scan throttle as an additional layer.
  - Use the shared production cache; do not rely on per-process LocMem for enforcement across workers.
  - Audit repeated violations with throttled logging so an attacker cannot flood the audit table.
  - Test both limits, expiry, exempt non-API routes, response headers, and combined scan/global behavior.

### 1D. Content Security Policy

- [x] **1.5 Harden SecurityHeadersMiddleware without breaking inline assets**
  - Generate a cryptographically random nonce per request and store it only on `request`; never store request-specific nonces on middleware `self`.
  - Inventory all inline scripts and external CDN/font/image dependencies first.
  - Deploy initially as `Content-Security-Policy-Report-Only`, add nonces or externalize scripts, then enforce after browser verification.
  - Remove `'unsafe-inline'` from `script-src`; retain only explicitly required sources.
  - Align the final policy with the requirements for scripts, styles, images, frames, forms, and connections.
  - Wire or remove the currently unused CSP setting tuples so configuration has one clear source of truth.
  - Add a bounded CSP-report endpoint that validates JSON size/shape and records violations in AuditEvent.
  - Test nonce uniqueness across requests, headers on success/error responses, required directives, and report logging.

### 1E. Password policy and session verification

- [x] **1.6 Add password composition validation**
  - Add a validator requiring uppercase, lowercase, digit, and special character, with minimum length 8.
  - Keep Django’s common-password, numeric-password, and similarity validators.
  - Return specific unmet requirements to the user.
  - Apply the same validation to registration, password reset, admin-created passwords, and user password changes.

- [x] **1.7 Add last-five password history**
  - Add a password-history model/migration that stores Django password hashes only, never plaintext.
  - Check candidate passwords against the current and previous five hashes using Django’s password verification.
  - Update history on every successful password change and prune entries older than the retained five.
  - Cover registration, reset, admin, and user-account password paths.
  - Test reuse rejection, non-reuse acceptance, history pruning, and unchanged existing sessions.

- [x] **1.8 Lock in session security with tests**
  - Verify HttpOnly, SameSite=Lax, four-hour age, production Secure, login session-key rotation, and the existing shorter inactivity timeout.
  - Do not add another session-timeout mechanism.
  - Correct misleading configuration comments if they claim `SESSION_SAVE_EVERY_REQUEST` rotates session IDs.

---

## Phase 2 — Enrollment, Holiday, and Schedule Integrity

### 2A. Shared enrollment validation

- [x] **2.1 Add shared curriculum validation**
  - Implemented in `apps/core/services/enrollment_service.py` (`validate_student_curriculum`, `check_class_capacity`, `audit_enrollment_rejection`).
  - Verified by `apps.core.tests.test_enrollment_validation` (2026-11-09).
  - A new `apps/core/services/enrollment_service.py` is acceptable because none exists now, but it must serve the existing flows rather than replace them.
  - Validate that `class_obj.subject` has a Curriculum row for the student’s assigned `curriculum_version`.
  - Reject missing curriculum assignment with a clear “contact administration” message.
  - Reject subjects outside the assigned curriculum.
  - Log rejection with student ID, class code, and reason in AuditEvent.
  - Reuse existing curriculum-version helpers where possible; do not create another curriculum resolver.

- [x] **2.2 Wire curriculum and capacity validation into every enrollment path**
  - Wired into `student_join_class`, `class_roster_enroll`, and `class_roster_enroll_batch` with `select_for_update` capacity checks and explicit audited overrides (`allow_cross_program`, admin-only `override_capacity`).
  - Verified by `test_enrollment_validation`, `test_class_join_codes`, and `test_classes_page` (2026-11-09). Join-code and batch-clash fixtures were updated to assign a curriculum version and subject entries, since Req 1 now rejects students without one.
  - Call shared validation from join-code, single manual, and batch manual enrollment.
  - Preserve `select_for_update` capacity checks to prevent concurrent over-enrollment.
  - Keep `capacity=None` unlimited and never remove enrollments merely because capacity was lowered.
  - Manual admin/teacher curriculum override must be explicit and audited.
  - Only admin may override capacity, and the override must be explicit and audited.
  - Audit capacity rejection as well as successful overrides.
  - Test valid/invalid/missing curriculum, full/unlimited capacity, concurrent boundary behavior, both override types, and all three entry paths.

### 2B. Holiday automation

- [x] **2.3 Auto-cancel sessions for newly created scheduled holidays**
  - Implemented in `apps/core/signals/holiday_signals.py` (post_save on AcademicEvent; creation only; Asia/Manila boundary conversion; per-session plus summary audit events).
  - The duplicate (slot, session_date) fixture in `test_closed_and_already_cancelled_sessions_are_untouched` was corrected to use a second slot. All `test_holiday_autocancel` tests pass (2026-11-09).
  - Use actual `AcademicEvent.start_datetime` and `end_datetime`, not nonexistent `event_date`.
  - Convert event boundaries to project-local dates and find affected SCHEDULED/OPEN ClassSessions.
  - Set status to CANCELED and store a cancellation reason containing the holiday title.
  - Create an AuditEvent for every canceled session.
  - Register the handler through the project’s existing signal initialization.
  - Do not restore sessions when a holiday is deleted or canceled.
  - Retain the existing audited manual reopen behavior.
  - Test no sessions, one/multiple sessions, already CLOSED/CANCELED sessions, deletion/cancel non-restoration, and manual reopen.

### 2C. Consolidated schedule conflicts — Requirements 11 and 18

- [x] **2.4 Complete the existing detect_slot_conflicts function**
  - The teacher/room `elif` now records both conflict records for a single slot; conflict dicts carry type, class code, weekday, formatted times, room, and teacher name. Academic-year scoping, TBA skipping, and `exclude_slot_ids` are covered by `test_week7` (2026-11-09).
  - Change the teacher/room `elif` so one existing slot can return both applicable conflict records.
  - Return all conflicts with type, class code, weekday, start/end or formatted time range, room, and teacher name.
  - Continue excluding inactive slots/classes and explicit `exclude_slot_ids`.
  - Continue academic-year scoping and empty/TBA room skipping.
  - Add tests for simultaneous teacher+room conflict, multiple conflicts, boundary-touching times, editing exclusion, TBA, and year isolation.

- [x] **2.5 Enforce one save policy in legacy slot and Section Wizard flows**
  - Intentional behavior change (2026-11-09): room clashes previously only warned; they now hard-block in both `class_slot_save` and the wizard save paths unless the admin explicitly confirms (`override_conflicts=1`), which writes a `CLASS_SLOT_CONFLICT_OVERRIDE` / `WIZARD_ROOM_CONFLICT_OVERRIDE` AuditEvent with the conflict details. Teacher clashes remain unconditional blocks. The wizard review step and the legacy slots modal both expose the explicit confirmation.
  - There is no slot-edit route in the application (slots are created and retired only), so `exclude_slot_ids` remains a service-level capability exercised by unit tests rather than a view concern.
  - `test_room_conflict_warns_but_saves` (both copies in `test_week7`) was replaced with block/override test pairs; all `test_week7`, `test_class_wizard`, and `test_classes_page` suites pass.
  - Teacher and room conflicts must hard-block by default before ClassSlot creation/editing.
  - If an admin override is retained, require explicit confirmation and write an AuditEvent containing conflict details.
  - Pass the current slot ID in `exclude_slot_ids` on edit.
  - Do not create a second conflict detector in either view.

---

## Phase 3 — Academic-Year Class Structure Cloning

- [x] **3.1 Add class/slot cloning beside the existing term rollover**
  - `clone_classes_academic_year(actor, source_year, target_year)` in `apps/core/services/academic_service.py` copies active classes (code, section, subject, teacher, program, year level, capacity, grace minutes) and active slots (weekday, start/end, room). Enrollments, sessions, attendance, and join codes are never copied; clones start with an empty digest and `join_code_active=False`. Duplicates are reported and never overwritten. Each class is copied in its own savepoint. Returns counts, mapping, and errors; the completed operation is audited (`CLONE_ACADEMIC_YEAR_CLASSES`).
  - Verified by `apps.core.tests.test_academic_clone` (2026-11-09): success, no join-code/roster/session copy, inactive skipping, duplicates, same-year rejection, partial failure without a leftover shell, and view permission/GET/param tests.
  - Extend `apps/core/services/academic_service.py` with a class-cloning operation accepting actor, source year, and target year.
  - Copy active classes with class_code, section_code, subject, teacher, program, year_level, capacity, and grace_minutes.
  - Copy active slots with weekday, start/end, and room.
  - Never copy enrollments, sessions, attendance records, or join codes.
  - New classes must have an empty join-code digest and `join_code_active=False`.
  - Detect duplicate target class codes and report them without silently overwriting.
  - Use per-class transactions/savepoints so one class failure can be reported without leaving a broken outer transaction or partial class/slot copy.
  - Return copied class count, copied slot count, class mapping, and errors.
  - Audit the completed operation with actor and summary.

- [x] **3.2 Add cloning controls to the existing academic-year UI**
  - `/academic-years/clone-classes/` (admin POST) plus a Clone Classes button and modal on the existing academic-years page with source/target selectors, a confirmation dialog, copied counts, skipped duplicates, and per-class errors. Distinct from the rollover wizard (no term activation, no student promotion).
  - Confirmation is a JS `confirm()` plus the server-side distinct-term check; role mismatches redirect to the dashboard via the existing `role_required` decorator.
  - Add source/target selectors and confirmation to current academic-year views/templates.
  - Display copied counts, skipped duplicates, and per-class errors.
  - Keep this operation distinct from the existing “activate new term and promote students” action.
  - Test successful cloning, no join-code copying, no roster/session copying, duplicates, partial errors, permissions, and confirmation.

---

## Phase 4 — Notifications and Workflow Completion

### 4A. Repair Web Push end to end

- [x] **4.1 Establish one VAPID configuration**
  - Use `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, and `VAPID_ADMIN_EMAIL` consistently.
  - Point the base-template context at the same public key used by the delivery service; remove the split `WEB_PUSH_PUBLIC_KEY` configuration.
  - Document deployment key generation and secure storage; do not generate private keys during application startup.
  - Verified 2026-11-09: single `VAPID_*` source in `mysite/settings/base.py`; context processors and the base-template meta both read `VAPID_PUBLIC_KEY`; `.env.example` documents generation as a deployment secret; no startup generation.

- [x] **4.2 Connect notification creation to push delivery**
  - After creating in-app notifications, invoke PushNotificationService without allowing delivery failures to break the main transaction.
  - Cover both single-user and bulk/class notification creation paths.
  - Keep disabled/missing-key behavior audited and non-raising.
  - Align payload and service-worker click handling: backend currently nests URL under `data`, while the worker reads a top-level URL.
  - Verify configured icon/badge URLs actually exist.
  - Verified 2026-11-09: `in_app_notification_service` queues push via `transaction.on_commit` for single, class, and absent-student paths; payload carries top-level `url` plus `data.url`; worker reads both; `/static/img/kcc_logo.png` exists; missing-key/disabled delivery is audited and non-raising.

- [x] **4.3 Reuse PushNotificationService in subscription endpoints and finish UI**
  - Replace direct ORM subscription logic in feature views with service create/delete methods so audit behavior is consistent.
  - Add a visible enable/status/unsubscribe control; the existing `classstamp:enable-push` event currently has no discovered trigger.
  - Test subscribe, duplicate subscribe, unsubscribe, expired endpoint cleanup, disabled delivery, and browser permission states.
  - Verified 2026-11-09: `push_subscription_save`/`delete` call the service; notifications page has a `data-push-toggle` control with status/unsubscribe; `test_notifications` subscription cases pass (34 tests OK).

### 4B. At-risk automation

- [x] **4.4 Extend notify_at_risk into the complete daily workflow**
  - Reuse the canonical absence-radar calculation and institutional threshold.
  - Add explicit class and academic-year association for at-risk AnomalyFlags so deduplication does not depend on a scan session.
  - Create at most one OPEN at-risk flag per student/class/academic year.
  - Notify both student and assigned teacher by email and in-app notification; push then flows through the repaired notification integration.
  - When absence drops below threshold, mark the flag RESOLVED and set `resolved_at`; add the status choice/migration because the current model does not define RESOLVED.
  - Audit flags created, flags resolved, and notifications sent for each run.
  - Retain `--dry-run` and ensure it performs no flags, notifications, or completion mutations.
  - Document daily scheduling using the target OS scheduler.
  - Test threshold boundaries, deduplication, teacher/student delivery, resolution after excuse approval, dry-run, and audit totals.
  - Verified 2026-11-09: command reuses `absence_radar_for_students` + `absence_threshold_percent`; migration `0031_anomaly_at_risk_fields` adds class/academic-year/RESOLVED; `test_at_risk_workflow` passes (14 tests OK); scheduling documented in the command docstring (schtasks/cron).

### 4C. Bulk excuse approval

- [x] **4.5 Extract and reuse a single-slip approval service**
  - Move the shared status transition, attendance-record correction, notification, and audit behavior out of the single-review view into a service operation.
  - Keep the existing single-slip endpoint behavior unchanged while converting it to call the service.
  - Verified 2026-11-09: `excuse_service.review_excuse_slip` is the shared operation (PermissionService re-check per slip); single review and bulk both call it.

- [x] **4.6 Add bulk approval endpoint and UI**
  - Accept selected slip IDs by POST at a teacher excuse route.
  - Check every slip with PermissionService; never infer permission from a selected ID alone.
  - Process slips independently so one failure does not prevent remaining valid approvals.
  - Send individual student notifications and write a bulk AuditEvent with approved/error counts.
  - Add checkboxes, select-all, approve-selected action, and per-item/summary feedback to the existing teacher excuse template.
  - Test mixed ownership, already reviewed slips, one failing slip, notifications, audit count, CSRF, and non-POST rejection.
  - Verified 2026-11-09: `teacher_excuse_bulk_approve` + checkboxes/select-all/approve-selected in `teacher/excuse_slips.html`; `test_bulk_excuse` passes (8 tests OK).

### 4D. PDF attendance export

- [x] **4.7 Add PDF beside existing matrix CSV**
  - Extend the current attendance-matrix export path with `format=pdf`; do not create a separate report dataset.
  - Use one PDF dependency consistently and add it to project requirements only if absent.
  - Include class header, student list, attendance grid, generation timestamp, and generating user.
  - Return `application/pdf` and an attachment Content-Disposition filename.
  - On PDF failure, show a clear error and preserve the existing CSV fallback.
  - Test permissions, filename, content type, PDF signature, empty roster, timestamp/user metadata, and CSV regression.
  - Verified 2026-11-09: `build_attendance_matrix_pdf` (reportlab) on the existing matrix path; `reportlab==5.1.0` already in requirements; `test_pdf_export` passes.

### 4E. Internal messaging

- [x] **4.8 Add MessageService**
  - Implement send, thread retrieval, mark-as-read, and enrollment-based role validation.
  - Student ↔ teacher is allowed only when an ACTIVE enrollment connects them.
  - Teacher → admin and admin → any user need no enrollment check.
  - Restrict thread access to participants and mark-as-read to the recipient.
  - Reuse existing in-app/email notification services and AuditEvent.
  - Do not truncate silently as a substitute for form validation; enforce subject/body limits at the boundary.
  - Verified 2026-11-09: `MessageService` (send/thread/mark-as-read/eligible recipients, ACTIVE-enrollment student↔teacher rule); `test_messaging` passes (21 tests OK).

- [x] **4.9 Add messaging views, URLs, and templates**
  - Add inbox grouped by conversation, compose, and two-user thread pages.
  - Limit recipient choices to users the sender may contact.
  - Add unread badge and read-state updates using the existing base/sidebar structure.
  - Test every role pair, unrelated-user denial, thread privacy, read authorization, notifications, empty states, and CSRF.
  - Verified 2026-11-09: `/messages/`, `/messages/compose/`, `/messages/thread/<id>/` plus inbox/compose/thread templates; sidebar Messages link with `unread_message_count` badge from the context processor.

---

## Phase 5 — Predictive Analytics

- [x] **5.1 Validate and test the existing prediction service**
  - Keep `AnalyticsService.predict_final_attendance`; do not add another prediction implementation.
  - Test fewer than five sessions, exactly five sessions, 0%, 100%, monotonic improvement/decline, missing records, and clamping.
  - Treat the result as advisory, not an official pass/fail decision.
  - Review the arbitrary 85% total-session estimate before presenting predictions as reliable; document the assumption in the UI if retained.
  - Verified 2026-11-09: `apps/core/tests/test_predictions.py` covers session-count boundaries, 0%/100%, improvement/decline clamping, missing records, OPEN/future-session exclusion, and batch ranking; the 85% term-length estimate is documented in the matrix UI note.

- [x] **5.2 Add predictions to the existing class analytics/matrix UI**
  - Display prediction per actively enrolled student using current-academic-year sessions.
  - Show “insufficient data” for None.
  - Derive the warning/passing threshold from the existing institutional absence policy rather than adding a duplicate threshold setting.
  - Highlight below-threshold predictions and add an at-risk-only filter.
  - Avoid N+1 attendance queries; batch data loading if per-student calls prove expensive.
  - Verified 2026-11-09: teacher matrix page and admin matrix sheet render a Predicted/Pred column with “— data” for insufficient sessions, danger highlight below `100 - absence_threshold_percent()`, and an at-risk-only filter; `predict_class_attendance` loads sessions/records once (query count independent of roster size).
  - Intentional fixture updates (2026-11-09): `test_week8` batch cohort and the hierarchy GE case now assign curriculum versions/rows, because Req 1 correctly rejects students without a version whose curriculum lacks the subject.

- [x] **5.3 Add algorithm-version auditing**
  - Define an explicit algorithm version constant.
  - Record the version when the prediction model/configuration is refreshed or changed; do not create one AuditEvent per student per page view.
  - Test version inclusion and UI warning/insufficient-data states.
  - Verified 2026-11-09: `PREDICTION_ALGORITHM_VERSION = 'linreg-cumulative-v1'`; `ensure_algorithm_version_audited` writes one AuditEvent per version; version string renders in both matrix UIs; covered in `test_predictions.py`.

---

## Phase 6 — Final Verification and Deployment Preparation

- [x] **6.1 Reconcile dependencies and migrations**
  - Inspect current requirements before adding pywebpush, py-vapid, numpy, scikit-learn, or a PDF library; several are already used by the code.
  - Generate explicit migrations for Message changes if any, password history, at-risk flag associations/status, and other schema work.
  - Review migration order and test both forward migration and rollback behavior where supported.
  - Document database backup before deployment.
  - Verified 2026-11-09: `pywebpush==2.0.1` added to requirements (numpy/scikit-learn/reportlab were already pinned); `makemigrations --check --dry-run` reports no changes; migrations `0029_create_message_model`, `0030_password_history`, `0031_anomaly_at_risk_fields` cover the new schema in order. Deployment backup: take a database backup (mysqldump, or a file copy of `db.sqlite3`) before running `migrate`.

- [x] **6.2 Run complete automated verification**
  - Run all focused tests for each completed phase.
  - Run the full suite with SQLite.
  - Run the full suite against MySQL when available.
  - Confirm no obsolete `year_code` fixtures or invalid push patch targets remain.
  - Record results:
    - Focused suites: 2026-11-09 — test_predictions, test_teacher_matrix, test_week8, test_hierarchy_scoping, test_validation, test_phase1_security, apps.users.tests, test_password_policy, test_pdf_export, test_notifications (34), test_bulk_excuse (8), test_at_risk_workflow (14), test_messaging (21), test_enrollment_validation — all OK after the Phase 4/5 completion fixes.
    - SQLite full suite: 2026-11-09 — 899 tests, OK (exit 0), `USE_SQLITE=True python pmanage.py test`.
    - SQLite full suite after 6.3/6.4 (enforced CSP): 2026-11-10 — 899 tests, OK in 643 s, `USE_SQLITE=True python pmanage.py test` (`full_suite_after_csp2.log`). An earlier run the same day stopped on one date-dependent calendar assertion; see 6.4 for the fix.
    - MySQL full suite: 2026-11-09 — 899 tests, OK (exit 0), `python pmanage.py test` against XAMPP MySQL `bsitcrud` (`full_suite_mysql.txt`). Its two new migrations were applied on 2026-11-10 (see 6.4).
  - No obsolete `year_code` fixtures remain (Phase 0 repairs); push tests patch `sys.modules['pywebpush']` at the real import site.

- [x] **6.3 Perform browser verification**
  - Verified 2026-11-10 against the SQLite dev database with the role accounts in `VERIFY_ACCOUNTS.md`. Full evidence table: `docs/07_BROWSER_VERIFICATION_2026-11-10.md`.
  - Navigation: admin (19 links: 11 academic/management, 3 security, 3 oversight, notifications, messages), teacher (9 teacher-only items), student (8 student-only items); no sidebar regression.
  - Denials: teacher to `/admin/students/` and `/student/dashboard/` returns 403; student to `/admin/students/` returns 403; anonymous requests redirect to `/?next=...`. A student flipped to PENDING mid-session is redirected to `/student/approval-waiting/` and the attempt is audited as `ACCESS_DENIED_UNAPPROVED`; a PENDING account is also refused at login.
  - Enrollment: join without a curriculum version is rejected with the “contact administration” message; a BSA student into a BSIT major class is rejected, and the explicit `allow_cross_program=1` retry succeeds and audits `ENROLLMENT_REJECTED_CURRICULUM_OVERRIDE`; a class whose capacity was lowered keeps its existing roster (VERF shows 2 / 1). Full-capacity rejection and both overrides stay covered by `test_enrollment_validation`.
  - Holiday: creating an all-day Holiday cancelled both live sessions with “Auto-cancelled: <title> (Holiday)”, wrote two `SESSION_AUTO_CANCELLED` events, showed the teacher facing calendar advisory, and reopening the session through the teacher dashboard was audited as `REOPEN_CLASS_SESSION`.
  - Conflicts: teacher clash hard-blocked with no override offered; room clash blocked with `override_available` and the conflict list, then saved with `override_conflicts=1` and audited `CLASS_SLOT_CONFLICT_OVERRIDE`. Wizard paths remain covered by `test_class_wizard` and `test_week7`.
  - Cloning: the Clone Classes modal ran source to target, reported “Copied 0 class(es) … 4 class(es) were skipped or failed” with per-class reasons, and the existing clones keep `join_code_active=False`, an empty digest, no enrollments and no sessions.
  - Bulk excuse: select-all enabled “Approve selected (2)”, both slips resolved, each student got an in-app notification, `EXCUSE_BULK_APPROVED` was written, and a submission containing another teacher’s slip plus a missing id returned `approved: 0, failed: 2` with per-item reasons (CSRF-less POST returns 403).
  - Exports and messaging: `?format=pdf` returned `application/pdf` with `attachment; filename="attendance_matrix_VER1_20261110.pdf"` and a `%PDF-` header, `?format=csv` returned `text/csv`; teacher compose listed only the admin and enrolled students, the sent message rendered in the thread, and the student received the message notification with an unread badge.
  - Predictions: the matrix renders the PREDICTED column, a danger badge with the advisory title below the 80 % threshold, the at-risk-only filter, and the `linreg-cumulative-v1` note with the 85 % term-length assumption.
  - Push: the notifications page renders the enable control and degrades to a disabled “Push not supported” state in a browser without the Push API; with no VAPID keys the delivery attempt is audited as `PUSH_NOTIFICATION_SKIPPED` while in-app delivery succeeds. Real delivery, expired endpoints and click-through remain covered by `test_notifications` because this environment has neither HTTPS nor VAPID keys.
  - CSP: report-only produced zero violations from every post-fix page load; the 62 historical events all predate the nonce fixes. A rendered-HTML sweep of 40 routes found no inline `<script>` without a nonce and no inline `on*=` handlers.

- [x] **6.4 Production readiness checklist**
  - Verified 2026-11-10; operator steps and commands are collected in `docs/06_PRODUCTION_READINESS.md`.
  - `mysite/settings/prod.py` sets `SESSION_COOKIE_SECURE=True`, `CSRF_COOKIE_SECURE=True`, `SECURE_SSL_REDIRECT` (default True), one-year HSTS with subdomains and preload, and `SECURE_PROXY_SSL_HEADER`; startup raises when `DJANGO_SECRET_KEY` or `DJANGO_ALLOWED_HOSTS` is missing.
  - Production defaults the cache to `DatabaseCache` (`classstamp_cache`, `createcachetable`) unless `DJANGO_CACHE_BACKEND` points at a real shared backend, so rate limiting and anti-replay no longer depend on per-process LocMem.
  - `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` and `VAPID_ADMIN_EMAIL` come from the environment only; `.env.example` documents key generation and no key is created at startup.
  - The at-risk run is documented for `schtasks` (Windows/XAMPP) and cron in the command docstring; a `--dry-run` rehearsal is part of the rollout.
  - CSP is now enforced (`CSP_ENFORCE=True`) because report-only validation came back clean; violations still report to `/api/csp-report/`. Intentional change: three assertions that pinned the Report-Only header were updated (`test_phase1_security` keeps a Report-Only test through `override_settings(CSP_ENFORCE=False)`).
  - Migrations: SQLite reports “No changes detected” and `migrate --check` exits 0; MySQL `bsitcrud` was dumped to `backups/backup_bsitcrud_20261110_101804.sql` (git-ignored) before `0030_password_history` and `0031_anomaly_at_risk_fields` were applied, and `migrate --check` now exits 0 there too.
  - Only `.env.example` is tracked; `.env`, `*.env`, `backups/` and `*.log` are ignored, and no VAPID, SMTP or Django secret is committed.
  - Full suite: recorded under 6.2 (899 tests). A date-dependent assertion in `test_calendar` (`mini_calendar_events_json` is a JSON string for the template island, not a list) failed only once today’s events fell inside the mini-calendar window; the test now parses the JSON before asserting the keys, and the calendar suite is green.

---

## Requirement Traceability

| Requirement | Completion task(s) |
| --- | --- |
| 1 | 2.1, 2.2 |
| 2 | 2.2 |
| 3 | 2.3 |
| 4 | 0.3, 4.1–4.3 |
| 5 | 1.2 |
| 6 | 1.3 |
| 7 | 0.2, 1.1 |
| 8 | 4.8, 4.9 |
| 9 | 4.4 |
| 10 | Already satisfied by the shared base/sidebar; verified in 6.3 |
| 11 + 18 | 2.4, 2.5 |
| 12 | 3.1, 3.2 |
| 13 | 4.5, 4.6 |
| 14 | 4.7 |
| 15 | 5.1–5.3 |
| 16 | 1.4 |
| 17 | 1.5 |
| 19 | Existing implementation; 1.8 verification |
| 20 | 1.6, 1.7 |

## Continuation Protocol

1. Phases 0–6 are complete (6.1–6.4 recorded above). Remaining work is 
   deployment-owned: TLS/secret provisioning, the scheduler entry, and a final 
   database backup on the target server — see `docs/06_PRODUCTION_READINESS.md`. 
   Keep the suite green when you touch authentication, CSP, or the calendar.
2. Read the current source before editing; this plan describes the audited state on 2026-11-09 and may become stale.
3. Complete one numbered task at a time and run its listed tests.
4. Update the checkbox only after implementation and verification are complete.
5. Record any intentional behavior change in this file, including why tests were updated.
6. Do not mark a phase complete based only on file presence or a successful import.
7. Do not commit or push unless the user explicitly requests it.
