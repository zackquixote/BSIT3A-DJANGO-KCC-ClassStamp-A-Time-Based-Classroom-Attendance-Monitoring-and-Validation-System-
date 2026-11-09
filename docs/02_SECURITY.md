# KCC ClassStamp Security

This document describes the security controls currently implemented in the
application. It is an implementation reference, not a backlog.

## Authentication

- Django `authenticate()` and `login()` are used for account authentication.
- Login failures are tracked in cache by account and IP address, with a five-attempt
  threshold and temporary lockout.
- Successful login and completed recovery flows rotate the Django session key.
- Password changes are validated through Django's configured password validators.
- Privileged admin and registrar accounts can use TOTP 2FA and hashed recovery codes.
- Password reset tokens are time-limited Django tokens and reset operations are audited.

## Authorization and account state

- View-level login and role checks enforce access for ADMIN, TEACHER, and STUDENT roles.
- Teacher and student features also use account approval checks.
- Access checks are enforced by backend views rather than template visibility alone.
- Active sessions can be revoked when student credentials are rotated or a high-risk
  account change requires it.

## Attendance credentials and replay prevention

- Student QR credentials are randomly generated 64-character hexadecimal seeds.
- Attendance tokens use TOTP verification with a bounded time-window.
- QR credential rotation creates a new seed, revokes unconsumed offline badges, and
  records an audit event.
- Student, class-session, schedule, time-window, and replay checks are enforced during
  QR scans. Scan attempts and suspicious outcomes are recorded for review.

## Protected uploads and documents

- Registration proofs and excuse attachments are limited to PDF, JPG, JPEG, PNG, and
  WEBP, with a 5 MB maximum and server-side size validation.
- File signatures and image decoding are checked so renamed or corrupted files are rejected.
- Registration proofs and excuse attachments are not publicly routed under `/media/`.
- Private document views enforce ownership and role-based access:
  - registration proofs: owning student or ADMIN;
  - excuse attachments: owning student, assigned TEACHER, or ADMIN.
- Protected responses disable caching and set `X-Content-Type-Options: nosniff`.

## Browser and transport security

- Django CSRF protection and server-side form validation are used for state-changing requests.
- Production cookies are HTTPS-only, HttpOnly, and SameSite=Lax.
- Production redirects HTTP to HTTPS and enables HSTS.
- Security middleware sets CSP, MIME-sniffing, referrer, permissions, cross-origin opener,
  and XSS-protection headers.
- Production framing is denied and sensitive responses are prevented from being cached.

## Auditability

Security-sensitive account, credential, approval, override, and system changes are
recorded in `AuditEvent` where the corresponding workflow is implemented.
