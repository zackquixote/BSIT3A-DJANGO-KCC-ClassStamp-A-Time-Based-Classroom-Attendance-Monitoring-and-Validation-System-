# 🎓 KCC ClassStamp — Full Development Plan
**A Time-Based Classroom Attendance Monitoring and Validation System**

---

## 🗺️ System Overview

KCC ClassStamp is a **3-role, QR-powered attendance system** built on Django.
After login, every user lands on a role-specific dashboard — no shared UI confusion.

| Role | Core Purpose |
|------|-------------|
| **KCC Admin** | Validate accounts, manage org structure, oversee everything |
| **Teacher** | Open sessions, scan student QR codes, track class attendance |
| **Student** | View personal QR code, monitor own absences & attendance logs |

---

## 👤 Role Definitions & Permissions

### 🔴 KCC Admin
- Full access to all system data
- Validate/approve/reject Student & Teacher account registrations
- Assign roles, departments, programs, and subjects to accounts
- Create, edit, deactivate Teacher profiles
- Manage Departments, Programs, Subjects, Academic Years
- View all attendance records system-wide
- Access anomaly/fraud flags and review actions
- Export attendance reports

### 🟡 Teacher
- Role-specific dashboard showing their assigned classes
- Open / close class sessions
- **Scan student QR codes** to mark attendance (QR Scanner page)
- Manually override attendance (PRESENT → LATE → ABSENT → EXCUSED)
- View attendance log per session and per student in their class
- See anomaly flags for their own sessions

### 🟢 Student
- Role-specific dashboard showing enrolled subjects
- **Personal QR Code page** — displays their rotating TOTP-based QR
- View personal attendance log (per subject: present, late, absent counts)
- See absence warnings (e.g. "You are at 3 absences — max is 5")
- Cannot modify any records

---

## 🏗️ Architecture: What Already Exists vs. What to Build

### ✅ Already Built (in `apps/core/models.py`)

| Model | Status |
|---|---|
| `Department` | ✅ Complete |
| `Program` | ✅ Complete |
| `Subject` | ✅ Complete |
| `Curriculum` | ✅ Complete |
| `AcademicYear` | ✅ Complete |
| `Profile` (role + QR secret) | ✅ Complete |
| `Class` + `ClassSlot` | ✅ Complete |
| `Enrollment` | ✅ Complete |
| `ClassSession` | ✅ Complete |
| `AttendanceRecord` | ✅ Complete |
| `StampAttempt` | ✅ Complete |
| `AnomalyFlag` + `ReviewAction` | ✅ Complete |
| `AuditEvent` | ✅ Complete |

### ⚠️ Existing Auth/Views (partially built)
- `login_view`, `logout_view`, `register_view` — basic, no role routing yet
- `user_list_page` / AJAX CRUD — superuser only, not tied to `Profile`

---

## 📋 Phase-by-Phase Build Plan

---

### 🔵 Phase 1 — Role-Based Routing & Dashboards

**Goal:** After login, redirect each user to the correct role dashboard.

#### Tasks:
1. **Registration Flow Update**
   - Add role selection (`Student` or `Teacher`) on register
   - Auto-create `Profile` on user creation
   - Students: enter student number, select program & year level
   - Teachers: select department
   - Set `approval_status = PENDING` for all new registrations

2. **Post-Login Redirect**
   - `login_view` → check `profile.role` → redirect to role dashboard:
     - `ADMIN` → `/admin-panel/`
     - `TEACHER` → `/teacher/`
     - `STUDENT` → `/student/`

3. **Dashboard Pages** (3 separate templates + views)

   **Admin Dashboard**
   - Summary cards: Pending accounts, Active teachers, Enrolled students, Open sessions
   - Quick links: Account validation queue, Manage departments, Manage programs

   **Teacher Dashboard**
   - Today's class schedule
   - Quick "Open Session" button per slot
   - Recent attendance activity

   **Student Dashboard**
   - Enrolled subjects with attendance summary (Present / Late / Absent)
   - Absence alert if nearing max
   - Link to "My QR Code"

---

### 🔵 Phase 2 — Admin Panel

