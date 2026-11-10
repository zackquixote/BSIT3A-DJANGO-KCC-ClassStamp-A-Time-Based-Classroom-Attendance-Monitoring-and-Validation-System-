# Requirements Document

## Introduction

This document specifies requirements for the System Integration & Enhancement Suite, a comprehensive set of 18 fixes and enhancements to the KCC ClassStamp Django attendance system. The system is a three-role (Admin/Teacher/Student) TOTP-based attendance verification platform with 15+ models, QR code authentication, and MySQL backend.

The enhancement suite addresses critical integration gaps, security hardening, workflow automation, and user experience improvements across role connectivity, data integrity enforcement, automated workflows, and communication systems.

## Glossary

- **System**: The KCC ClassStamp Django attendance management platform
- **Student**: A user with role=STUDENT whose attendance is tracked and reported
- **Teacher**: A user with role=TEACHER who manages classes, sessions, and attendance
- **Admin**: A user with role=ADMIN who oversees the entire institutional system
- **Enrollment**: The M2M binding of an approved student to a class section
- **Class**: A subject section assigned to a teacher within an academic year
- **ClassSession**: A time-bounded attendance collection window for a specific class meeting
- **CurriculumVersion**: A reviewable snapshot of a program's required subjects
- **AcademicEvent**: Calendar events including holidays, examinations, and deadlines
- **PushSubscription**: Web Push API subscription endpoint for browser notifications
- **ExcuseSlip**: A student-submitted absence justification requiring teacher/admin approval
- **AnomalyFlag**: A fraud detection alert for suspicious attendance patterns
- **PermissionService**: Centralized authorization service for object-level access control
- **Middleware**: Django request/response pipeline components
- **RBAC**: Role-Based Access Control
- **VAPID**: Voluntary Application Server Identification for Web Push
- **CSP**: Content Security Policy HTTP header for XSS protection
- **TOTP**: Time-based One-Time Password for QR code authentication

## Requirements

### Requirement 1: Curriculum-Based Enrollment Validation

**User Story:** As a system, I want to validate student enrollments against their curriculum version, so that students can only join classes that are part of their program requirements.

#### Acceptance Criteria

1. WHEN a student attempts to join a class via join code, THE System SHALL verify that the class subject exists in the student's curriculum version
2. WHEN a student's curriculum version does not include the class subject, THE System SHALL reject the enrollment and return an error message
3. WHEN a student has no curriculum version assigned, THE System SHALL reject the enrollment and prompt the student to contact administration
4. WHEN an admin or teacher manually enrolls a student, THE System SHALL validate against curriculum version with option to override
5. WHEN curriculum validation fails, THE System SHALL log the rejection in AuditEvent with student ID, class code, and reason

### Requirement 2: Class Capacity Enforcement

**User Story:** As a system, I want to enforce class capacity limits during enrollment, so that classes do not exceed their maximum roster size.

#### Acceptance Criteria

1. WHEN a class has a capacity value set, THE System SHALL count active enrollments before accepting new joins
2. WHEN active enrollment count equals or exceeds capacity, THE System SHALL reject new join code enrollments with "class full" message
3. WHEN a class has no capacity value set, THE System SHALL allow unlimited enrollments
4. WHEN an admin manually enrolls a student into a full class, THE System SHALL allow the override and log the action in AuditEvent
5. WHEN capacity is changed on an existing class, THE System SHALL not automatically remove existing enrollments

### Requirement 3: Automatic Session Cancellation on Holidays

**User Story:** As a teacher, I want sessions to be automatically cancelled when holidays are created, so that I don't have to manually cancel each affected session.

#### Acceptance Criteria

1. WHEN an AcademicEvent with CATEGORY_HOLIDAY is created, THE System SHALL identify all ClassSessions scheduled on the holiday date
2. WHEN a matching ClassSession exists, THE System SHALL update its status to CANCELED
3. WHEN a ClassSession is auto-canceled, THE System SHALL create an AuditEvent recording the holiday title and affected session
4. WHEN a holiday AcademicEvent is deleted or status changes to CANCELED, THE System SHALL not automatically restore cancelled sessions
5. WHEN a teacher manually reopens a cancelled session, THE System SHALL allow the action and log the manual override

