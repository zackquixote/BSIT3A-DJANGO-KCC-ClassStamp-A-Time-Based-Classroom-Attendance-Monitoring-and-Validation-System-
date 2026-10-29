# 📋 KCC ClassStamp — Master Improvement Roadmap
**System:** KCC ClassStamp: A Time-Based Classroom Attendance Monitoring & Validation System
**Last Updated:** October 28, 2026
**Total Improvements:** 53 items across 4 areas

> **Status Legend:**
> - ✅ **Done** — Fully implemented
> - 🟡 **Partial** — Backend/route exists, front-end or UI incomplete
> - ❌ **Not Built** — Feature not yet started

---

## 📑 Table of Contents
1. [Admin Portal Improvements (20)](#admin-portal--20-improvements)
2. [Teacher Portal Improvements (12)](#teacher-portal--12-improvements)
3. [Student Portal Improvements (9)](#student-portal--9-improvements)
4. [Backend & Technical Improvements (12)](#backend--technical--12-improvements)
5. [Summary & Build Order](#summary--recommended-build-order)

---

## 🛡️ Admin Portal — 20 Improvements

### 🔴 Urgent

#### A-01 — Batch / Bulk Validation Approval
- **Status:** ✅ Done (checkboxes + select-all + floating batch bar wired to `/validation/batch/`; endpoint runs in a single `transaction.atomic()` and emits a `BATCH_VALIDATION` audit entry)
- **Problem:** At semester start, hundreds of students register. Approving one-by-one is extremely tedious.
- **Solution:**
  - Add multi-select checkboxes to `/validation/pending/`
  - **Bulk Approve Selected (N):** Provisions QR secrets and emits batch audit logs in a single atomic transaction
  - **Bulk Reject Selected:** Opens a modal to apply a standard rejection reason to all selected students

#### A-02 — Slide-Over Dossier Preview Drawer
- **Status:** ✅ Done (2026-10-26) — Quick View button per pending row opens a slide-over dossier (photo/proof, all registration fields, prev/next navigation) fed by the new `validation_dossier_json` endpoint; keyboard shortcuts (J/K navigate, A approve via existing endpoint, R opens the reject modal, Esc closes); no page redirect needed
- **Problem:** Clicking a student redirects away to a detail page, breaking the review flow.
- **Solution:**
  - Off-canvas slide-over drawer directly on the validation queue
  - Preview COR/ID photo without page reload
  - Keyboard shortcuts: `A` = Approve, `R` = Reject, `J`/`K` = navigate, `Esc` = close

#### A-03 — In-Place Student Profile Editor Modal
- **Status:** ✅ Done (student directory rows have an Edit button opening a modal for Student ID, First/Last Name, Department, Program, Year Level, plus an optional "Reset QR secret" checkbox; saves via POST to `students/update/` AJAX endpoint with unique-student-number, department↔program, and year-vs-years_total validation; profile edits and QR resets are audited)
- **Problem:** No way for admin to fix typos in student number, name, or program without CLI access.
- **Solution:**
  - "Edit Profile" modal in Student Directory
  - Editable fields: Student ID, Full Name, Department, Program, Year Level
  - Option to reset student TOTP QR secret seed if compromised

### 🟡 High Priority

#### A-04 — Predefined Rejection Reason Templates
- **Status:** ✅ Done (standard templates "COR Unreadable", "ID Mismatch", "Wrong Program", "Duplicate Registration" as quick-select chips in all three reject modals: pending queue, batch reject, validation hub)
- **Solution:** Dropdown of standard rejection reasons: "COR Unreadable", "ID Mismatch", "Wrong Program", "Duplicate Registration"

#### A-05 — Real-Time Sidebar Pending Count Badge
- **Status:** ✅ Done (`sidebar_pending.js` polls `/api/admin/pending-count/` every 45s on every admin page; dashboard SSE handler also updates it live)
- **Solution:** Extend the existing poller to also update the sidebar badge without page reload

#### A-06 — End-of-Year Student Promotion Utility
- **Status:** ✅ Done (2026-10-27) — `promote_students` service advances all approved students one year level inside `transaction.atomic()` (capped at program duration), audits `PROMOTE_STUDENTS`, and is exposed as a 1-click confirm button on the student directory via `student_promote_all`; the academic-term rollover wizard now reuses the same promotion helper)

#### A-07 — Program-Centric Curriculum Matrix Builder
- **Status:** ✅ Done (2026-10-26) — Year × Semester grid modal on the Programs page; `Curriculum.semester` dimension added with unique (program, year_level, semester, subject); assign/remove via existing AJAX endpoints; new `program_curriculum_list` JSON endpoint; keyboard-free chip-based UI in `curriculum_matrix.js`)

### 🟢 Medium Priority

#### A-08 — Academic Term Rollover Wizard
- **Status:** ✅ Done (2026-10-26) — 4-step wizard modal on Academic Years page; atomic `rollover_academic_year` service creates the new active term, deactivates predecessors, optionally promotes approved students (+1 year, capped at program duration); audits CREATE_ACADEMIC_YEAR, TERM_ROLLOVER, PROMOTE_STUDENTS)

#### A-09 — Advanced Audit Log Multi-Filtering
- **Status:** ✅ Done (Actor filter added to the audit log page and CSV export alongside the existing category tabs, action dropdown, date filter, and search; dropdown lists distinct actor usernames with full names, filtering matches exact username, and the CSV export applies the same actor filter)

#### A-10 — CSV Import Validation Preview (3-Step)
- **Status:** ✅ Done (2026-10-27) — Upload → Preview & Validate → Confirm. `import_students_from_csv(..., dry_run=True)` returns a per-row verdict list (valid/invalid + reason) without writing anything; the preview page renders a scrollable verdict table with valid/invalid counts and a disabled-confirm state when 0 rows are valid; the CSV text round-trips through a hidden field so no session storage is needed; legacy direct-upload path preserved)

#### A-11 — Subject Prerequisite Mapping
- **Status:** ❌ Not Built
- **Solution:** Link subjects as prerequisites (e.g. IT211 requires IT111); prevent duplicate course codes

#### A-12 — Teacher Department Reassignment Modal
- **Status:** ✅ Done (2026-10-27) — Each teacher row has a reassign button that opens a modal showing name, current department, and intact teaching-load count; `POST /teachers/<pk>/reassign/` (`teacher_reassign_ajax` → `reassign_teacher_department`) moves the teacher, leaves assigned classes untouched, and audits `TEACHER_REASSIGNED` with old/new department; same-department transfers are rejected 400)
- **Solution:** Quick modal to transfer a teacher between academic departments with load overview

