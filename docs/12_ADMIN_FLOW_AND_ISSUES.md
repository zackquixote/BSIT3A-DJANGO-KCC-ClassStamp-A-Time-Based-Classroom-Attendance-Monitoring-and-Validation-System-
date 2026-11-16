# KCC ClassStamp — Admin Flow Analysis

> Audit date: 2026-11-16
> Scope: Admin portal end-to-end (auth → setup → classes → validation → attendance)
> Method: Code walk (URLs, views, services, middleware, signals) + live MySQL/SQLite checks + test baseline
> Tests at time of audit: `test_rooms.py` 26/26 pass · affected suites 150 pass / 1 pre-existing fail (`test_checklist_identifies_missing_section_setup`, fails on clean `origin/main` too)

---

## 1. Overall Admin Flow

### 1.1 Entry and access control

```
/ (login)
  └─► /dashboard/  (role dispatcher)
        ├─ ADMIN / superuser ──► /admin/dashboard/
        ├─ TEACHER           ──► /teacher/dashboard/
        └─ STUDENT (approved)──► /student/dashboard/
             └─ STUDENT (pending/rejected) ──► /student/approval-waiting/  (ApprovalCheckMiddleware)
```

- Login accepts username, email, student number, or faculty ID.
- Optional TOTP 2FA (`/login/2fa/`) — **opt-in**, not enforced for admins.
- Lockout: 5 failed attempts → IP **and** account lock.
- Every admin route: `@login_required` + `@role_required(ROLE_ADMIN)`.
- `RoleBasedAccessMiddleware` additionally guards URL prefixes `/admin/`, `/teacher/`, `/student/`.
- Superusers inherit ADMIN (not STUDENT).

### 1.2 Foundation setup (one-time / start of term)

Sidebar order under **Academic Structure**:

| Step | Module | What it establishes |
|---|---|---|
| 1 | Departments `/departments/` | CEAS, CMAT, COC, … |
| 2 | Programs & Curriculum `/programs/` | Programs, curriculum versions (draft → approve), major flags |
| 3 | Subject Catalogue `/subjects/` | Subjects, units, `is_lab` flag |
| 4 | Academic Terms `/academic-years/` | Active term, rollover, clone classes |
| 5 | Room Directory `/rooms/` | Canonical rooms/labs, capacity, type, `room_ref` |
| 6 | Faculty Directory `/teachers/` | Teachers, passwords, class assignments |

### 1.3 Classes and schedules

Two paths, same destination:

- **Section Wizard** `/classes/wizard/` — guided: Curriculum → Subject & Teacher → Section → Schedule (room select, clash detection, audited override) → Review.
- **Class Sections** `/classes/` — manual: create/edit section, Manage Slots (day/time/room picker, conflict override), Roster Enlistment, join-code menu.

**Class Setup Checklist** on `/classes/` is the “section is ready for attendance” gate:
Teacher · Schedule · Room (not TBA) · Student roster · Join code.

### 1.4 People onboarding

```
Student self-registers /register/  ──► Profile.PENDING
        │
        ▼
Admin Account Validation /validation/  ──► Approve / Reject / Reopen / Batch
        │
        ▼
Approved student logs in ──► joins class with 12-char join code
        │                      (curriculum + capacity + schedule-overlap checks)
        ▼
QR badge /student/qr/  ──► teacher scanner stamps attendance
```

Teachers do **not** self-register — admins create them in Faculty Directory.
Student Masterlist `/students/`: profile edit, promote-all, QR reset, CSV import/export.

### 1.5 Daily operations

Admin = oversight. Teacher = execution.

```
Teacher opens session ──► students scan QR ──► stamp (Present / Late / Absent)
        │                                        │
        ▼                                        ▼
Admin dashboard: Active Sessions + live stamps (SSE /admin/live-stream/)
        │
Holiday on Academic Calendar ──► that day’s sessions auto-cancel (create only)
```

Admin-side modules around the loop: Academic Calendar, Attendance Reports, Messages, Audit Log, Security (2FA, Attendance Policy, Security Alerts, Database Backup).

### 1.6 Term lifecycle

```
Set active AY ──► clone classes ──► [GAP: enable join codes per class] ──► promote students
      ▲                                                                │
      └──────────────────────── new term starts ◄──────────────────────┘
```

Clone copies classes + slots (including `room_ref` / `slot_type`) but **never** enrollments, sessions, attendance, or join codes. Clones start with `join_code_active=False`.

