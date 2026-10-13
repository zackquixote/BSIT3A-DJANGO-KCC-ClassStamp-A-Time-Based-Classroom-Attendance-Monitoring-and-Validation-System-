# KCC ClassStamp — Professional System Architecture Blueprint

> **System**: KCC-ClassStamp (A Time-Based Classroom Attendance Monitoring and Validation System)  
> **Pattern**: Domain-Driven Layered Service Architecture (Clean Django)  
> **Standard**: Industry Enterprise Standard (Separation of Concerns / Single Responsibility Principle)

---

## 1. Architectural Philosophy

The **KCC ClassStamp** backend transitions from standard Django monolith conventions (fat models, monolithic 1000+ line views) into a **Strict 5-Tier Layered Service Architecture**. This ensures:

1. **Thin Views (HTTP Handlers)**: Views only parse HTTP requests, invoke services, and return responses or redirects.
2. **Dedicated Form Validation**: Input sanitization, password policy enforcement, and constraint checks are encapsulated in Django Forms.
3. **Encapsulated Business Logic (Services)**: Multi-step database workflows, atomic transactions, QR secret rotation, and CSV batch processing live inside pure Python service functions.
4. **Isolated Domain Models**: Models are split across bounded domains (`academic`, `attendance`, `profile`, `classroom`, `audit`) instead of a single god-file.
5. **Decoupled Data Transformation (Serializers)**: Model-to-Dictionary transformations for AJAX tables, modals, and export formats are decoupled from template rendering.

---

## 2. Full Directory Layout