### Requirement 4: Web Push Notification Implementation

**User Story:** As a user, I want to receive browser push notifications for important events, so that I stay informed even when not actively viewing the system.

#### Acceptance Criteria

1. THE System SHALL generate and store VAPID public and private keys on first startup
2. WHEN a user grants browser notification permission, THE System SHALL create a PushSubscription record with endpoint, p256dh, and auth keys
3. WHEN a notification-worthy event occurs, THE System SHALL send push notifications to all active PushSubscriptions for the target user
4. WHEN a push endpoint returns 410 Gone, THE System SHALL delete the expired PushSubscription record
5. WHEN a push delivery fails with retryable error, THE System SHALL log the failure in AuditEvent without raising an exception
6. WHEN notification sending is disabled via NOTIFICATIONS_ENABLED setting, THE System SHALL skip push delivery and log the skip action

### Requirement 5: Role-Based Middleware RBAC Enforcement

**User Story:** As a security officer, I want role-based access control enforced at the middleware level, so that unauthorized portal access is blocked before reaching views.

#### Acceptance Criteria

1. WHEN an authenticated user accesses a URL path starting with /admin/, THE System SHALL verify the user has role=ADMIN
2. WHEN an authenticated user accesses a URL path starting with /teacher/, THE System SHALL verify the user has role=TEACHER
3. WHEN an authenticated user accesses a URL path starting with /student/, THE System SHALL verify the user has role=STUDENT
4. WHEN role verification fails, THE System SHALL return HTTP 403 Forbidden with clear error message
5. WHEN the user is not authenticated, THE System SHALL redirect to the login page before role checking
6. WHEN the URL path is in an exempted list, THE System SHALL skip role checking for that request

### Requirement 6: Approval Status Middleware Enforcement

**User Story:** As an administrator, I want approval status enforced at the middleware level, so that unapproved students cannot access student portal features.

#### Acceptance Criteria

1. WHEN an authenticated student user accesses the student portal, THE System SHALL verify approval_status equals APPROVED
2. WHEN approval_status is PENDING or REJECTED, THE System SHALL redirect to the approval waiting page
3. WHEN the user is a teacher or admin, THE System SHALL skip approval status checking
4. WHEN the URL path is in an exempted list, THE System SHALL skip approval checking for that request
5. WHEN approval status check fails, THE System SHALL log the access attempt in AuditEvent

### Requirement 7: Centralized Permission Service

**User Story:** As a developer, I want a centralized PermissionService class, so that object-level authorization logic is consistent and maintainable.

#### Acceptance Criteria

1. THE PermissionService SHALL provide a method can_user_access_class that returns True when user has permission to view class details
2. THE PermissionService SHALL provide a method can_user_modify_session that returns True when user has permission to edit session attendance
3. THE PermissionService SHALL provide a method can_user_approve_excuse that returns True when user has permission to approve excuse slips
4. THE PermissionService SHALL provide a method can_user_manage_enrollment that returns True when user has permission to manage class enrollment
5. WHEN permission check logic changes, THE System SHALL only require updates to PermissionService methods

### Requirement 8: Internal Messaging System

**User Story:** As a student, I want to send messages to my teachers, so that I can communicate about attendance and academic matters within the system.

#### Acceptance Criteria

1. WHEN a student sends a message to a teacher, THE System SHALL create a Message record with sender, recipient, subject, and body
2. WHEN a teacher sends a message to a student, THE System SHALL verify the student is enrolled in at least one of the teacher's classes
3. WHEN a teacher sends a message to an admin, THE System SHALL create the message without enrollment verification
4. WHEN an admin sends a message to any user, THE System SHALL create the message without restriction
5. WHEN a message is created, THE System SHALL send an in-app notification and optional email notification to the recipient
6. WHEN a user accesses the messaging interface, THE System SHALL display messages grouped by conversation thread

### Requirement 9: Automated At-Risk Student Alerts