### 1.7 Mental model

> **Admin = registrar + MIS.** They build the institution, gatekeep who gets in, assemble sections, and then **monitor** attendance. Teachers run time-based stamping; students scan QR. Admin never stamps attendance themselves — they make it possible and then account for it.

---

## 2. What Is Solid

- Layered architecture: views → services → models, with `AuditEvent` on sensitive mutations.
- RBAC decorators + middleware on admin views; document access checks (avatar / COR / excuse attachments).
- Messaging recipient rules (student ↔ enrolled teachers only; admin ↔ anyone).
- Join-code throttle, hashed codes, curriculum / capacity / schedule-overlap validation on join.
- Term-switch blocker when the outgoing term still has an OPEN session (force requires a reason, audited).
- Room CRUD (post-audit): protected delete, code format, duplicate-code rejection, slot-count aligned with delete protection.
- Admin can open/close sessions (`teacher_session_open` allows ADMIN).
- `test_rooms.py` 26/26 passing.

---

## 3. Problems (ranked)

### 🔴 P1 — Will bite in real use

#### P1-1. Term rollover dead-ends: cloned classes have no join codes and no bulk enable

`clone_classes_academic_year` copies classes and slots but forces every clone to
`join_code_active=False` with an empty digest.
`apps/core/services/academic_service.py` (see `clone_classes_academic_year`).

Join codes can only be rotated **one class at a time** in the UI.
`apps/core/views/class_views.py` — `class_join_code_manage` (rotate / revoke).

**Impact.** After cloning N sections for a new term, students cannot join anything until an admin opens every class and rotates. No “enable all cloned classes” action exists.

**Fix shape.** After a successful clone, offer “Generate join codes for all copied classes” (one transaction, one audit event per class, codes shown once). Same for rollover.

---

#### P1-2. Room conflict detection misses legacy/string slots when scheduling from the picker

Manage Slots now submits `room_id` only (`room=''`).
`detect_slot_conflicts` compares FK-to-FK when `proposed_room_id` is set, but for a legacy slot
(`room='LAB-1'`, `room_ref=None`) the string branch compares against an **empty** `proposed_room` → no conflict.

- `apps/core/services/schedule_service.py` — `detect_slot_conflicts`
- `templates/core/admin/classes.html` — Add Meeting Slot (sends `room_id`, not `room`)
- Live MySQL data is already in the legacy shape (`room='TBA'`, `room_ref=None`)

The Section Wizard sends **both** `room` (code) and `room_id`; Manage Slots does not.

**Impact.** Same physical room can be double-booked across old (string) and new (FK) slots.

**Fix shape.** In `class_slot_save`, resolve `room_ref` **before** conflict detection and pass both
`room=canonical_code` and `room_id`. Same for the wizard batch save. Alternatively, inside
`detect_slot_conflicts`, if `proposed_room_id` is set, load the Room and use its code as `proposed_room`.

---

#### P1-3. Class Setup Checklist goes stale after a student joins

`student_join_class` never calls `_invalidate_checklist_cache`.
`apps/core/views/student_portal_views.py` — `student_join_class`
Cache helper: `apps/core/views/class_views.py` — `_class_setup_checklist` / `_invalidate_checklist_cache` (60s TTL).

Admin-side roster enlistment **does** invalidate; the student self-join path does not.
After a successful join, the admin’s “empty roster” warning sticks for up to 60 seconds.

**Related (why the checklist unit test fails on clean `main`).**
`_class_setup_checklist` uses `'test' in sys.argv` to skip the cache. Under pytest, `sys.argv`
is `['…\pytest.exe', 'apps/core/tests/test_classes_page.py', …]` — no element equals `'test'`,
so `is_testing` is **False**, the first GET populates the cache, and the second GET after creating
a slot returns the stale “no Room” result. The project uses pytest, not `manage.py test`.

**Fix shape.**
1. Call `_invalidate_checklist_cache` (and any equivalent) after a successful join / enrollment change in the student portal.
2. Replace the test-detection with `'PYTEST_CURRENT_TEST' in os.environ` (or a settings flag) so pytest actually bypasses the cache.

---

#### P1-4. Holiday auto-cancel only fires on create, not on edit

`apps/core/signals/holiday_signals.py` — `auto_cancel_sessions_on_holiday` runs only when `created=True`.