#### A-13 — Student TOTP QR Secret Reset Button
- **Status:** ✅ Done (2026-10-27) — Shield button on each student directory row calls `student_qr_reset_ajax`, which rotates the 64-char TOTP seed, invalidates all unconsumed offline badges, and audits `STUDENT_QR_RESET` with a security-reset reason)

#### A-19 — Section Builder Wizard & Timetable Conflict Detection
- **Status:** ✅ Done (2026-10-27) — 5 phases shipped:
  - **P1 Model foundation:** nullable `program` + `year_level` FKs on `Class` (migration 0009); `assign_class` accepts them; idempotent `backfill_class_program` command parses `BSIT-3A`-style legacy codes.
  - **P2 `schedule_service.py`:** `detect_slot_conflicts` (same-weekday interval overlap for teacher/room; boundary-touch = no clash; TBA rooms never clash), `suggest_section_letter`, `eligible_teachers_for(program)`; wired into the existing slot modal (teacher double-book = hard block, room clash = warning).
  - **P3 Wizard endpoints:** `class_wizard_options` (program+year+semester → curriculum subjects, ranked teachers, suggested code) and atomic `class_wizard_save` (class + slots + audits).
  - **P4 Wizard UI:** `/classes/setup/` 5-step flow — Term → Offering → Teacher → Section → Schedule (Mon–Sat time click-grid with live conflict highlights) → Review; verified end-to-end in browser (golden path created a section with 2 slots).
  - **P5 Wrap:** 31 tests in `test_week7.py`; full suite green.
  - **Problem solved:** building a section no longer spans five pages; hand-typed codes are auto-suggested; double-bookings are caught at save time.

