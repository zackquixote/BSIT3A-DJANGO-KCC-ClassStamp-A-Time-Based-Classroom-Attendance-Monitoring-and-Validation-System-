# Browser Verification — 2026-11-10 (plan task 6.3)

Live walkthrough of the integrated application against the SQLite development
database, using the dedicated role accounts in `VERIFY_ACCOUNTS.md`
(password `#`-redacted; see that file). Server:
`USE_SQLITE=True python pmanage.py runserver 127.0.0.1:8000 --noreload`.

Three evidence levels appear below:

- **UI** — driven through the rendered page (clicks, form fills, visible text).
- **Endpoint** — the page’s own JavaScript path called with the session cookie
  and the page’s CSRF token (the same request the UI makes), used where a native
  file picker or a confirm dialog would block automation.
- **DB** — the resulting rows in `AuditEvent` / models, read straight from the
  database after the action.

Automated coverage for the same behaviour lives in the suites named in
`tasks.md` (all green, see task 6.2).

## Result summary

| # | Check | Result | Evidence |
| --- | --- | --- | --- |
| 1 | Admin, teacher, student navigation, no sidebar regression | Pass | UI: admin sidebar 19 links (11 academic/management, 3 security, 3 oversight, notifications, messages); teacher sidebar 9 teacher-only items; student sidebar 8 student-only items |
| 2 | Role denial (middleware) | Pass | UI: teacher → `/admin/students/` 403; teacher → `/student/dashboard/` 403; student → `/admin/students/` 403; anonymous → `/student/dashboard/` redirects to `/?next=/student/dashboard/` |
| 3 | Approval denial + waiting page | Pass | DB: student flipped to PENDING mid-session; UI: `/student/attendance/` → `/student/approval-waiting/` "Waiting for approval"; DB: `ACCESS_DENIED_UNAPPROVED` "Attempted to access /student/attendance/ with status PENDING". Login of a PENDING account is refused earlier with "Your account registration is currently PENDING Admin validation." |
| 4 | Curriculum rejection | Pass | UI/Endpoint: `verify_nocv` join with a valid VER3 code → "No curriculum version assigned. Please contact administration." |
| 5 | Cross-program rejection + audited override | Pass | Endpoint: BSA student → VER1 (IT311 major) 400 "Cross-program enrollment for major subjects is restricted."; retry with `allow_cross_program=1` → 200. DB: `ENROLLMENT_REJECTED_CURRICULUM_OVERRIDE` + `ENROLL_STUDENT` |
| 6 | Capacity | Pass (partly by test) | UI: VERF renders `2 / 1` — existing enrollments are never removed when capacity is lowered. Full-class rejection/override covered by `test_enrollment_validation` |
| 7 | Holiday auto-cancellation | Pass | UI: calendar → Add Event → Holiday "QA Verification Holiday" (2026-11-10, all-day) → toast "Event … successfully created" + "4 active class timetable slot(s) coincide with this date span". DB: sessions 13 (VER1) and 15 (VERF) became `CANCELED` with reason "Auto-cancelled: QA Verification Holiday (Holiday)" and two `SESSION_AUTO_CANCELLED` events |
| 8 | Manual reopen (audited) | Pass | UI: teacher dashboard kept the holiday badge/advisory; opening VER1 for today reopened session 13 and the scanner showed "Calendar Advisory: Today coincides with an official event…". DB: `REOPEN_CLASS_SESSION` |
| 9 | Legacy slot conflicts | Pass | Endpoint: teacher clash hard-blocked 400 "the teacher is already teaching VER1 Tuesday 09:00-10:30" (no override offered); room clash 400 with `override_available: true` and conflict list; `override_conflicts=1` saved the slot and DB recorded `CLASS_SLOT_CONFLICT_OVERRIDE` |
| 10 | Section Wizard conflicts | Pass (test-covered) | `test_class_wizard` + `test_week7` cover block/override in the wizard save paths; the wizard page renders under the enforced CSP |
| 11 | Class cloning + disabled join codes | Pass | UI: Clone Classes modal (source → target), duplicate run reported "Copied 0 class(es)… 4 class(es) were skipped or failed" with per-class reasons and no overwrite. DB: the four 2nd-Semester clones have `join_code_active=False`, empty digest, 0 enrollments, 0 sessions |
| 12 | Push permission / subscription / delivery | Partial (environment-limited) | UI: notifications page renders "Enable desktop alerts"; the automation browser reports no Push API support, so the control correctly degrades to a disabled "Push not supported". No VAPID keys are configured, so the delivery service audits `PUSH_NOTIFICATION_SKIPPED — VAPID keys not configured` and the notification still lands in-app. Subscribe/duplicate/410/expired paths are covered by `test_notifications` |
| 13 | Bulk excuse approval | Pass | UI: two pending slips → "Select all pending excuse slips" → "Approve selected (2)" → both resolved. DB: `EXCUSE_APPROVED` ×2, `EXCUSE_BULK_APPROVED`, in-app "Excuse slip approved" ×2, `NOTIFY_EXCUSE_DECISION` (email delivery failure recorded, non-fatal) |
| 14 | Bulk partial failure | Pass | Endpoint: POST with another teacher’s slip + a missing id → `approved: 0, failed: 2`, "You are not authorized to review this excuse slip." and "Excuse slip not found."; CSRF-less POST → 403 |
| 15 | CSV + PDF exports | Pass | Endpoint: `?format=pdf` → 200 `application/pdf`, `attachment; filename="attendance_matrix_VER1_20261110.pdf"`, 2 748 bytes, `%PDF-` magic; `?format=csv` → 200 `text/csv`, `attendance_matrix_VER1_20261110.csv` |
| 16 | Messaging permissions, thread, unread | Pass | UI: teacher compose lists admin + the three students enrolled with that teacher only (no unrelated accounts); send → thread page renders both messages; DB: notification "New message: Messaging smoke test…" for the student. Student unread badge counts in the sidebar |
| 17 | Predictions | Pass | UI: matrix "PREDICTED" column, danger badge with advisory title below the 80 % line, "At-risk only (3)" filter, algorithm note `linreg-cumulative-v1` and the 85 % term-length assumption. Insufficient-data rendering is covered by `test_predictions` |
| 18 | Join code panel | Pass | UI: teacher class cards expose Generate/Rotate/Disable join code; a code generated for VER3 was accepted by the student endpoint |
| 19 | CSP violations before enforcing | Pass | Report-only policy: 0 violations from all post-fix page loads; the 62 historical report-only events (00:38–00:57 UTC) all point at pages whose inline scripts have since been given nonces. A rendered-HTML sweep of 40 routes found 0 inline `<script>` without `nonce` and 0 inline `on*=` attributes |
| 20 | CSP after enforcing | Pass | `Content-Security-Policy` (not Report-Only) with per-request nonce + `report-uri`; admin dashboard chart instance renders, classes-page roster modal fetches its roster, academic-years clone modal works, student dashboard and login render, and Django’s own admin site (index, program changelist with filter sidebar, program change form) loads with no blocked scripts; 0 `CSP_VIOLATION` events after the switch |