Gaps:
- Extending a holiday, fixing a wrong date, or changing an event’s category **to** Holiday does nothing.
- No academic-year filter — sessions on those calendar dates in **any** term are cancelled.
- Force-cancels an **OPEN** session that may already have attendance stamps (stamps remain on a CANCELED session).
- No notification to the affected teacher or enrolled students.
- Audit actor is `None`.

**Fix shape.** Run the cancel sweep on create **and** on date/category/status change; filter to the
active (or event’s) academic year; skip sessions that already have attendance or mark them separately;
notify the class teacher; keep “delete does not restore” as documented.

---

#### P1-5. Account lockout = account DoS

Failed logins lock both IP **and account** (`login_lock:account:{id}`).
`apps/core/views/helpers/auth_helpers.py` — `_set_lock_state` / `_get_lock_state`.

Student numbers are the login identifier and are semi-public in a school. Anyone who knows a
student number can lock that student out with 5 wrong passwords from any IP.

**Fix shape.** Prefer IP+identifier **combined** lock (or exponential backoff per IP, with account
lock only behind 2FA / admin action). At minimum, do not count a wrong-password attempt against
the account when the request already looks like a bot (or require a captcha after 2 IP failures).

---

### 🟠 P2 — Flow inconsistencies

#### P2-1. RBAC is two different systems

`RoleBasedAccessMiddleware` only guards `/admin/`, `/teacher/`, `/student/`.
`apps/core/middleware/rbac.py`.

Most admin pages live **outside** those prefixes:
`/rooms/`, `/classes/`, `/validation/`, `/students/`, `/teachers/`, `/subjects/`, `/departments/`, `/programs/`, `/academic-years/`.

They are protected only by `@role_required` on the view. One missing decorator = student/teacher access.
`room_options_json` was exactly that bug (login-only) until it was tightened to ADMIN.

Also inconsistent denial UX for the same “not allowed” event:
- Teacher on `/admin/calendar/` → **403** (middleware)
- Teacher on `/rooms/` → **302 to dashboard** (decorator)

**Fix shape.** Either move admin pages under `/admin/`, or add a second middleware map for the
known admin prefixes, or a view-audit test that walks `urls.py` and asserts every non-auth,
non-student, non-teacher view has `@role_required`. Keep 403 for cross-role, 302 for same-role
dashboard fallback — but pick one and document it.

---

#### P2-2. Manage Slots cannot set `slot_type` and ignores room capacity

Section Wizard: auto-sets `LABORATORY` when the subject `is_lab`, warns when section capacity > room capacity.
`static/js/classes/section_wizard.js`

Manage Slots (`classes.html` Add Meeting Slot): no `slot_type` field (always `LECTURE`), no capacity warning.
A 50-cap section can be parked in a 40-seat lab with no warning; a lab subject scheduled via Manage Slots
is typed as LECTURE even in LAB-1.

**Fix shape.** Mirror the wizard: `slot_type` select (preselect from subject `is_lab`), room-capacity
badge/warning, optional “lab subject in lecture room” warning.

---

#### P2-3. Pending students: two gates that do not meet

- `login_view` **blocks PENDING from signing in at all** (`apps/core/views/auth_views.py`).
- `ApprovalCheckMiddleware` + `/student/approval-waiting/` only fire for users who are **already logged in** when status flips.

After self-registration a student never sees the waiting page — just a login-screen warning.
`dashboard_redirect`’s unapproved-student branch (`home.html`) is dead code: the middleware
intercepts `/dashboard/` first.

**Fix shape.** After registration, either (a) render the waiting page content on the login warning,
or (b) issue a limited session that can only see `/student/approval-waiting/`. Remove the dead
branch in `dashboard_redirect` or make it match the middleware.

---

#### P2-4. Approval middleware can flood the audit log

Every denied request writes an `AuditEvent` (`apps/core/middleware/approval.py`).
`static/js/core/app_desktop_alerts.js` polls `/api/notifications/unread/` every 60s and is loaded
from `theme/base.html` — which the waiting page extends.

A pending student who enabled desktop alerts generates a 403 + audit row every minute until logout.

**Fix shape.** Exempt `/api/notifications/unread/` (and other harmless polls) from the approval
audit, or do not load the desktop-alerts poller unless the profile is an approved student / staff.
Throttle identical denial audits (same user + path within N minutes).

---

#### P2-5. 2FA is opt-in for admins

`two_factor_required` is true only if `profile.totp_enabled` and a secret exists.
`apps/core/services/two_factor_service.py`