#### A-20 — Organisation Flow Consolidation
- **Status:** ✅ Done (2026-10-28) — answers "which section is the student in?" from both directions and removes duplicated feature paths:
  - **P1 Section identity & enlistment:** student directory "Enrolled Section(s)" column scoped to the active academic year with ACTIVE tags (clickable → filtered directory) and amber Pending tags; "Unassigned (no section)" filter option; roster modal gained program/year candidate filters, a seats counter, and a batch "Enlist All Matching Students" endpoint (`class_roster_enroll_batch` — capacity-guarded, reactivates withdrawn enrollments, one audit event per student).
  - **P2 One way to create a section:** the classes page "Create Class Section" button now points at the Section Wizard; the legacy create modal, its subject-cascade JS, and the create path of `class_save` were removed (edit modal retained; `class_save` rejects POSTs without `class_id`).
  - **P3 Curriculum single-owner:** Subjects page lost its Curriculum Mapping modal and inline assign section (read-only count badge retained, "managed in Programs → Curriculum Matrix"); the assign/remove AJAX endpoints moved under `/programs/curriculum/*`; `subject_curriculum_list` deleted; `curriculum_modal.js` deleted. The Programs matrix builder (A-07) is now the only curriculum editor.
  - **P4 Sidebar & coherence:** Organisation menu reordered to Academic Years → Departments → Programs → Subjects → Teachers → Classes & Schedules; Subjects page retitled "Subject Catalogue".
  - **Tests:** 19 new tests in `test_week8.py` + render smoke tests; full suite 354/354 green.

### ⚪ Polish

#### A-14 — Printable PVC Student ID Badge Generator
- **Status:** ❌ Not Built
- **Solution:** CR80 card format PDF with photo, barcode, program name, emergency contact

#### A-15 — 1-Click Database Backup Button
- **Status:** ✅ Done (2026-10-27) — "Database Backup" launcher on the admin dashboard streams a gzip-compressed mysqldump snapshot (`classstamp_backup_<timestamp>.sql.gz`) via `backup_service.stream_database_backup`; password passed through the `MYSQL_PWD` env var so it never appears in the process list; gzip produced with zlib (`wbits=31`) so no external gzip binary is needed; every download audited as `DB_BACKUP_DOWNLOAD`; a missing mysqldump shows a friendly message and redirects instead of 500ing)
- **Solution:** Admin panel button to download compressed `.sql.gz` database snapshot

#### A-16 — Storage Optimizer (Auto WebP Compression)
- **Status:** ✅ Done (2026-10-27) — `storage_optimizer.optimize_proof_upload` is hooked into account provisioning: raster proofs (jpg/png/webp/bmp/tif) are downscaled to ≤1600px and re-encoded as WebP quality 80; PDFs and unreadable/corrupt files pass through unchanged so registration never breaks on a bad upload)
- **Solution:** Auto-compress uploaded COR/ID photos to WebP format on upload

#### A-17 — Dossier Cleanup Tool
- **Status:** ❌ Not Built
- **Solution:** Purge rejected registration attachments older than 60 days for data privacy compliance

#### A-18 — Non-Blocking Toast Notifications System-Wide
- **Status:** ✅ Done (all eight legacy module `showAlert` implementations — teachers, subjects, users, departments, programs, academic years, info delete, scanner — now delegate to the unified `window.App.toast` in `app_toasts.js`, with their inline banners kept as fallbacks; removed dual-call sites that would double-toast in subjects add/delete, academic-year activation, teaching-load, and teacher toggle; fixed `academic_calendar.js`, which called a never-defined `window.showToast`, via a delegating shim)
- **Solution:** Replace all remaining `alert()`/`confirm()` popups with smooth async toast notifications

---

## 👨‍🏫 Teacher Portal — 12 Improvements

### 🔴 Urgent

