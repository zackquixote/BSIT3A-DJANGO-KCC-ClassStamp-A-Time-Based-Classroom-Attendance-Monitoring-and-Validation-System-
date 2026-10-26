# 10 — Demo Accounts by Role

Seeded login accounts for testing each RBAC persona in KCC ClassStamp.
All three are created/refreshed by the idempotent seeder:

```bash
python manage.py seed_all_roles
```

> ⚠️ Running the seeder **resets these three passwords** to the values below and
> also ensures the canonical departments, programs, academic year, subject, and
> sample class `BSIT-3A-IT311` exist. These are local-development credentials —
> never use them in production.

| Role | Username | Email (also valid login) | Password | Lands on |
|---|---|---|---|---|
| 🛡️ Admin | `admin` | `admin@classstamp.local` | `admin12345` | `/admin/dashboard/` |
| 👨‍🏫 Teacher | `teacher` | `teacher@kcc.edu.ph` | `teacher12345` | `/teacher/dashboard/` |
| 🎓 Student | `student` | `student@kcc.edu.ph` | `student12345` | `/student/dashboard/` |

## Login identifiers

The login form accepts three kinds of identifiers for any account:

1. Username (e.g. `admin`)
2. Email address (e.g. `teacher@kcc.edu.ph`)
3. Student ID number (students only, e.g. `2024-0001`)

The root URL `/` serves the login page; `/dashboard/` is the role-aware
dispatcher that redirects an authenticated user to their own dashboard.

## Profile details

| Account | Profile shape (enforced by `chk_cs_profile_shape`) |
|---|---|
| `admin` | Role ADMIN — no department, program, year, or student number |
| `teacher` | Role TEACHER — Department **CMAT**, approval/student fields NULL |
| `student` | Role STUDENT — Program **BSIT**, Year 3, Student No `2024-0001`, status **APPROVED**, 64-char TOTP QR secret |

## Notes

- Teacher + student accounts skip the registration/approval queue (student is
  pre-approved) so you can jump straight into scanning and dashboards.
- Other developer-created accounts (e.g. `glenn`, `testteacher99`,
  `wowowin`) exist in the local DB but are not managed by the seeder and have
  no documented passwords.
- Re-run the seeder any time you need to restore the canonical trio or their
  passwords.