## Intentional change made during this task

`mysite/settings/base.py` now ships the policy enforced (`CSP_ENFORCE = True`).
This is the documented follow-up to task 1.5 ("enforce after browser
verification"). The policy still reports to `/api/csp-report/`, so regressions
keep landing in `AuditEvent`. Three assertions that pinned the old
Report-Only header were updated to match the enforced default, and
`test_phase1_security` now proves the Report-Only header still appears when
`CSP_ENFORCE=False` is forced:

- `test_phase1_security.CspMiddlewareTests.test_enforced_header_by_default_with_nonce` (was `…report_only_header_by_default…`)
- `test_phase1_security.CspMiddlewareTests.test_report_only_mode_uses_the_report_only_header` (now uses `@override_settings(CSP_ENFORCE=False)`)
- `test_middleware.SecurityHeadersMiddlewareTests.test_security_headers_present`

## Test data created and removed

Created for the walkthrough and removed afterwards: the QA holiday event, the
two ad-hoc VER3/VER2 slots, the `verify_bsa` → VER1 override enrollment, the
foreign-class QA excuse slip, and the temporary VER3 join code (disabled again).
Sessions 13/15 are back to `OPEN`, matching the documented fixture state. The
two approved QA excuse slips remain as ordinary resolved history.

## Not verifiable in this environment

- Real Web Push delivery (needs HTTPS, a Push-capable browser and deployment
  VAPID keys). The disabled/unsupported states and the audited skip path were
  verified instead.
- Camera-based QR scanning through a physical device; the scanner page loads,
  its scripts run under the enforced CSP, and scanning logic is covered by
  `test_scan_security`.
