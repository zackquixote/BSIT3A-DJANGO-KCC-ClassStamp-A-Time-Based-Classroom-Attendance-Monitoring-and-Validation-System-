# 🗄️ KCC ClassStamp — Data Models & Architecture Reference

This document describes all Django models, their relationships, and key business rules.

---

## Entity Relationship Overview

```
Department
  └── Program (many per dept)
        └── Curriculum (program + year + subject)
              └── Subject

AcademicYear
  └── Class (subject + teacher + academic year)
        └── ClassSlot (recurring weekly schedule)
              └── ClassSession (actual daily session)
                    └── AttendanceRecord (per student)
                          └── StampAttempt (audit log)
                    └── AnomalyFlag → ReviewAction

Profile (one per User, 3 roles)
  ├── Admin (no dept/program)
  ├── Teacher → belongs to Department
  └── Student → belongs to Program, has qr_secret, approval_status
        └── Enrollment (student ↔ class)
```

---

## Model Quick Reference

### Organisation Models

| Model | Table | Key Fields |
|---|---|---|
| `Department` | `tblcs_department` | `code`, `name`, `is_active` |
| `Program` | `tblcs_program` | `department`, `code`, `name`, `years_total` |
| `Subject` | `tblcs_subject` | `code`, `name`, `is_active` |
| `Curriculum` | `tblcs_curriculum` | `program`, `year_level`, `subject` |
| `AcademicYear` | `tblcs_academic_year` | `name`, `starts_on`, `ends_on`, `is_active` |

### People Models

| Model | Table | Key Fields |
|---|---|---|
| `Profile` | `tblcs_profile` | `user`, `role`, `department`, `program`, `year_level`, `student_number`, `approval_status`, `qr_secret` |

### Class Models

| Model | Table | Key Fields |
|---|---|---|
| `Class` | `tblcs_class` | `academic_year`, `subject`, `teacher_profile`, `grace_minutes` |
| `ClassSlot` | `tblcs_class_slot` | `class_obj`, `weekday`, `starts_at`, `ends_at`, `room` |
| `Enrollment` | `tblcs_enrollment` | `student_profile`, `class_obj`, `status` |

### Attendance Models

| Model | Table | Key Fields |
|---|---|---|
| `ClassSession` | `tblcs_class_session` | `slot`, `session_date`, `status`, `opened_at`, `closed_at` |
| `AttendanceRecord` | `tblcs_attendance_record` | `session`, `student_profile`, `status`, `method`, `stamped_at`, `late_minutes` |
| `StampAttempt` | `tblcs_stamp_attempt` | `session`, `student_profile`, `outcome`, `method`, `token_age_s` |

### Audit Models

| Model | Table | Key Fields |
|---|---|---|
| `AnomalyFlag` | `tblcs_anomaly_flag` | `attendance_record`, `rule_code`, `risk_score`, `status` |
| `ReviewAction` | `tblcs_review_action` | `anomaly_flag`, `reviewer`, `decision`, `reason` |
| `AuditEvent` | `tblcs_audit_event` | `actor`, `action`, `object_type`, `object_id`, `old_value`, `new_value` |

---

## Profile Role Logic

```python
from apps.core.models import Profile

# Get profile
profile = request.user.classstamp_profile  # OneToOne via related_name

# Check role
profile.role == Profile.ROLE_ADMIN    # 'ADMIN'
profile.role == Profile.ROLE_TEACHER  # 'TEACHER'
profile.role == Profile.ROLE_STUDENT  # 'STUDENT'

# Check approval (Teacher/Student only)
profile.approval_status == Profile.APPROVAL_PENDING   # 'PENDING'
profile.approval_status == Profile.APPROVAL_APPROVED  # 'APPROVED'
profile.approval_status == Profile.APPROVAL_REJECTED  # 'REJECTED'
```

---

## Attendance Status Logic

```python
from apps.core.models import AttendanceRecord

# Determine status based on time:
def determine_status(session, stamped_at):
    slot = session.slot
    scheduled_start = datetime.combine(session.session_date, slot.starts_at)
    grace_end = scheduled_start + timedelta(minutes=slot.class_obj.grace_minutes)

    if stamped_at <= grace_end:
        return AttendanceRecord.STATUS_PRESENT  # On time or within grace
    else:
        return AttendanceRecord.STATUS_LATE     # After grace period
```

---

## ClassSession Lifecycle

```
SCHEDULED → OPEN → CLOSED
                 → CANCELED
```

- **SCHEDULED**: slot exists but teacher hasn't opened yet
- **OPEN**: teacher started session; QR scanning active
- **CLOSED**: teacher or system closed; no more scans accepted
- **CANCELED**: session canceled (holiday, etc.)

---

## StampAttempt Outcomes

| Outcome | Meaning |
|---|---|
| `ACCEPTED` | Valid QR, student marked present/late |
| `INVALID` | QR payload could not be verified (bad signature) |
| `EXPIRED` | TOTP token was too old (> ±30s window) |
| `DUPLICATE` | Student already stamped for this session |
| `INELIGIBLE` | Student not enrolled in this class |
| `SESSION_CLOSED` | Scan attempted after session closed |

---

## Key Queries (Common Patterns)

```python
# Pending accounts (admin validation queue)
Profile.objects.filter(
    role__in=[Profile.ROLE_STUDENT, Profile.ROLE_TEACHER],
    approval_status=Profile.APPROVAL_PENDING
).select_related('user', 'department', 'program')

# Today's sessions for a teacher
from django.utils import timezone
today = timezone.localdate()
ClassSession.objects.filter(
    slot__class_obj__teacher_profile=profile,
    session_date=today,
).select_related('slot', 'slot__class_obj', 'slot__class_obj__subject')

# Student attendance summary per class
from django.db.models import Count
AttendanceRecord.objects.filter(
    student_profile=profile,
    session__slot__class_obj=class_obj
).values('status').annotate(count=Count('id'))

# Check if student has exceeded absence threshold
absent_count = AttendanceRecord.objects.filter(
    student_profile=profile,
    session__slot__class_obj=class_obj,
    status=AttendanceRecord.STATUS_ABSENT
).count()
```

---

## Migrations Workflow

```bash
# After modifying models.py:
python manage.py makemigrations core
python manage.py migrate

# Check current migration state:
python manage.py showmigrations

# Reset and rebuild (development only!):
python manage.py migrate core zero
python manage.py migrate
```

---

## Database Naming Convention

All tables use prefix `tblcs_` (table classstamp):
```
tblcs_department
tblcs_program
tblcs_subject
tblcs_curriculum
tblcs_academic_year
tblcs_profile
tblcs_class
tblcs_class_slot
tblcs_enrollment
tblcs_class_session
tblcs_attendance_record
tblcs_stamp_attempt
tblcs_anomaly_flag
tblcs_review_action
tblcs_audit_event
```