#### T-01 — CHED 20% Absence Radar Badges
- **Status:** ✅ Done (`absence_radar.py` helper classifies per-student unexcused absence rates via one aggregated query; teacher dashboard class cards show 🔴 FDA-risk / 🟡 watchlist chips; live scanner roster rows show colored band dots with rate tooltips; EXCUSED excluded, zero records = Safe)
- **Institutional Rule:** Students exceeding 20% unexcused absences → Failure Due to Absences (FDA)
- **Solution:**
  - Compute absence % per student per class
  - 🟢 Safe (<10%) | 🟡 Watchlist (10-19%) | 🔴 Critical FDA Risk (≥20%)
  - Visible on teacher dashboard and live scanner roster

#### T-02 — Live Interactive Attendance Matrix During Session
- **Status:** ✅ Done (scanner has a List/Grid view toggle; grid mode renders each student as a color-coded cell 🟢 Present | 🟡 Late | 🔴 Absent | 🔵 Excused | ⚪ Pending; live counter line `Present: 28 | Late: 4 | Absent: 3 | Excused: 1 | Total: 36 (88.9%)` updates on scan, override, and a 10s poll of the new `teacher/session/<id>/roster/` JSON endpoint, which also syncs changes from other terminals)
- **Solution:**
  - Real-time color-coded grid: 🟢 Present | 🟡 Late | 🔴 Absent | 🔵 Excused
  - Live header counter: `Present: 28 | Late: 4 | Absent: 3 | Total: 35 (91.4%)`

#### T-03 — 1-Click Manual Override in Scanner
- **Status:** ✅ Done (override modal with status dropdown + reason field is wired in the scanner via `scanner_ui.js` → POST `/session/<id>/override/` with in-place roster refresh)
- **Original ask:** Click student in live roster → Quick Override Drawer with reason dropdown; implemented as a modal instead of a slide-out drawer

### 🟡 High Priority

#### T-04 — Registrar-Format Excel Export (Term-Wide)
- **Status:** ✅ Done (`teacher_class_term_export` streams an .xlsx per class section via openpyxl: one column per meeting (Week N with date), per-student P/L/A/E letters, Total Present/Late/Absent and Attendance % columns, frozen header, and red fill + bold red % on rows whose unexcused absence rate reaches the CHED 20% threshold; button on the attendance matrix page)
- **Solution:**
  - Columns: Student ID | Name | Week 1-18 Dates | Total Present | Total Late | Total Absent | % Attendance
  - Export options: Single Session, Midterm (Weeks 1-9), Finals (Weeks 1-18)
  - Red conditional formatting for high-absence students

#### T-05 — Consecutive 3-Absence Sentinel
- **Status:** ✅ Done (teacher dashboard scans each class's newest records per student and flags students whose leading run of unexcused ABSENT statuses is 3 or more; purple pill chips on the class card show name, student number, and streak length; helper also exposes an `absent_streak_students` aggregate)

#### T-06 — Midterm / Final Term Attendance Split Export
- **Status:** ✅ Done (2026-10-27) — `?range=midterm|finals|all` on `teacher_class_term_export` slices to the first 9 / 18 meetings; worksheet title and xlsx filename reflect the range; the matrix page now offers Term, Midterm, and Finals Excel buttons)

### 🟢 Medium Priority

#### T-07 — Kiosk / Projector Mode for Self-Scanning
- **Status:** ✅ Done (2026-10-26) — Fullscreen kiosk overlay on the scanner page (Fullscreen API with overlay fallback); large projector-sized stamp feedback; student number masked (last 4 digits only); result auto-hides after 2.5s back to the idle scan frame; Escape or fullscreen exit closes kiosk mode)

#### T-08 — Attendance Heatmap & Trends
- **Status:** ❌ Not Built
- **Solution:** Day-of-week attendance trend chart; chronic latecomer detection per student

#### T-09 — Makeup / Special Session Logging
- **Status:** ❌ Not Built
- **Solution:** Teacher opens a Special/Makeup Session linked to original missed date with reason

#### T-10 — Walk-In / Add-Drop Student Support
- **Status:** ❌ Not Built
- **Solution:** During first 2 weeks of semester, teacher can accept unregistered student scans as Walk-In

### ⚪ Polish

