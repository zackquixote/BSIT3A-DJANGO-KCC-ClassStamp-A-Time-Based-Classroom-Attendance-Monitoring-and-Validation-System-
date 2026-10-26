# 📋 KCC ClassStamp — Master Improvement Roadmap
**System:** KCC ClassStamp: A Time-Based Classroom Attendance Monitoring & Validation System
**Last Updated:** October 26, 2026
**Total Improvements:** 51 items across 4 areas

> **Status Legend:**
> - ✅ **Done** — Fully implemented
> - 🟡 **Partial** — Backend/route exists, front-end or UI incomplete
> - ❌ **Not Built** — Feature not yet started

---

## 📑 Table of Contents
1. [Admin Portal Improvements (18)](#admin-portal--18-improvements)
2. [Teacher Portal Improvements (12)](#teacher-portal--12-improvements)
3. [Student Portal Improvements (9)](#student-portal--9-improvements)
4. [Backend & Technical Improvements (12)](#backend--technical--12-improvements)
5. [Summary & Build Order](#summary--recommended-build-order)

---

## 🛡️ Admin Portal — 18 Improvements

### 🔴 Urgent

#### A-01 — Batch / Bulk Validation Approval
- **Status:** ✅ Done (checkboxes + select-all + floating batch bar wired to `/validation/batch/`; endpoint runs in a single `transaction.atomic()` and emits a `BATCH_VALIDATION` audit entry)
- **Problem:** At semester start, hundreds of students register. Approving one-by-one is extremely tedious.
- **Solution:**
  - Add multi-select checkboxes to `/validation/pending/`
  - **Bulk Approve Selected (N):** Provisions QR secrets and emits batch audit logs in a single atomic transaction
  - **Bulk Reject Selected:** Opens a modal to apply a standard rejection reason to all selected students

#### A-02 — Slide-Over Dossier Preview Drawer
- **Status:** ❌ Not Built
- **Problem:** Clicking a student redirects away to a detail page, breaking the review flow.
- **Solution:**
  - Off-canvas slide-over drawer directly on the validation queue
  - Preview COR/ID photo without page reload
  - Keyboard shortcuts: `A` = Approve, `R` = Reject, `J`/`K` = navigate, `Esc` = close

#### A-03 — In-Place Student Profile Editor Modal
- **Status:** ❌ Not Built
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
- **Status:** ❌ Not Built
- **Solution:** 1-click batch promote all approved students (`year_level += 1`); 4th Year → Alumni status

#### A-07 — Program-Centric Curriculum Matrix Builder
- **Status:** ❌ Not Built
- **Solution:** Visual Year × Semester grid inside each Program page to add/remove subjects

### 🟢 Medium Priority

#### A-08 — Academic Term Rollover Wizard
- **Status:** ❌ Not Built
- **Solution:** Guided 4-step: pick new term → deactivate old → optional promotion → audit log

#### A-09 — Advanced Audit Log Multi-Filtering
- **Status:** 🟡 Partial (category tabs, action dropdown, date filter, and search already exist — only an **Actor** filter is missing)
- **Solution:** Add Actor filter alongside the existing category/action/date/search controls

#### A-10 — CSV Import Validation Preview (3-Step)
- **Status:** 🟡 Partial (direct import exists — preview step missing)
- **Solution:** Upload → Preview & flag invalid rows → Confirm import

#### A-11 — Subject Prerequisite Mapping
- **Status:** ❌ Not Built
- **Solution:** Link subjects as prerequisites (e.g. IT211 requires IT111); prevent duplicate course codes

#### A-12 — Teacher Department Reassignment Modal
- **Status:** ❌ Not Built
- **Solution:** Quick modal to transfer a teacher between academic departments with load overview

#### A-13 — Student TOTP QR Secret Reset Button
- **Status:** ❌ Not Built
- **Solution:** Admin button to rotate a student's 64-char TOTP seed if compromised; logged in audit trail

### ⚪ Polish

#### A-14 — Printable PVC Student ID Badge Generator
- **Status:** ❌ Not Built
- **Solution:** CR80 card format PDF with photo, barcode, program name, emergency contact

#### A-15 — 1-Click Database Backup Button
- **Status:** ❌ Not Built
- **Solution:** Admin panel button to download compressed `.sql.gz` database snapshot

#### A-16 — Storage Optimizer (Auto WebP Compression)
- **Status:** ❌ Not Built
- **Solution:** Auto-compress uploaded COR/ID photos to WebP format on upload

#### A-17 — Dossier Cleanup Tool
- **Status:** ❌ Not Built
- **Solution:** Purge rejected registration attachments older than 60 days for data privacy compliance

#### A-18 — Non-Blocking Toast Notifications System-Wide
- **Status:** 🟡 Partial (done in some views)
- **Solution:** Replace all remaining `alert()`/`confirm()` popups with smooth async toast notifications

---

## 👨‍🏫 Teacher Portal — 12 Improvements

### 🔴 Urgent

#### T-01 — CHED 20% Absence Radar Badges
- **Status:** ❌ Not Built
- **Institutional Rule:** Students exceeding 20% unexcused absences → Failure Due to Absences (FDA)
- **Solution:**
  - Compute absence % per student per class
  - 🟢 Safe (<10%) | 🟡 Watchlist (10-19%) | 🔴 Critical FDA Risk (≥20%)
  - Visible on teacher dashboard and live scanner roster

#### T-02 — Live Interactive Attendance Matrix During Session
- **Status:** 🟡 Partial (`matrix.html` exists for post-session — live in-session grid not built)
- **Solution:**
  - Real-time color-coded grid: 🟢 Present | 🟡 Late | 🔴 Absent | 🔵 Excused
  - Live header counter: `Present: 28 | Late: 4 | Absent: 3 | Total: 35 (91.4%)`

#### T-03 — 1-Click Manual Override in Scanner
- **Status:** ✅ Done (override modal with status dropdown + reason field is wired in the scanner via `scanner_ui.js` → POST `/session/<id>/override/` with in-place roster refresh)
- **Original ask:** Click student in live roster → Quick Override Drawer with reason dropdown; implemented as a modal instead of a slide-out drawer

### 🟡 High Priority

#### T-04 — Registrar-Format Excel Export (Term-Wide)
- **Status:** 🟡 Partial (single-session export exists — full term sheet missing)
- **Solution:**
  - Columns: Student ID | Name | Week 1-18 Dates | Total Present | Total Late | Total Absent | % Attendance
  - Export options: Single Session, Midterm (Weeks 1-9), Finals (Weeks 1-18)
  - Red conditional formatting for high-absence students

#### T-05 — Consecutive 3-Absence Sentinel
- **Status:** ❌ Not Built
- **Solution:** Alert teacher when student misses 3 consecutive meetings; "Generate Absence Notice" button

#### T-06 — Midterm / Final Term Attendance Split Export
- **Status:** ❌ Not Built
- **Solution:** Separate export buttons for Midterm (Weeks 1-9) and Finals (Weeks 1-18)

### 🟢 Medium Priority

#### T-07 — Kiosk / Projector Mode for Self-Scanning
- **Status:** ❌ Not Built
- **Solution:** Full-screen self-scanning mode; shows first name + status; auto-hides after 2.5s; masks student number

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
- **Status:** ❌ Not Built
- **Solution:** Queue QR scans locally during Wi-Fi drops; flush to backend on reconnect with anti-replay protection

---

## 🎓 Student Portal — 9 Improvements

### 🔴 Urgent

#### S-01 — Animated SVG Countdown Ring on QR Badge
- **Status:** ✅ Done (SVG circular ring replaces the linear bar; counts down the 30s TOTP window and pulses when the token rotates)
- **Solution:** Replace progress bar with animated SVG circular countdown ring; pulses on 30s reset

#### S-02 — QR Badge Photo Watermark
- **Status:** ❌ Not Built
- **Solution:** Overlay student photo + student ID on QR badge card to deter proxy sharing

#### S-03 — Per-Subject Attendance Breakdown Cards
- **Status:** ❌ Not Built (dashboard only shows total aggregate counts)
- **Solution:**
  - One card per enrolled class: Subject Code, Instructor, Present/Late/Absent/Excused counts, compliance %
  - Expandable meeting-by-meeting session log

### 🟡 High Priority

#### S-04 — CHED 20% Early-Warning Sentinel
- **Status:** ❌ Not Built
- **Solution:** 4-stage color progression per subject:
  - 🟢 <10% — "Excellent Attendance"
  - 🟡 10-15% — "Caution" amber alert
  - 🟠 16-19% — Orange warning banner
  - 🔴 ≥20% — Red critical: "Exceeded threshold — Contact Instructor/Dean"

#### S-05 — Visual Weekly Timetable Grid
- **Status:** 🟡 Partial (enrolled classes listed as text — visual grid not built)
- **Solution:** Mon-Sat color-coded schedule blocks; today highlighted in gold; "Today's Badge" quick-jump

#### S-06 — Detailed Meeting-by-Meeting Attendance Log
- **Status:** 🟡 Partial (`attendance_log.html` exists — detail level may be insufficient)
- **Solution:** Per session: Date, Time, Status, Method (QR Scan vs Manual Teacher Override); filterable

### 🟢 Medium Priority

#### S-07 — Offline QR Badge (PWA / Local Storage)
- **Status:** ❌ Not Built — ⚠️ **SECURITY REVIEW REQUIRED:** storing the TOTP *secret* client-side in localStorage lets anyone with device access mint unlimited valid tokens forever. Needs a security design (per-session derived keys, hardware-bound storage, or short-lived server-issued badges) before implementation.
- **Solution:** Store encrypted TOTP secret in browser; generate rotating token in client-side JS; works 100% offline

#### S-08 — Online Excuse Slip Submission Workflow
- **Status:** ❌ Not Built
- **Solution:** Student selects missed session, uploads Medical Certificate photo → Teacher reviews → EXCUSED

### ⚪ Polish

#### S-09 — Excuse Slip Status Tracker
- **Status:** ❌ Not Built
- **Solution:** Dashboard section showing all submitted excuse slips with Pending/Approved/Rejected status

---

## ⚙️ Backend & Technical — 6 Improvements

#### B-01 — Pin All Dependency Versions
- **Status:** 🟡 Partial (`pyotp>=2.9.0`, `qrcode>=7.4`, `Pillow>=10.0` use loose ranges)
- **Solution:** Pin all packages to exact versions in `requirements.txt` for reproducible deployments

#### B-02 — Split `session_views.py` (43KB)
- **Status:** ❌ Not Done
- **Solution:** Extract into `session_lifecycle.py`, `session_scan.py`, `session_export.py`, `session_override.py`

#### B-03 — Run Test Coverage Report
- **Status:** ❌ Not Measured
- **Solution:** Run `pytest --cov=apps --cov-report=html`; target ≥60% coverage on all views and services

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
- **Status:** ❌ Not Built
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
| 🛡️ Admin | 3 | 2 | 13 | **18** |
| 👨‍🏫 Teacher | 1 | 2 | 9 | **12** |
| 🎓 Student | 1 | 2 | 6 | **9** |
| ⚙️ Backend | 4 | 1 | 7 | **12** |
| **TOTAL** | **9** | **7** | **35** | **51** |

---

### 🚀 Recommended Build Order

#### Week 1 — Quick Wins (APIs already exist, just wire front-end)
| ID | Feature | Why Easy |
|---|---|---|
| T-03 | Override drawer in scanner | API already exists |

#### Week 2 — Core UX
| ID | Feature |
|---|---|
| A-03 | In-place student profile editor modal |
| S-03 | Per-subject attendance breakdown cards |
| T-01 | CHED 20% absence radar badges |
| T-02 | Live in-session attendance matrix grid |
| A-18 | System-wide toast notification cleanup |

#### Week 3 — Reports & Analytics
| ID | Feature |
|---|---|
| T-04 | Registrar term-wide Excel export |
| S-04 | CHED early-warning 4-stage sentinel |
| S-05 | Weekly visual timetable grid |
| A-09 | Actor filter for audit log |
| T-05 | Consecutive 3-absence sentinel alert |

#### Week 4+ — Advanced Features
| ID | Feature |
|---|---|
| A-02 | Slide-over dossier drawer |
| A-07 | Curriculum matrix builder |
| A-08 | Term rollover wizard |
| T-07 | Kiosk / projector mode |
| S-07 | Offline PWA QR badge |
| S-08 | Excuse slip upload workflow |
| T-12 | Offline camera buffer (IndexedDB) |

---

*This document is the single source of truth for all KCC ClassStamp improvement items.*
*Update the Status field of each item as it is completed.*
