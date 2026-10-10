# 🎓 KCC ClassStamp
### A Time-Based Classroom Attendance Monitoring and Validation System

A **Django-powered**, QR-code-based attendance system for KCC with 3 role-based portals: Admin, Teacher, and Student.

## 👥 Group Members
- **RONELO DACILLO**
- **LOURD IAN AKOL**
- **YASTER JOSHUA DADO**

*10/7/2026 — 100 Points*

---

## 📚 Documentation

| Document | Description |
|---|---|
| [📋 Dev Plan](docs/01_DEV_PLAN.md) | Full phase-by-phase build plan |
| [🔐 Security Guidelines](docs/02_SECURITY.md) | Auth, RBAC, CSRF, QR security rules |
| [🎨 UI Design System](docs/03_UI_DESIGN_SYSTEM.md) | Colors, typography, components, CSS |
| [🗄️ Models Reference](docs/04_MODELS_REFERENCE.md) | All models, queries, relationships |

---

## 👤 Role Overview

| Role | Access | Key Features |
|---|---|---|
| **KCC Admin** | `/admin-panel/` | Validate accounts, manage departments/programs/subjects/teachers |
| **Teacher** | `/teacher/` | Open class sessions, scan student QRs, manage attendance |
| **Student** | `/student/` | View personal rotating QR code, monitor attendance log |

---

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt
pip install pyotp "qrcode[pil]" Pillow

# 2. Run migrations
python manage.py migrate

# 3. Create a superuser (becomes KCC Admin)
python manage.py createsuperuser

# 4. Run development server
python manage.py runserver
```

---

## 🏗️ Project Structure

```
KCC-ClassStamp/
├── apps/
│   ├── core/          # Models, decorators, QR logic
│   ├── users/         # Auth, registration, profile management
│   ├── admin_panel/   # Admin dashboard & management
│   ├── teacher/       # Teacher dashboard & QR scanner
│   └── student/       # Student dashboard & attendance log
├── templates/         # Django HTML templates
├── static/            # CSS, JS, images
└── docs/              # Project documentation
```

---

## 📦 Tech Stack

- **Backend**: Django (Python)
- **Database**: MySQL (via XAMPP)
- **QR Generation**: `qrcode[pil]` + `Pillow`
- **QR Tokens**: `pyotp` (TOTP — rotates every 30s)
- **QR Scanner**: `html5-qrcode` (JavaScript, camera-based)
- **Frontend**: Pure Vanilla CSS + JavaScript (Dark Glassmorphism — No CSS Frameworks)
- **Font**: Inter (Google Fonts)