**User Story:** As a teacher, I want automatic alerts when students exceed the absence threshold, so that I can intervene early without manually checking reports.

#### Acceptance Criteria

1. THE System SHALL run a daily background task that calculates absence rates for all active enrollments
2. WHEN a student's unexcused absence rate exceeds the institutional threshold, THE System SHALL create an AnomalyFlag if none exists for the current academic year
3. WHEN an at-risk AnomalyFlag is created, THE System SHALL send push notifications and emails to both the student and teacher
4. WHEN absence rate drops below threshold after excuse slip approval, THE System SHALL mark the AnomalyFlag as RESOLVED
5. WHEN the daily task completes, THE System SHALL log the number of alerts generated in AuditEvent

### Requirement 10: Portal Template Consolidation

**User Story:** As a developer, I want shared base templates for all three portals, so that sidebar and navigation code is not duplicated.

#### Acceptance Criteria

1. THE System SHALL provide a base_portal.html template that defines common portal structure
2. WHEN rendering admin portal pages, THE System SHALL extend base_portal.html with admin-specific sidebar blocks
3. WHEN rendering teacher portal pages, THE System SHALL extend base_portal.html with teacher-specific sidebar blocks
4. WHEN rendering student portal pages, THE System SHALL extend base_portal.html with student-specific sidebar blocks
5. WHEN navigation items change, THE System SHALL only require updates to the role-specific sidebar block

### Requirement 11: Enhanced Schedule Conflict Detection

**User Story:** As an admin, I want the system to detect room and teacher double-booking, so that scheduling conflicts are prevented before sessions are created.

#### Acceptance Criteria

1. WHEN creating or editing a ClassSlot, THE System SHALL check for teacher double-booking in the same time window
2. WHEN creating or editing a ClassSlot, THE System SHALL check for room double-booking in the same time window
3. WHEN a conflict is detected, THE System SHALL return error details including conflicting class code and time range
4. WHEN the conflict detection service is called, THE System SHALL exclude the current slot being edited from conflict checks
5. WHEN academic year is specified, THE System SHALL only check conflicts within that academic year

### Requirement 12: Academic Year Rollover

**User Story:** As an admin, I want to roll over class structures to a new academic year, so that I don't have to manually recreate classes each term.

#### Acceptance Criteria

1. WHEN admin initiates rollover from source academic year to target academic year, THE System SHALL copy all active classes to the target year
2. WHEN copying a class, THE System SHALL copy class_code, section_code, subject, teacher, program, year_level, and capacity
3. WHEN copying a class, THE System SHALL copy all ClassSlots with the same weekday, times, and room
4. WHEN copying a class, THE System SHALL not copy enrollments, sessions, or join codes
5. WHEN rollover completes, THE System SHALL return a summary report with copied class count and any errors

### Requirement 13: Bulk Excuse Slip Approval

**User Story:** As a teacher, I want to approve multiple excuse slips at once, so that I can process excuse requests more efficiently.

#### Acceptance Criteria

1. WHEN a teacher selects multiple excuse slips, THE System SHALL provide a bulk approve action
2. WHEN bulk approve is submitted, THE System SHALL update all selected slips to APPROVED status
3. WHEN bulk approve completes, THE System SHALL send individual notifications to each affected student
4. WHEN bulk approve encounters an error on one slip, THE System SHALL process remaining slips and report the error
5. WHEN bulk approve completes, THE System SHALL log the action in AuditEvent with count of approved slips

### Requirement 14: PDF Report Export

**User Story:** As a teacher, I want to export attendance reports as PDF files, so that I can print and submit official attendance records.

#### Acceptance Criteria

1. WHEN a user exports an attendance matrix, THE System SHALL provide both CSV and PDF export options
2. WHEN PDF export is selected, THE System SHALL generate a PDF with class header, student list, and attendance grid
3. WHEN generating PDF, THE System SHALL include report generation timestamp and user who generated it
4. WHEN PDF generation fails, THE System SHALL return an error message and allow CSV fallback
5. WHEN PDF is generated, THE System SHALL set appropriate Content-Disposition header for download

### Requirement 15: Predictive Attendance Analytics