`verify_admin` ships with 2FA off. If `docs/02_SECURITY.md` says privileged accounts must use 2FA,
the login flow does not enforce it.

**Fix shape.** Policy flag: “ADMIN accounts with `totp_enabled=False` get a setup wizard on first
login” or at least a persistent admin-console warning.

---

### 🟡 P3 — Smaller but real

| ID | Issue | Where |
|---|---|---|
| P3-1 | Context processor runs 4–5 queries on **every** admin page (unread notifications, unread messages, pending-approval count, open anomalies) with no cache | `apps/core/context_processors.py` |
| P3-2 | Messages mark-as-read is N+1 (one UPDATE per message in a loop) | `apps/core/views/messaging_views.py` — `message_thread` |
| P3-3 | Holiday cancel writes `actor=None` and does not notify the affected teacher | `apps/core/signals/holiday_signals.py` |
| P3-4 | `room_options_json` is still unused by the frontend (wizard and slots modal are server-rendered). Dead-ish endpoint — keep as API or remove | `apps/core/views/room_views.py` |
| P3-5 | `class_wizard_save` and `_class_wizard_save_batch` duplicate slot-creation / room_ref resolution | `apps/core/views/class_views.py` |
| P3-6 | Checklist “Room” check looks only at the `room` string (`TBA` / `ASSIGNED ROOM`). Safe today because `ClassSlot.save()` syncs the string from `room_ref`; fragile if anyone writes `room_ref` without the string | `apps/core/views/class_views.py` — `_class_setup_checklist` |
| P3-7 | `class_slot_save` does not block adding slots to inactive classes or closed academic years | `apps/core/views/class_views.py` |
| P3-8 | Stat cards on Room Directory count **all** rooms for type totals and **active** for “Active & Ready” — consistent now, but easy to re-break if someone “optimizes” the aggregate | `apps/core/views/room_views.py` — `room_list` |
| P3-9 | Pre-existing test failure (not introduced by the Room work): `test_checklist_identifies_missing_section_setup` fails on clean `origin/main` because of P1-3’s cache detection | `apps/core/tests/test_classes_page.py` |

---

## 4. Recommended fix order

Do these in order — each one unblocks the next stage of the term-start flow:

1. **P1-1 Bulk join codes after clone/rollover** — without this, the term-start ceremony is N manual clicks.
2. **P1-2 Conflict detection for `room_id`-only proposals** — without this, the new room picker silently under-detects clashes against legacy `TBA` / string slots.
3. **P1-3 Checklist invalidate on join + pytest cache flag** — fixes the failing test and the 60s stale admin UI.
4. **P1-4 Holiday cancel on update + notify** — otherwise the calendar is a one-shot tool.
5. **P1-5 Lockout DoS** — policy decision (combined lock vs captcha vs admin-unlock).
6. **P2-1 RBAC prefix audit test** — prevent the next missing-decorator hole.
7. **P2-2 Manage Slots parity with the wizard** (`slot_type` + capacity).
8. Everything in P3 as cleanup.

---

## 5. File index (what was inspected)

| Area | File |
|---|---|
| Role dispatcher / dashboards | `apps/core/views/dashboard_views.py` |
| RBAC middleware / decorators | `apps/core/middleware/rbac.py`, `apps/core/decorators/rbac.py` |
| Approval gate | `apps/core/middleware/approval.py` |
| Login / 2FA / lockout | `apps/core/views/auth_views.py`, `apps/core/views/helpers/auth_helpers.py`, `apps/core/services/two_factor_service.py` |
| Classes / slots / wizard / checklist | `apps/core/views/class_views.py`, `templates/core/admin/classes.html`, `static/js/classes/slots_modal.js`, `static/js/classes/section_wizard.js` |
| Rooms | `apps/core/views/room_views.py`, `apps/core/models/room.py`, `apps/core/services/academic_service.py` (room functions), `templates/core/admin/rooms.html`, `static/js/rooms/room_crud.js` |
| Conflict detection | `apps/core/services/schedule_service.py` |
| Student join / QR | `apps/core/views/student_portal_views.py` |
| Validation | `apps/core/urls.py` (`/validation/…`) |
| Messages | `apps/core/views/messaging_views.py`, `apps/core/services/message_service.py` |
| Calendar / holiday | `apps/core/views/calendar_views.py`, `apps/core/signals/holiday_signals.py` |
| Documents | `apps/core/views/document_views.py` |
| Context processor | `apps/core/context_processors.py` |
| Tests | `apps/core/tests/test_rooms.py`, `apps/core/tests/test_classes_page.py`, `apps/core/tests/test_week7.py` |