#### T-11 — Substitute Teacher Delegation
- **Status:** ❌ Not Built
- **Solution:** Department Chair assigns temp scan permissions to substitute faculty for a specific date only

#### T-12 — Offline Camera Buffer (IndexedDB)
- **Status:** ✅ Done (2026-10-26) — `offline_buffer.js` queues failed scans in IndexedDB (`classstamp-offline`), auto-flushes on the `online` event and page load, shows a "queued offline" badge, and permanently drops server-rejected scans (expired TOTP tokens can never become valid again; server-side anti-replay still guards each flush)

---

## 🎓 Student Portal — 9 Improvements

### 🔴 Urgent

#### S-01 — Animated SVG Countdown Ring on QR Badge
- **Status:** ✅ Done (SVG circular ring replaces the linear bar; counts down the 30s TOTP window and pulses when the token rotates)
- **Solution:** Replace progress bar with animated SVG circular countdown ring; pulses on 30s reset

#### S-02 — QR Badge Photo Watermark
- **Status:** ✅ Done (2026-10-27) — The badge header renders the uploaded COR/ID photo (when it is an image) with a rotated, semi-transparent student-number watermark overlaid via `badge-id-photo__watermark`; the watermark is baked into the DOM so screenshots carry the number — a proxy-sharing deterrent; non-image proofs (e.g. PDF) skip the photo block)
- **Solution:** Overlay student photo + student ID on QR badge card to deter proxy sharing

#### S-03 — Per-Subject Attendance Breakdown Cards
- **Status:** ✅ Done (student dashboard "Attendance Breakdown by Subject" card renders one panel per enrolled class: subject + class code, instructor, compliance % badge (green ≥90, amber ≥80, red <80), Present/Late/Absent/Excused count tiles, and an expandable meeting-by-meeting log with per-session status and late minutes)
- **Solution:**
  - One card per enrolled class: Subject Code, Instructor, Present/Late/Absent/Excused counts, compliance %
  - Expandable meeting-by-meeting session log

### 🟡 High Priority

#### S-04 — CHED 20% Early-Warning Sentinel
- **Status:** ✅ Done (each per-subject breakdown card on the student dashboard now shows a 4-stage unexcused-absence sentinel banner computed from ABSENT ÷ total records: 🟢 <10% "Excellent Attendance", 🟡 10-15.9% "Caution", 🟠 16-19.9% "Warning", 🔴 ≥20% "Exceeded threshold — Contact Instructor/Dean"; classes with no meetings show "No meetings yet")
- **Solution:** 4-stage color progression per subject:
  - 🟢 <10% — "Excellent Attendance"
  - 🟡 10-15% — "Caution" amber alert
  - 🟠 16-19% — Orange warning banner
  - 🔴 ≥20% — Red critical: "Exceeded threshold — Contact Instructor/Dean"

#### S-05 — Visual Weekly Timetable Grid
- **Status:** ✅ Done (student dashboard "Examination Windows & Timetable" card now renders a Mon-Sat color-coded weekly grid from the enrolled classes' active slots — six day columns, today's column highlighted gold with a TODAY badge, and per-slot blocks with time, subject·class, room, and a rotating palette accent; Sunday and inactive slots are excluded)

#### S-06 — Detailed Meeting-by-Meeting Attendance Log
- **Status:** ✅ Done (2026-10-27) — attendance log upgraded with a GET filter bar (status dropdown and class selector scoped to enrolled classes) and a Time column showing the scheduled slot window; view validates and passes the filters through, with a filtered-empty state)

### 🟢 Medium Priority

#### S-07 — Offline QR Badge (PWA / Local Storage)
- **Status:** ✅ Done (2026-10-26) — SECURITY REDESIGN: TOTP secrets are never stored client-side. Instead the server issues a single-use `OfflineBadge` (48h expiry) whose raw 64-hex token is shown once and stored only as a SHA-256 hash. The scan pipeline accepts `classstamp:offline:<student_number>:<token>`, atomically redeems the badge (select_for_update), stamps PRESENT/LATE, and audits REDEEM_OFFLINE_BADGE. Students issue/replace badges from their QR badge page (`offline_badge.js`).)