**Goal:** A beautiful, role-guarded admin section (NOT Django admin).

#### 2A — Account Validation Queue
- List all PENDING profiles (Student & Teacher)
- Approve → set `approval_status = APPROVED`, generate `qr_secret`
- Reject → set `approval_status = REJECTED`, optional note

#### 2B — Department Management
- CRUD: Create / Edit / Deactivate departments

#### 2C — Program Management
- CRUD: Assign to department, set year levels count

#### 2D — Subject Management
- CRUD: Assign subjects to programs via Curriculum

#### 2E — Teacher Management
- Admin can create a Teacher account directly
- Assign to department, set password

#### 2F — Academic Year Management
- Create academic years, mark one as active

#### 2G — Class & Schedule Management
- Create classes (link subject + teacher + academic year)
- Add weekly time slots, enroll students

---

### 🔵 Phase 3 — Student QR Code Feature

**Goal:** Every student sees their personal rotating QR on their dashboard.

#### Tasks:
1. On profile approval: generate `qr_secret` (32-byte random)
2. QR Page (`/student/my-qr/`) encodes: `classstamp:<student_number>:<token>`
3. Token rotates every 30 seconds with countdown — auto-refresh via JS
4. Validation: verify TOTP against `qr_secret` with ±1 bucket tolerance

---

### 🔵 Phase 4 — Teacher QR Scanner

**Goal:** Teacher opens a session and scans student QRs to mark attendance.

#### Tasks:
1. Teacher opens session → `ClassSession.status = OPEN`
2. Scanner page (`/teacher/scan/<session_id>/`) uses `html5-qrcode` JS library
3. Backend validates QR + checks enrollment → returns status toast
4. Attendance list sidebar: green = present, yellow = late, red = absent
5. Manual override with required reason

---

### 🔵 Phase 5 — Student Attendance Log

**Goal:** Students can view their full attendance history.

#### Tasks:
1. Log page (`/student/attendance/`) — filter by subject, date, status
2. Summary header: Total Present / Late / Absent
3. Absence warning banner with color progression: green → yellow → orange → red

---

### 🔵 Phase 6 — Notifications & Polish

1. Email notifications: account approved/rejected, absence warning
2. Anomaly Flag UI: dismiss/confirm/excuse suspicious stamps
3. Reports & Export: CSV download, print-friendly attendance sheets

---

## 🎨 UI/UX Design System

### Theme: Dark Glassmorphism + KCC Brand

| Token | Value |
|---|---|
| Background | `#0f172a` (deep navy) |
| Card | `rgba(255,255,255,0.05)` + `backdrop-filter: blur(12px)` |
| Accent Gold | `#f59e0b` |
| Accent Blue | `#3b82f6` |
| Font | Inter (Google Fonts) |
| Border radius | `12px` |
| Transition | `all 0.3s ease` |

---

## 📁 URL Structure

```
/login/                    → Login page
/register/                 → Register (choose role)
/logout/

/admin-panel/              → Admin dashboard
/admin-panel/accounts/     → Account validation queue
/admin-panel/departments/
/admin-panel/programs/
/admin-panel/subjects/
/admin-panel/teachers/
/admin-panel/classes/
/admin-panel/academic-years/

/teacher/                  → Teacher dashboard
/teacher/scan/<id>/        → QR scanner
/teacher/attendance/<id>/  → Session attendance list

/student/                  → Student dashboard
/student/my-qr/            → Personal QR code
/student/attendance/       → Attendance log
```

---

## 📦 Required Packages

```
pyotp          # TOTP rotating QR tokens
qrcode[pil]   # QR image generation
Pillow         # Image handling
```

---

## 🚀 Build Order

```
Phase 1 → Role routing + 3 dashboards         (Day 1-2)
Phase 2 → Admin panel (accounts + org mgmt)   (Day 3-5)
Phase 3 → Student QR code display             (Day 6)
Phase 4 → Teacher QR scanner + session mgmt   (Day 7-8)
Phase 5 → Student attendance log              (Day 9)
Phase 6 → Polish, notifications, export       (Day 10+)
```

> **Start with Phase 1** — role-based routing is the foundation everything depends on.