```text
KCC-ClassStamp-A-Time-Based-Classroom-Attendance-Monitoring-and-Validation-System/
│
├── mysite/                               # ⚙️ SYSTEM CONFIGURATION
│   ├── __init__.py
│   ├── asgi.py                           # ASGI entrypoint for async capabilities
│   ├── wsgi.py                           # Production WSGI application gateway
│   ├── settings.py                       # Modular settings with environment bindings (.env)
│   └── urls.py                           # Master URL dispatch table
│
├── apps/                                 # 📦 DOMAIN APPLICATIONS NAMESPACE
│   │
│   └── core/                             # Primary Institutional Management Subsystem
│       ├── __init__.py
│       ├── apps.py                       # AppConfig declaration & startup hooks
│       ├── urls.py                       # Institutional subsystem route bindings
│       │
│       ├── models/                       # 1️⃣ DATA & SCHEMA LAYER (Persistent Entities)
│       │   ├── __init__.py               # Flat registry re-exporting all 15 models
│       │   ├── academic.py               # Department, Program, Subject, Curriculum, AcademicYear
│       │   ├── profile.py                # Profile (Student/Teacher/Admin), QR seed, approval states
│       │   ├── classroom.py              # Class, ClassSlot, Enrollment (rosters)
│       │   ├── attendance.py             # ClassSession, AttendanceRecord, StampAttempt
│       │   └── audit.py                  # AnomalyFlag, ReviewAction, AuditEvent
│       │
│       ├── forms/                        # 2️⃣ VALIDATION & SANITIZATION LAYER
│       │   ├── __init__.py               # Flat form class registry
│       │   ├── registration_form.py      # Student self-registration & credential validator
│       │   └── academic_forms.py         # DepartmentForm & ProgramForm (Admin ModelForms)
│       │
│       ├── services/                     # 3️⃣ BUSINESS LOGIC LAYER (Service Engine)
│       │   ├── __init__.py               # Public Service API
│       │   ├── auth_service.py           # Student account provisioning & credential pipeline
│       │   ├── approval_service.py       # Registrar approval workflow & QR rotation
│       │   ├── academic_service.py       # Department/Program CRUD & audit emissions
│       │   └── student_service.py        # Masterlist filtering & atomic bulk CSV ingestion
│       │
│       ├── views/                        # 4️⃣ HTTP CONTROLLER LAYER (Thin Controllers)
│       │   ├── __init__.py               # Re-exports all endpoint handlers
│       │   ├── auth_views.py             # Login, logout, registration controller
│       │   ├── dashboard_views.py        # Role-based dashboard dispatchers
│       │   ├── department_views.py       # Academic department management controllers
│       │   ├── program_views.py          # Degree program management controllers
│       │   ├── student_views.py          # Masterlist directory & CSV import controllers
│       │   ├── validation_views.py       # Registrar dossier review & validation queue
│       │   └── helpers/                  # Sub-controller computational helpers
│       │       ├── __init__.py           # Re-exports helper utilities
│       │       ├── auth_helpers.py       # Session throttling, lockout counters
│       │       └── dashboard_helpers.py  # Dashboard statistics & KPI aggregators
│       │
�│       ├── decorators/                   # 🛡️ ROUTE & VIEW AUTHORIZATION GUARDS
│       │   ├── __init__.py               # Re-exports @role_required, @approved_required
│       │   └── rbac.py                   # Role-based & approved-status route guards
│       │
│       ├── middleware/                   # 🛡️ REQUEST/RESPONSE SECURITY PIPELINE
│       │   ├── __init__.py               # Re-exports all middleware classes
│       │   ├── cache.py                  # DisableBrowserCacheMiddleware (no-cache headers)
│       │   ├── session.py                # SessionInactivityTimeoutMiddleware (kiosk auto-logout)
│       │   └── security.py               # SecurityHeadersMiddleware (defense-in-depth headers)
│       │
│       ├── signals/                      # ⚡ DOMAIN EVENT DISPATCHERS & AUDIT LISTENERS
│       │   ├── __init__.py               # Re-exports login/logout audit & file cleanup hooks
│       │   ├── auth_signals.py           # Auth lifecycle listeners (login/logout/failed audits)
│       │   └── file_signals.py           # File cleanup hooks (post_delete registration proof)
│       │
│       ├── validators/                   # 🛡️ DOMAIN SANITIZATION & BOUNDARY VALIDATORS
│       │   ├── __init__.py               # Re-exports identity & academic validators
│       │   ├── identity_validators.py    # Student ID format & proof document size/ext guards
│       │   └── academic_validators.py    # Academic year code, duration & section validators
│       │
│       ├── management/                   # 🤖 CUSTOM CLI MANAGEMENT COMMANDS
│       │   └── commands/
│       │       ├── __init__.py
│       │       ├── rotate_qr_seeds.py    # Automated periodic QR secret seed rotation
│       │       ├── seed_kcc_data.py      # Initial institutional baseline seeder
│       │       ├── seed_demo_roster.py   # Demo academic dataset seeder
│       │       └── create_admin.py       # Interactive admin account bootstrapper
│       │
│       ├── context_processors.py         # Global template variables (user profiles)
│       │
│       └── tests/                        # 🧪 AUTOMATED TEST SUITE (Mirrors Domain)
│           ├── __init__.py
│           ├── test_home.py              # Root landing & route redirection tests
│           ├── test_auth.py              # Sign-in, lockout thresholds, registration
│           ├── test_departments.py       # Department & Program CRUD integrity tests
│           ├── test_validation.py        # Dossier queue, QR secret rotation tests
│           ├── test_students.py          # Masterlist filtering & CSV import tests
│           ├── test_dashboard.py         # Aggregation metrics & role redirection
│           └── test_middleware.py        # Access control & session protection tests
│
├── templates/                            # 🎨 PRESENTATION LAYER
│   ├── base.html                         # Master layout with responsive navigation & alerts
│   ├── auth/                             # Login, self-registration, credential flows
│   ├── core/                             # Admin, teacher, student dashboards & queues
│   │   └── admin/                        # Departments, programs, rosters, validation queue
│   └── components/                       # Reusable UI partials (tables, badges, modal dialogs)
│
├── static/                               # ⚡ STATIC ASSET REPOSITORY
│   ├── css/                              # Theme variables, utility styles
│   ├── js/                               # Dynamic client interactivity
│   └── images/                           # Logos, institutional marks
│
├── sql/                                  # 🗄️ DATABASE ENGINE CONTRACTS
│   ├── 01_schema_constraints.sql         # DB Check constraints & foreign keys
│   └── 02_triggers.sql                   # Integrity triggers (trg_cs_profile_bu)
│
└── docs/                                 # 📚 ARCHITECTURAL & SECURITY DOCUMENTATION
    ├── 01_DEV_PLAN.md                    # Roadmap & phase breakdown
    ├── 02_SECURITY.md                    # Threat matrix & cryptographic specs
    ├── 03_UI_DESIGN_SYSTEM.md            # Color tokens, typography, component specs
    ├── 04_MODELS_REFERENCE.md            # Schema ERD & attribute dictionary
    └── 05_ARCHITECTURE_BLUEPRINT.md      # This document
```

---

## 3. Data Flow & Request Lifecycle