---

## 6. Environment notes (audit-time)

- Dev server: MySQL `bsitcrud` (fully migrated through `0035`).
- SQLite `db.sqlite3`: migrated through `0035` during this audit (was two migrations behind).
- Live data snapshot: 14 rooms, 2 slots — both `room='TBA'`, `room_ref=None`; one live session in room `TBA`.
- Nothing in this document is a code change; it is an analysis record.


---

## 7. Fix log — 2026-11-16 (same-day follow-up)

Status after the P1–P3 pass. Nothing in §1–§6 was rewritten; this section records what changed.

### P1-1 Bulk join codes after clone — already implemented; test repaired
Service, view, UI, and tests already existed (`enable_join_codes_for_classes`,
`/academic-years/enable-join-codes/`, clone checkbox + Generate button).
`test_service_rerun_skips_already_active` looked clones up by `class_code`,
which collides with the source class. It now looks up by cloned PK.

### P1-2 Room conflict detection for `room_id`-only proposals
`detect_slot_conflicts` now resolves `room_id` to the Room's canonical code
**before** comparing, so a Manage Slots picker submission clashes with legacy
string slots (`room='TBA'`, `room_ref=None`). `class_slot_save` also resolves
`room_ref` before conflict detection. Regression test:
`test_detect_slot_conflicts_room_id_against_legacy_string_slot`.

### P1-3 Checklist cache: pytest flag + invalidate on student join
`_class_setup_checklist` now uses `'PYTEST_CURRENT_TEST' in os.environ`
instead of `'test' in sys.argv`. `student_join_class` calls
`_invalidate_checklist_cache` after a successful join. The pre-existing
`test_checklist_identifies_missing_section_setup` failure is gone.

### P1-4 Holiday auto-cancel on update, scoped, stamped-safe, notified
`auto_cancel_sessions_on_holiday` runs on every save of an active HOLIDAY
(create, date change, category flip). Sweep is scoped to the event's (or the
active) academic year. Sessions that already have attendance stamps are left
untouched. The class teacher is notified once per teacher. Audit actor is
`updated_by` / `created_by`, not `None`.

### P1-5 Lockout is combined IP+identifier, not a global account lock
Five wrong passwords lock that IP and that (IP, identifier) pair. They no
longer write `login_lock:account:{id}`. A clean network with the right
password still signs in — knowing a semi-public student number cannot take
the account offline from every campus lab. Legacy account-lock keys still
expire naturally. `test_account_lock_holds_across_client_addresses` was
rewritten as `test_clean_ip_with_the_right_password_is_not_dossed`.

### P2-1 RBAC URL-walk test
`role_required` now stamps `wrapper.allowed_roles`.
`apps/core/tests/test_rbac_audit.py` walks every URL pattern and refuses an
app view that is neither public, nor a documented shared-authenticated page,
nor `@role_required`-guarded. It also asserts the known admin directories
(`/rooms`, `/validation`, `/departments`, `/programs`, `/subjects`,
`/academic-years`, `/students`, `/teachers`) require ADMIN. Denial UX stays
as documented: portal prefixes 403 via middleware; other admin pages 302 via
decorator.

### P2-2 Manage Slots parity with the wizard
Add Meeting Slot now has a `slot_type` select (preselected from the
subject's `is_lab`), a room-capacity warning, and a lab-subject-in-lecture-
room warning. `class_slot_save` already accepted `slot_type`; covered by
`test_class_slot_save_accepts_slot_type`.

### P3 cleanup that shipped
- **P3-1** Context processor counters are cached (20 s per-user unread, 30 s
  admin pending/anomaly). Bypassed under pytest.
- **P3-2** Thread open marks unread incoming messages with one UPDATE and one
  `MESSAGE_READ` audit row (`mark_thread_as_read`).
- **P3-3** Covered by P1-4 (actor + teacher notification).
- **P3-6** Checklist "Room" check honors `room_ref` even if the legacy string
  is stale.
- **P3-7** `class_slot_save` refuses inactive classes and closed academic years.
- **P3-9** Covered by P1-3.

### P3 left as-is (not bugs)
- **P3-4** `room_options_json` kept as a JSON API.
- **P3-5** Wizard save / batch save still duplicate slot creation — refactor,
  not a defect.
- **P3-8** Room stat-card totals were already consistent.
