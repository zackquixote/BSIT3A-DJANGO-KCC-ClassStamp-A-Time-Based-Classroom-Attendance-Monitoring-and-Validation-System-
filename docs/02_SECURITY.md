# 🔐 KCC ClassStamp — Security Guidelines

This document defines all security rules and patterns for the KCC ClassStamp system.
Every developer and every AI agent working on this project **must follow these rules**.

---

## 1. Authentication & Session Security

### Login
- Use Django's built-in `authenticate()` + `login()` — never roll your own
- Enforce **brute-force protection**: lockout after 5 failed attempts (already in `core/views.py`)
- Use `@login_required(login_url='login')` on every view that requires auth
- Never expose `is_authenticated` check in templates as the sole guard — always guard at the view layer

### Session
- Use `SESSION_COOKIE_HTTPONLY = True` (prevents JS access)
- Use `SESSION_COOKIE_SAMESITE = 'Lax'`
- For production: `SESSION_COOKIE_SECURE = True` (HTTPS only)
- Regenerate session after login (`request.session.cycle_key()`)

---

## 2. Role-Based Access Control (RBAC)

### The 3 Roles
```
Profile.ROLE_ADMIN   = 'ADMIN'
Profile.ROLE_TEACHER = 'TEACHER'
Profile.ROLE_STUDENT = 'STUDENT'
```

### Guard Pattern — use these decorators everywhere:

```python
# apps/core/decorators.py

from functools import wraps
from django.shortcuts import redirect

def role_required(*roles):
    """Restrict a view to specific Profile roles."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            profile = getattr(request.user, 'classstamp_profile', None)
            if profile is None or profile.role not in roles:
                return redirect('dashboard')  # or 403
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

def approved_required(view_func):
    """Ensure student/teacher account has been approved by admin."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        profile = getattr(request.user, 'classstamp_profile', None)
        if profile and profile.approval_status != 'APPROVED':
            return redirect('pending_approval')
        return view_func(request, *args, **kwargs)
    return wrapper
```

### Usage:
```python
@login_required(login_url='login')
@role_required('ADMIN')
def admin_dashboard(request): ...

@login_required(login_url='login')
@role_required('TEACHER')
@approved_required
def teacher_dashboard(request): ...

@login_required(login_url='login')
@role_required('STUDENT')
@approved_required
def student_dashboard(request): ...
```

### NEVER:
- Check role in templates only (e.g., `{% if user.profile.role == 'ADMIN' %}`) without a view-layer guard
- Allow Teacher to access Admin URLs
- Allow unapproved accounts to access dashboards

---

## 3. QR Code & TOTP Security

### QR Secret
- `Profile.qr_secret` is a 32-character base32 secret — **never expose this in any API response or template**
- Generate on account approval only: `pyotp.random_base32()`
- Store encrypted at rest (consider Django's encrypted fields for production)

### TOTP Validation
```python
import pyotp

def verify_student_qr(student_profile, token):
    totp = pyotp.TOTP(student_profile.qr_secret)
    return totp.verify(token, valid_window=1)  # ±30s tolerance
```

### QR Payload Format
```
classstamp:<student_number>:<totp_token>
```
- **Never put** student names, emails, or any PII directly in the QR payload
- Token expires in 30s — reject anything older

### Replay Attack Prevention
- Use `StampAttempt` model to log every scan with outcome
- Check for `DUPLICATE` outcome before accepting — one scan per session per student

---

## 4. CSRF Protection

- Never disable `{% csrf_token %}` in forms
- For AJAX POST requests, always include the CSRF token:
```javascript
// In every AJAX POST:
headers: { 'X-CSRFToken': document.cookie.match(/csrftoken=([^;]+)/)[1] }
```
- Use `@require_POST` decorator on all state-changing views

---

## 5. SQL Injection & ORM Rules

- **Always** use Django ORM — never raw SQL unless absolutely necessary
- If raw SQL is unavoidable, use parameterized queries:
```python
# NEVER:
cursor.execute(f"SELECT * FROM table WHERE id = {user_id}")

# ALWAYS:
cursor.execute("SELECT * FROM table WHERE id = %s", [user_id])
```

---

## 6. Input Validation

- Validate all form inputs server-side (never trust client-side only)
- Use Django form classes or manual validation — never `request.POST.get()` directly into DB without sanitizing
- Strip whitespace on all text inputs: `.strip()`
- Validate email with `validate_email()` from `django.core.validators`

---

## 7. File Upload Security (if needed in future)

- Restrict allowed file types (whitelist, not blacklist)
- Never serve uploaded files from the web root directly
- Validate file content (not just extension)
- Store uploads outside `MEDIA_ROOT` if they contain sensitive data

---

## 8. Secret Management

### Settings:
```python
# settings.py — NEVER hardcode secrets
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
DATABASES = { 'default': { 'PASSWORD': os.environ.get('DB_PASSWORD') } }
DEBUG = os.environ.get('DEBUG', 'False') == 'True'
```

### Never commit:
- `.env` files
- Database passwords
- Secret keys
- QR secrets or TOTP seeds

### `.gitignore` must include:
```
.env
*.env
local_settings.py
db.sqlite3
```

---

## 9. Security Headers (for production)

Add to `settings.py`:
```python
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
```

---

## 10. Audit Trail

- Every significant action must be logged in `AuditEvent`
- Log: account approvals, rejections, attendance overrides, QR secret rotation
- Never delete audit events — append only

```python
from apps.core.models import AuditEvent

AuditEvent.objects.create(
    actor=request.user,
    action='APPROVE_ACCOUNT',
    object_type='Profile',
    object_id=str(profile.pk),
    new_value=f'Approved by {request.user.username}',
)
```