```text
       [ Client Browser / Mobile HTTP Request ]
                          │
                          ▼
             [ Security & Session Middleware ]
          (DisableBrowserCache, Inactivity, Headers)
                          │
                          ▼
             [ mysite/urls.py & apps/core/urls.py ]
                          │
                          ▼
             [ Decorators / RBAC Guard ]
        (e.g., @role_required, @approved_required)
                          │
                          ▼
              [ apps/core/views/ Layer ]
             (Thin HTTP Orchestration)
             /            │            \
            /             │             \
           ▼              ▼              ▼
     [ forms/ ]     [ services/ ]   [ helpers/ ]
     Validation    Business Logic   Calculations
                          │
                          ▼
                  [ models/ Layer ]
               ORM Schema & Constraints
                          │
                          ▼
              [ Signals / Audit Listeners ]
             (AuditEvent & File Cleanup)
                          │
                          ▼
              [ Database / Triggers ]
             (MySQL + InnoDB Constraints)
                          │
                          ▼
              [ serializers/ Layer ]
            Transform to Dict / JSON
                          │
                          ▼
             [ templates/ or JsonResponse ]
                          │
                          ▼
                   [ HTTP Response ]
```

---

## 4. Layer Responsibility Matrix

| Layer | Files / Packages | Key Responsibilities | What It Must NEVER Do |
|---|---|---|---|
| **Models** | `apps/core/models/` | Table schemas, indexing, foreign keys, choices | Never handle `request` objects or render templates |
| **Forms** | `apps/core/forms/` | Form fields, widget styles, field sanitization, clean methods | Never execute background jobs or manage sessions |
| **Validators** | `apps/core/validators/` | Reusable data integrity checks (student ID formats, upload file types & sizes, academic year patterns) | Never access HTTP session state or perform redirects |
| **Services** | `apps/core/services/` | Business workflows, multi-table transactions, QR rotation, audit logging | Never import `HttpRequest`, `redirect`, or `render` |
| **Views** | `apps/core/views/` | HTTP request routing, message flashes, redirects, template dispatch | Never contain 100+ line loops, raw SQL, or complex algorithms |
| **Helpers** | `apps/core/views/helpers/` | Session lock-state management, stats aggregation | Never directly modify database schemas |
| **Decorators** | `apps/core/decorators/` | View route guards, RBAC enforcement (`@role_required`), account approval checks (`@approved_required`) | Never modify response payloads or render templates directly |
| **Middleware** | `apps/core/middleware/` | Session inactivity timeout, browser cache suppression, security headers (X-Frame-Options, CSP, etc.) | Never perform heavy DB transactions or business operations |
| **Signals** | `apps/core/signals/` | Decoupled event logging (login/logout/failed auth to `AuditEvent`), file cleanup on model deletion | Never execute synchronous slow network calls or halt request thread |
| **Management** | `apps/core/management/` | Scheduled CLI automation (QR seed rotation, database seeders, admin setup) | Never depend on active HTTP request context |
| **Serializers** | `apps/core/serializers/` | Converting Model instances to dictionaries for JSON | Never perform password authentication or user logins |
| **Tests** | `apps/core/tests/` | Regression verification, security boundary audits | Never contain production application logic |bs or manage sessions |
| **Services** | `apps/core/services/` | Business workflows, multi-table transactions, QR rotation, audit logging | Never import `HttpRequest`, `redirect`, or `render` |
| **Views** | `apps/core/views/` | HTTP request routing, message flashes, redirects, template dispatch | Never contain 100+ line loops, raw SQL, or complex algorithms |
| **Helpers** | `apps/core/views/helpers/` | Session lock-state management, stats aggregation | Never directly modify database schemas |
| **Serializers** | `apps/core/serializers/` | Converting Model instances to dictionaries for JSON | Never perform password authentication or user logins |
| **Tests** | `apps/core/tests/` | Regression verification, security boundary audits | Never contain production application logic |

---

## 5. Architectural Quality Guarantees

1. **Compliance with High-Standard Production Standards**: Matches patterns used in production Django open-source codebases like **Sentry**, **Wagtail**, and **Saleor**.
2. **Ready for REST API / Mobile App Expansion**: Because business logic lives entirely in `services/`, building a mobile REST API or QR Scanner API requires only adding API view endpoints that call the existing services.
3. **Clean Defense Presentation**: High marks in capstone/thesis defense code reviews due to clear separation of concerns, zero god-files, and comprehensive unit tests.
