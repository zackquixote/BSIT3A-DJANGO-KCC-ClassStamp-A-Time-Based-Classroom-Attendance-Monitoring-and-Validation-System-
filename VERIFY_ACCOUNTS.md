# ClassStamp — Role-Based Verification Accounts

Dedicated test accounts for browser verification (plan task **6.3**) and manual QA.
Created in **both** the SQLite dev database (`db.sqlite3`) and the XAMPP MySQL
database (`bsitcrud`).

- **Login URL:** <http://127.0.0.1:8000/>
- **Password for every account:** `Verify#2026x`
- **Start the dev server (SQLite):**
  `USE_SQLITE=True python pmanage.py runserver 127.0.0.1:8000 --noreload`
- **Recreate the accounts if needed:**
  `python _create_role_accounts.py` (add `USE_SQLITE=True` for the SQLite DB)

> Do not use these accounts in production. They exist only for local
> verification and are not listed anywhere in the student/teacher directories
> as real people.

---

## Account list

| Role | Username | Display name | State / purpose |
| --- | --- | --- | --- |
| ADMIN | `verify_admin` | Vera Admin | Superuser + ADMIN profile. Full admin console. 2FA disabled. |
| TEACHER | `verify_teacher` | Theo Teacher | CMAT faculty. Owns the verification classes (SQLite). |
| STUDENT | `verify_student` | Sofia Student | APPROVED · BSIT Y3. Main student; enrolled in `VER1`; has a pending excuse slip. |
| STUDENT | `verify_student2` | Sam Second | APPROVED · BSIT Y3. Enrolled in `VER1` and `VERF`; only 2 attendance records (prediction “insufficient data”). |
| STUDENT | `verify_student3` | Tara Third | APPROVED · BSIT Y3. **No enrollments** — use for join-code acceptance / capacity tests. |
| STUDENT | `verify_low` | Liam Low | APPROVED · BSIT Y3. Enrolled in `VER1`; 3 absences in 6 sessions → prediction below the 80% pass line (at-risk highlight). |
| STUDENT | `verify_nocv` | Noa Curriculum | APPROVED · BSIT Y3 · **no curriculum version** — join/roster is rejected with the “contact administration” message (Req 1). |
| STUDENT | `verify_bsa` | Bea Accounting | APPROVED · **BSA** Y3 — cross-program enrollment into a BSIT major class is rejected unless an admin overrides. |
| STUDENT | `verify_pending` | Pia Pending | **PENDING** approval — student portal redirects to `/student/approval-waiting/` (Req 6). |

---

## Role walkthrough

### ADMIN — `verify_admin`
1. Sign in → Admin Dashboard (sidebar: Academic Terms, Departments, Programs &
   Curriculum, Subject Catalogue, Class Sections, Section Wizard, Faculty
   Directory, Account Validation, Student Masterlist, User Accounts, Security).
2. Academic Calendar → create a Holiday event → scheduled sessions that day are
   auto-cancelled (Req 3).
3. Academic Terms → Clone Classes (source term → target term) → summary shows
   copied class/slot counts; clones have join codes disabled (Req 12).
4. Class Sections → add a slot that clashes → hard-blocked; admin may confirm
   the override (audited) (Req 11 + 18).
5. Class roster → enroll `verify_bsa` (cross-program) and `verify_student3`
   into a full class → rejected; retry with the explicit override checkboxes
   (audited) (Req 1 + 2).
6. Messages → inbox/compose; admins may message anyone (Req 8).

### TEACHER — `verify_teacher`
1. Sign in → Teacher dashboard; sidebar shows teacher modules only.
2. `VER1` attendance matrix → Predicted column: `verify_low` highlighted below
   threshold, `verify_student2` shows “— data” (insufficient sessions) (Req 15).
3. Matrix export → CSV and PDF (`format=pdf`) downloads (Req 14).
4. Class join-code panel → rotate → copy the 12-character code (Req 1 flow).
5. Excuse Slips → checkboxes + Approve selected → bulk approval; a slip from
   another teacher’s class fails independently (partial-failure summary) (Req 13).
6. Open session on `VER1` for today → re-opens a holiday-cancelled session
   (`REOPEN_CLASS_SESSION` audit).
7. Messages → student ↔ teacher only when an ACTIVE enrollment links them
   (`verify_student` works; an unrelated student is not offered) (Req 8).

### STUDENT — `verify_student`
1. Sign in → Student portal; sidebar shows student modules only.
2. Join class with the `VER1` code (use `verify_student3` for a clean join) →
   auto-activated enrollment (Req 1 acceptance path).
3. `verify_nocv` + same code → rejected: no curriculum version.
4. Full class code (`VERF`, capacity 1) → “no remaining seats”.
5. Messages → thread with `verify_teacher`; unread badge clears on read.
6. Notifications page → push toggle, service worker, in-app notifications.
7. `verify_pending` → any student route redirects to the approval-waiting page.

### Negative / RBAC checks
| Actor | Route | Expected |
| --- | --- | --- |
| Anonymous | `/dashboard/` | Redirect to login (`/`) |
| `verify_student` | `/teacher/...` | HTTP 403 (RoleBasedAccessMiddleware) |
| `verify_teacher` | `/admin/calendar/` | HTTP 403 |
| `verify_pending` | `/student/dashboard/` | Redirect to `/student/approval-waiting/` |

---

## Seeded verification data (SQLite `db.sqlite3` only)

Created by `_verify_seed.py` against the active term **2026-2027 1st Sem**:

| Class | Section | Subject | Teacher | Slot | Notes |
| --- | --- | --- | --- | --- | --- |
| `VER1` | BSIT-3A | IT311 | `verify_teacher` | Tue 09:00–10:30 · VRF-LAB | 6 closed sessions + today’s session; capacity 30 |
| `VER2` | BSIT-3A | GEE1 | `jose.reyes` | Wed 09:00–10:30 · R-202 | Other-teacher class (bulk-excuse permission failure) |
| `VER3` | BSIT-3A | GEE1 | `verify_teacher` | Wed 11:00–12:30 · R-203 | Empty slot target for conflict tests |
| `VERF` | BSIT-3B | IT311 | `verify_teacher` | Thu 13:00–14:30 · R-204 | **Capacity 1**, already filled → join/roster rejection |

- Attendance: `verify_low` = P,P,A,A,P,A (50% → below-threshold prediction);
  `verify_student2` = 2 records (insufficient data); `verify_student` = 1 ABSENT
  + pending excuse slip on the last closed session.
- Excuse slips (PENDING): slip on `VER1` (approvable by `verify_teacher`) and
  slip on `VER2` (not approvable by `verify_teacher` → bulk partial failure).

On MySQL the same accounts exist, but the class/session fixture is **not**
seeded (the MySQL dev database holds the project’s working data). Run
`_verify_seed.py` against MySQL only if you intentionally want the `VER*`
classes created there too.

---

## Security notes

- Passwords are stored as Django PBKDF2 hashes; the plaintext above is only
  for local verification.
- `verify_admin` is a superuser — never enable it outside development.
- Account creation goes through `set_password()` and therefore bypasses the
  composition/password-history validators (Req 20) — expected for seeding.