#### S-08 — Online Excuse Slip Submission Workflow
- **Status:** ✅ Done (2026-10-26) — Students file slips against ABSENT records (reason + optional attachment); `ExcuseSlip` model (unique per student/session); instructor review queue page with approve (absence converts to EXCUSED via upserted record) or reject (note required); audits EXCUSE_SUBMITTED / EXCUSE_APPROVED / EXCUSE_REJECTED; sidebar links for both roles)

### ⚪ Polish

#### S-09 — Excuse Slip Status Tracker
- **Status:** ✅ Done (2026-10-27) — "My Excuse Slips" card on the student dashboard lists the 10 most recent slips with Pending/Approved/Rejected count badges, per-slip subject·class, session date, status badge, truncated reason, reviewer note on rejection, and submitted timestamp, linking to the full slip list)

---

## ⚙️ Backend & Technical — 6 Improvements

#### B-01 — Pin All Dependency Versions
- **Status:** ✅ Done (2026-10-27) — `requirements.txt` pins exact versions: Django==4.2.30, mysqlclient==2.2.8, openpyxl==3.1.5, python-dotenv==1.1.1, pyotp==2.10.0, qrcode==8.2, Pillow==12.1.1)

#### B-02 — Split `session_views.py` (43KB)
- **Status:** ❌ Not Done
- **Solution:** Extract into `session_lifecycle.py`, `session_scan.py`, `session_export.py`, `session_override.py`

#### B-03 — Run Test Coverage Report
- **Status:** ✅ Measured (2026-10-27) — `python -m coverage run --source=apps.core manage.py test apps.core --noinput` then `coverage report`: **79%** line coverage across apps.core (8,164 statements, 1,729 missed), well above the ≥60% target

#### B-04 — N+1 Query Audit on Remaining Views
- **Status:** ❌ Not Done
- **Solution:** Install `django-debug-toolbar` and audit all views beyond the already-fixed `teacher_list`

#### B-05 — WebSocket Upgrade for Live Feed
- **Status:** 🟡 Partial — an SSE live stream (`/admin/live-stream/` + `EventSource`) ALREADY exists alongside the 30-second AJAX polling to `/api/admin/activity-feed/`
- **Current:** Hybrid SSE + 30-second AJAX polling
- **Solution:** Consolidate on one mechanism (SSE short-term, Django Channels only if multi-user push is required)

#### B-06 — `.env` Validation on Server Startup
- **Status:** ❌ Not Built
- **Solution:** Startup check that asserts all required env vars are present with clear error messages before Django starts

#### B-07 — Attendance Anomaly / Fraud Detection Subsystem
- **Status:** ✅ Done — 8 automated detectors wired into the scan pipeline and override controller: token replay across sessions, duplicate stamp attempts, rapid-scan proxy bursts, off-schedule window stamps, schedule conflicts, token brute-force storms, and post-close overrides
- **Extras included:** TOTP forensics (`StampAttempt.token_bucket`/`token_age_s` now populated), fail-open detector execution, adjudication fixes (shared decision mapping, atomic writes, record side effects: CONFIRM_PROXY → ABSENT, EXCUSE → EXCUSED), append-only DB triggers ported into migrations

#### B-08 — Anomaly Backfill & Re-Trigger Policy
- **Status:** ✅ Done — `backfill_anomalies` management command replays deterministic detectors over historical data (`--dry-run`, `--since`, `--session-id`, `--rules`); resolved flags automatically re-open (OPEN + audit trail) when their rule re-triggers

#### B-09 — Session-Timeout LOGIN_URL Bug
- **Status:** ✅ Done (`LOGIN_URL = '/'` in base settings; timeout redirects and AJAX 401s now carry the real login route instead of the default `/accounts/login/` 404)
- **Problem:** 30-minute inactivity timeout redirects to `/accounts/login/` which does not exist → 404 instead of the login page
- **Solution:** Point `LOGIN_URL` at the project's actual login route (`login`)

