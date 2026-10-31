Phase 1 — Trust & Safety (P0)
These are the gaps that can cause data leaks, wrong attendance, or unauthorized access. Do these first.

1.1 — Credential Lifecycle Service M
Build one service, apps/core/services/credential_service.py, with rotate_student_credentials(profile, actor, reason).
It rotates qr_secret, stamps qr_rotated_at, deletes all unconsumed OfflineBadge records, optionally invalidates active sessions, and writes an AuditEvent.
Refactor all five entry points to call it: profile editor reset, dedicated QR reset, rotate_qr_seeds, password reset, and account deactivation.
Files: qr_service.py, student_views.py, student_portal_views.py, rotate_qr_seeds.py, models/attendance.py
Purpose: today, “reset QR” means three different things depending on where you click. This guarantees revocation actually revokes every credential derived from the old secret.
1.2 — Private Document Delivery M
Stop serving registration_proofs/ and excuse_slips/ through public /media/ URLs.
Add permission-checked download views: owner, assigned teacher, or admin only.
Replace every {{ file.url }} in templates with an authorized view URL.
In production, serve files through Django FileResponse or nginx X-Accel-Redirect; keep files outside the web root.
Files: models/profile.py, models/excuse.py, student_portal_views.py, excuse_views.py, student/qr_badge.html, teacher/excuse_slips.html, student/excuse_slips.html
Purpose: CORs, student IDs, and medical certificates currently have guessable public URLs. This is the biggest privacy gap in the system.
1.3 — Upload Validation S
Apply the existing but unused validate_proof_file_size and validate_proof_file_extension to Profile.registration_proof.
Add the same validators to ExcuseSlip.attachment.
Enforce: 5 MB cap, allowlist of PDF/JPG/JPEG/PNG/WEBP, magic-byte check via Pillow, reject SVG/HTML, sanitize filenames.
Files: models/profile.py, models/excuse.py, forms/registration_form.py, validators/identity_validators.py
Purpose: prevents executable uploads and denial-of-service through oversized files.
1.4 — One Password Policy M
Route every password-setting path through Django’s validate_password: custom reset, teacher create/edit, CSV import.
Align the front-end rule (currently 6 characters) with the backend policy.
Add a must_change_password flag and a forced-change page for imported/default-password accounts (requires migration).
Remove or deprecate the unused admin_reset_teacher_password; make the canonical reset service emit an audit event.
Files: auth_views.py, auth_helpers.py, teacher_service.py, teacher_views.py, student_service.py, models/profile.py, reset_password_modal.js
Purpose: removes weak passwords, predictable shared defaults, and an unaudited high-privilege reset path.
1.5 — Explicit State Transitions + Audit M
Replace blind toggles with explicit activate / deactivate actions for teacher, subject, class, and user accounts.
Subject deactivation must block or warn when live classes exist; a forced deactivation must be audited with a reason.
Make single-row actions behave exactly like the new bulk teacher actions.
Every state change writes AuditEvent with old value, new value, actor, and reason.
Files: teacher_views.py, subject_views.py, class_views.py ⚠️, apps/users/views.py, related JS/templates
Purpose: prevents accidental double-click flips and produces a defensible trail of who changed what.
1.6 — Session Integrity M
Validate that a supplied slot_id belongs to the class and matches today’s weekday; reject mismatches.
Remove silent reopening of closed sessions. Add an explicit “Reopen Session” action with a reason, a time limit, and an audit event.
Prevent duplicate open sessions for the same slot and date.
When a class is deactivated, block deactivation if open sessions exist, or close them with an audit record.
Files: session_views.py, class_views.py ⚠️, teacher templates
Purpose: attendance can currently be recorded against the wrong schedule or after a session was intentionally closed.
1.7 — Shared Lockout & Cache State M
Move failed-login counters out of request.session into a server-side cache keyed by username + IP, with a TTL.
Replace LocMemCache for anti-replay and rate-limit keys with the database cache or Redis.
Configure the cache backend in base.py, dev.py, and prod.py.
Files: auth_views.py, auth_helpers.py, session_views.py, mysite/settings/*
Purpose: login lockout currently disappears when a cookie is cleared, and anti-replay protection breaks as soon as the app runs more than one worker.
1.8 — Spreadsheet Export Sanitization S
Add a shared safe_spreadsheet_cell() helper.
Prefix cells starting with =, +, -, @, tab, or carriage return with a single quote.
Apply it to every CSV and XLSX writer: audit log, user list, class roster, session reports.
Files: export_service.py, audit_views.py, apps/users/views.py, class_views.py ⚠️, session_views.py
Purpose: prevents formula injection when staff open exported student data in Excel.
1.9 — Batch Validation Hardening S
Replace broad except Exception with specific exceptions.
Process each row in its own savepoint; return a structured per-row result instead of raw error strings.
Audit the batch summary and partial failures.
Files: validation_views.py
Purpose: partial failures become diagnosable without leaking internals or aborting the whole batch.
Phase 2 — Data Integrity (P1)
2.1 — End-of-Term Control Center L
This is the main redesign.

New PromotionBatch model: actor, scope, counts, snapshot, created/reversed timestamps (migration).
Preview who moves up, who graduates, who is retained, and who has incomplete records.
Scope by program, year level, or section — never the whole school in one click.
Explicit outcomes: promoted, graduated/alumni, retained, dropped.
Rollover: archive old classes and enrollments; create or map next-year sections; switch the active academic year.
Safety: dry-run, confirmation phrase, per-student audit, and a time-limited “Revert Batch” action.
Output: downloadable term-close report for the registrar.
Files: academic_service.py, academic_year_views.py, new service/view/template/JS, models/audit.py or new model
Purpose: promotion is currently global, irreversible, and recorded only as a count. This makes it controlled, reversible, and defendable.
2.2 — Enrollment Conflicts + Capacity M
Wrap enrollment in a transaction and lock the class row with select_for_update().
Re-check capacity inside the transaction.
Query for timetable overlap against the student’s active enrollments: same academic year, overlapping weekday and time range.
Return clear conflict messages naming the clashing class.
Files: class_views.py ⚠️, services/academic_service.py
Purpose: prevents double-booked students and capacity overruns under concurrent enrollment.
2.3 — Scan Concurrency S
Replace the check-then-create flow with get_or_create plus IntegrityError handling.
Return an idempotent “already recorded” response instead of a 500.
Add a transaction test that simulates two simultaneous scans.
Files: session_views.py
Purpose: duplicate scans should be a normal outcome, not a server error.
2.4 — Audit Completeness + Retention M
Add a central log_audit() helper and make every mutation route use it: teacher, subject, class, user, academic year, enrollment, session, validation, backup.
Add python manage.py audit_integrity to detect drift: orphaned profiles, enrollments in inactive classes, sessions without slots, duplicate open sessions, offline badges belonging to rotated secrets, attendance outside session windows, missing files.
Document the retention policy for audit records and uploaded documents.
Files: models/audit.py, all mutation views, new management command
Purpose: gives you a way to detect data corruption before a user reports it.
2.5 — Academic Year Guard S
Block activating a new academic year while the outgoing year still has open sessions, active classes, or pending validations — or require an explicit force with audit.
Snapshot the outgoing year before switching.
Files: academic_service.py, academic_year_views.py
Purpose: prevents half-switched terms where classes belong to one year but attendance belongs to another.
Phase 3 — Operations (P1/P2)
3.1 — Backup + Restore Workflow M
Add a backup_database management command with retention count, timestamped filename, and checksum.
Document a tested restore_database procedure.
Show “last successful backup” on the admin dashboard.
Add scheduler instructions for Windows Task Scheduler or cron.
Files: backup_service.py, backup_views.py, new commands, admin template
Purpose: the current feature is download-only; recovery depends on someone remembering to click a button.
3.2 — Health Endpoint S
Add /health/ returning JSON: database connectivity, cache backend, media disk space, pending migrations, last backup timestamp.
Restrict to admin or a bearer token; never expose PII.
Files: new view + URL
Purpose: lets you monitor the system like a real deployment.
3.3 — Test Discovery + CI M
Fix apps/core/tests/__init__.py so manage.py test apps.core discovers all 375+ tests, not 59.
Add .github/workflows/ci.yml: MariaDB 10.5+ service, check, makemigrations --check, full test suite, coverage report.
Files: apps/core/tests/__init__.py, .github/workflows/ci.yml, requirements.txt
Purpose: regressions should fail automatically, not depend on someone running the full suite manually.
3.4 — README + Runbook S
Replace the 11-line stub with: prerequisites, .env setup, database creation, migrations, seed commands, demo accounts, how to run, how to test, backup/restore, troubleshooting, and an architecture map.
Files: README.md, docs/
Purpose: anyone — including panelists — can reproduce the system from scratch.
3.5 — Production Media & Security Config M
Private media root outside the web root.
nginx X-Accel-Redirect or Django FileResponse for protected files.
Database/Redis cache backend.
SECURE_PROXY_SSL_HEADER, logging, static file serving.
Re-run check --deploy.
Files: mysite/settings/prod.py, deployment docs
Purpose: the production configuration should not rely on Django’s development file server.
3.6 — Django 5.2 + MariaDB Upgrade L (blocked)
Back up the database first.
Upgrade XAMPP’s MariaDB to 10.5+ or install standalone MySQL 8.
Upgrade Django to 5.2 LTS, update requirements.txt, fix deprecations, run the full suite.
Purpose: Django 4.2 is past end-of-life and no longer receives security patches.
Phase 4 — Enhancements (P2)
4.1 — Notifications M
Email on account approval/rejection, excuse-slip decision, and absence-threshold crossing.
Use the console backend in development; SMTP in production.
Optional SMS integration later.
Purpose: students and faculty learn about problems without opening the portal.
4.2 — Parent/Guardian Read-Only View L
Add a guardian link to the student profile and an invite flow.
Read-only attendance summary scoped to one student.
Purpose: gives parents visibility without giving them admin access.
4.3 — Batch Credential Handoff Sheets S
Generate a printable PDF/CSV after import containing student number, temporary password, and first-login instructions.
Display once, never store the plaintext password, and audit the download.
Note: do not print QR codes — they rotate every 30 seconds. This replaces the “batch QR printing” idea with something that actually works.
Purpose: secure distribution of accounts to imported students.
4.4 — CHED/Registrar Reports M
Term attendance summary per student, class, program, and year level.
Absence-radar list for students approaching the 20% threshold.
Exportable PDF/XLSX with filters by academic year and program.
Purpose: turns attendance data into the reports the institution actually needs.
Rules for every item
Add or update tests; the full suite must stay green.
Add a migration if the schema changes.
Add an audit event if the action mutates data.
Update the relevant doc.
Do not touch the four uncommitted files until you confirm: apps/core/views/class_views.py, static/js/classes/section_wizard.js, templates/core/admin/class_wizard.html, templates/core/admin/subjects.html. Items 1.5, 1.6, and 2.2 will need them.