**User Story:** As a teacher, I want to see predicted final attendance rates, so that I can identify students who may fail the attendance requirement.

#### Acceptance Criteria

1. WHEN viewing class analytics, THE System SHALL display a linear regression prediction for each student's final attendance rate
2. WHEN calculating predictions, THE System SHALL use historical attendance trends from the current academic year
3. WHEN predicted final rate is below the passing threshold, THE System SHALL highlight the student with warning color
4. WHEN insufficient data exists for prediction, THE System SHALL display "insufficient data" instead of a prediction
5. WHEN prediction model is updated, THE System SHALL log the algorithm version in AuditEvent

### Requirement 16: API Rate Limiting

**User Story:** As a security officer, I want rate limiting on all API endpoints, so that the system is protected from abuse and denial-of-service attacks.

#### Acceptance Criteria

1. THE System SHALL apply rate limiting to all endpoints under /api/ and /student/scan/
2. WHEN an authenticated user exceeds 100 requests per minute, THE System SHALL return HTTP 429 Too Many Requests
3. WHEN an anonymous user exceeds 20 requests per minute, THE System SHALL return HTTP 429 Too Many Requests
4. WHEN rate limit is exceeded, THE System SHALL include Retry-After header with seconds to wait
5. WHEN rate limiting is applied, THE System SHALL log repeated violations in AuditEvent

### Requirement 17: Content Security Policy

**User Story:** As a security officer, I want a Content Security Policy enforced, so that the system is protected from cross-site scripting and code injection attacks.

#### Acceptance Criteria

1. THE System SHALL send a Content-Security-Policy header with every HTTP response
2. THE System SHALL allow scripts only from self and inline scripts with nonce
3. THE System SHALL allow styles only from self and inline styles
4. THE System SHALL allow images from self, data URIs, and HTTPS sources
5. WHEN CSP violation is reported, THE System SHALL log the violation in AuditEvent

### Requirement 18: Teacher-Room Conflict Detection Service

**User Story:** As a scheduler, I want the conflict detection service to check both teacher and room availability, so that double-booking is prevented at schedule creation time.

#### Acceptance Criteria

1. WHEN detect_slot_conflicts is called, THE System SHALL check for teacher double-booking by matching teacher_profile_id and time overlap
2. WHEN detect_slot_conflicts is called, THE System SHALL check for room double-booking by matching room name and time overlap
3. WHEN multiple conflicts exist, THE System SHALL return all conflicts as a list of conflict dictionaries
4. WHEN room is empty or "TBA", THE System SHALL skip room conflict checking
5. WHEN conflicts are found, THE System SHALL include conflict type, class_code, weekday, time range, room, and teacher name in each conflict record

## Special Requirements: Parser and Serializer

This system does not require custom parsers or serializers. All data validation and serialization is handled by Django's built-in form validation, model serialization, and JSON encoding.

## Special Requirements: Security Hardening

### Requirement 19: Session Security Enhancement

**User Story:** As a security officer, I want session cookies hardened, so that session hijacking is prevented.

#### Acceptance Criteria

1. THE System SHALL set SESSION_COOKIE_HTTPONLY to True to prevent JavaScript access
2. THE System SHALL set SESSION_COOKIE_SECURE to True in production to require HTTPS
3. THE System SHALL set SESSION_COOKIE_SAMESITE to 'Lax' to prevent CSRF attacks
4. THE System SHALL set SESSION_COOKIE_AGE to 14400 seconds (4 hours) for automatic timeout
5. THE System SHALL regenerate session IDs after login to prevent fixation attacks

### Requirement 20: Password Policy Enforcement

**User Story:** As a security officer, I want password policies enforced, so that weak passwords cannot be used.

#### Acceptance Criteria

1. THE System SHALL require minimum password length of 8 characters
2. THE System SHALL require at least one uppercase letter, one lowercase letter, one digit, and one special character
3. WHEN password validation fails, THE System SHALL display specific requirements that were not met
4. THE System SHALL reject passwords that match common password lists
5. THE System SHALL enforce password history to prevent reuse of last 5 passwords