#### B-10 — Django 4.2 → 5.2 LTS Upgrade
- **Status:** ❌ Not Built — **BLOCKED (2026-10-27):** Django 5.2 requires MariaDB 10.5+, but the XAMPP environment ships MariaDB 10.4.32 (`NotSupportedError: MariaDB 10.5 or later is required`). Requires a database upgrade (XAMPP upgrade or standalone MariaDB 10.5+/MySQL 8) before the framework upgrade can proceed. Downgrading to 5.1/5.0 is not viable — all pre-5.2 lines are already past extended support.
- **Problem:** Django 4.2.30 reached end-of-life in April 2026; no more security patches
- **Solution:** Upgrade to Django 5.2 LTS, re-run the full test suite, and verify mysqlclient compatibility

#### B-11 — Shared Cache Backend for Anti-Replay / Rate Limits
- **Status:** ❌ Not Built
- **Problem:** Default `LocMemCache` is per-process — token consumption and scan rate-limit state silently reset across workers under any multi-process deployment (gunicorn)
- **Solution:** Move to Redis (or database cache) so anti-replay and throttling survive process restarts and multiple workers

#### B-12 — Automatic Session Close Scheduler
- **Status:** ✅ Done — `auto_close_sessions` management command closes OPEN sessions past `slot.ends_at` (Asia/Manila wall-clock), auto-marks unscanned active enrollees ABSENT (METHOD_SYSTEM), sets `auto_closed=True`, and audits (`--dry-run`, `--grace-minutes`); schedule with cron `*/5 * * * *`
- **Problem:** `ClassSession.auto_closed` is dead code — no scheduler ever closes sessions left OPEN; students can be stamped hours after class ends (now flagged as an anomaly, but not prevented)
- **Solution:** Management command / cron that auto-closes OPEN sessions past `slot.ends_at` and sets `auto_closed=True`

---

## 📊 Summary & Recommended Build Order

### Count by Status

| Portal | ✅ Done | 🟡 Partial | ❌ Not Built | Total |
|---|---|---|---|---|
| 🛡️ Admin | 17 | 0 | 3 | **20** |
| 👨‍🏫 Teacher | 8 | 0 | 4 | **12** |
| 🎓 Student | 9 | 0 | 0 | **9** |
| ⚙️ Backend | 6 | 1 | 5 | **12** |
| **TOTAL** | **40** | **1** | **12** | **53** |

---

### 🚀 Recommended Build Order

#### Week 1 — Quick Wins (APIs already exist, just wire front-end)
| ID | Feature | Why Easy |
|---|---|---|
| T-03 | Override drawer in scanner | API already exists |

#### Week 2 — Core UX ✅ Complete (2026-10-26)
| ID | Feature |
|---|---|
| A-03 | In-place student profile editor modal |
| S-03 | Per-subject attendance breakdown cards |
| A-18 | System-wide toast notification cleanup |

#### Week 3 — Reports & Analytics ✅ Complete (2026-10-26)
| ID | Feature |
|---|---|
| T-04 | Registrar term-wide Excel export |
| S-04 | CHED early-warning 4-stage sentinel |
| S-05 | Weekly visual timetable grid |
| A-09 | Actor filter for audit log |
| T-05 | Consecutive 3-absence sentinel alert |

#### Week 4+ — Advanced Features ✅ Complete (2026-10-26)
| ID | Feature |
|---|---|
| A-02 | Slide-over dossier drawer |
| A-07 | Curriculum matrix builder |
| A-08 | Term rollover wizard |
| T-07 | Kiosk / projector mode |
| S-07 | Offline PWA QR badge |
| S-08 | Excuse slip upload workflow |
| T-12 | Offline camera buffer (IndexedDB) |

#### Week 7 — Section Builder & Schedules ✅ Complete (2026-10-27)
| ID | Feature |
|---|---|
| A-19 | 5-step Section Builder Wizard + timetable conflict detection |

#### Week 8 — Organisation Flow Consolidation ✅ Complete (2026-10-28)
| ID | Feature |
|---|---|
| A-20 | Single section-creation path, curriculum single-owner, section identity & batch enlistment |

---

*This document is the single source of truth for all KCC ClassStamp improvement items.*
*Update the Status field of each item as it is completed.*
