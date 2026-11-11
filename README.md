# KCC ClassStamp - A Time-Based Classroom Attendance Monitoring and Validation System

A **Django-powered**, QR-code-based attendance system for KCC with 3 role-based portals: Admin, Teacher, and Student.

### 👥 Group Members
- **RONELO DACILLO**
- **LOURD IAN AKOL**
- **YASTER JOSHUA DADO**

*10/7/2026 — 100 Points*

### 🔒 Security

ClassStamp includes defense-in-depth controls for authentication, authorization, attendance credentials, uploads, and browser delivery. The implemented controls are documented in [02_SECURITY.md](docs/02_SECURITY.md).

---

# KCC ClassStamp - A Time-Based Classroom Attendance Monitoring and Validation System
## BSIT Capstone Project Concept Paper

## INTRODUCTION

### BACKGROUND OF THE PROJECT
At Kabankalan Catholic College, Inc. (KCC), a private school in Kabankalan City, Negros Occidental, teachers use laptops and attendance sheets in their classroom attendance process. The proposed project will build on these existing practices by adding support for schedule-based validation, consistent attendance classification, monitoring, and report preparation. Teachers and administrators will continue to manage attendance procedures, academic records, reviews, and decisions; KCC ClassStamp will provide information and workflow tools to assist them.

To address the need for additional attendance support, the project will develop KCC ClassStamp, a web-based attendance support system. It will use dynamic student QR badges and compare scans with encoded weekly class schedules and the centralized server clock. For an open, authorized session, it will record scans and assist with attendance classification as Present, Late, Absent, or Excused. It will also prepare attendance summaries, CSV session ledgers, and Excel workbooks for review by instructors and academic administrators. Teachers and academic administrators will use these outputs within their existing attendance and review processes. The system will support students who do not have an active data connection through a single-use offline badge valid for up to forty-eight hours. It will not replace existing manual academic administration. Authorized administrators and teachers will remain responsible for manually encoding and maintaining academic records, schedules, instructor assignments, and class rosters. CSV upload will be a convenience for student directories. Administrators will review and decide account approvals, while instructors will review attendance exceptions and excuse requests. The system will provide information and workflow tools to support those duties.

### STATEMENT OF THE PROBLEM OR PROJECT OBJECTIVES
The main objective of this project will be to design, develop, and evaluate KCC ClassStamp, a web-based attendance support system that will assist with time-bound attendance recording and validation, help deter attendance fraud, and provide useful records for teachers and administrators. It will support, and will not replace, the institution's manual administrative and record-keeping procedures or the decisions made by authorized personnel.

---

## SPECIFIC OBJECTIVES
Specifically, the project will pursue the following objectives while keeping teachers and administrators responsible for their existing duties and decisions:

1. **User Account & Role-Based Access:** The project will provide secure user account and profile management with role-based access for system administrators, teachers or instructors, and students. An approval queue will organize student applications for administrator review; an authorized administrator will make each approval or rejection decision.
2. **Dynamic TOTP Student Identification:** The project will implement dynamic student identification badges using a Time-Based One-Time Password (TOTP) algorithm to generate time-varying QR codes and help deter screenshot reuse and proxy attendance.
3. **Time-Based Attendance Validation:** The project will construct a time-based validation engine that will compare scans with manually encoded weekly class schedule slots and a configurable per-class grace period. The system will assist with classifying attendance as Present, Late, Absent, or Excused; authorized instructors will retain responsibility for reviewing exceptions and applying institutional rules.
4. **Faculty Browser Camera Scanning:** The project will provide a browser-based scanning module for faculty-operated smartphones, tablets, or laptops using the HTML5 camera interface. It will support a single-use forty-eight-hour offline badge and queue scans captured while the scanning device is disconnected. Faculty members will operate the scanner and remain responsible for classroom attendance procedures.
5. **Anomaly Indicators & Audit Records:** The project will provide discrepancy and anomaly indicators for duplicate or replayed scans within a session, invalid or expired tokens, and out-of-schedule attempts, with events recorded in an audit trail designed to be append-only. An absence radar will present Safe, Watchlist, or Failure Due to Absences (FDA) Risk indicators in reference to the twenty percent (20%) absence ceiling cited in applicable CHED and institutional attendance policies. These indicators will support review by teachers and administrators, who will make intervention decisions. The system will prepare CSV session ledgers and Excel workbooks for Midterm and Finals compliance review.
6. **Student Self-Service Portal:** The project will provide a student self-service portal where learners will be able to view their personal attendance ledger, review subject-level compliance information, manage profile information, and submit digital excuse slips with supporting documents. Instructors will review the submissions and make the appropriate decisions.
7. **User Acceptance Testing (UAT):** The project will conduct user acceptance testing (UAT) with students, faculty members, and academic administrators. Using selected characteristics of the ISO/IEC 25010 software quality model, the evaluation will assess functional suitability, usability, and operational reliability.

---

## SIGNIFICANCE OF THE PROJECT
The proposed system will provide support and practical information to the following beneficiaries; it will not replace their roles or decision-making responsibilities:

- **Subject Teachers and Instructors:** The system will support teachers who use laptops, attendance sheets, or both by assisting with attendance validation, tallying, monitoring, and report preparation. It will complement their current workflow, not replace their attendance-taking role, review, or decisions.
- **Students:** The system will help students review their attendance standing and submit supporting documents for excuse requests. Instructors will continue to review and decide those requests.
- **Academic Department Chairs and School Administrators:** The system will provide summaries and indicators to support monitoring and timely intervention. Authorized personnel will retain responsibility for interpreting records and deciding appropriate actions.
- **Future Researchers and Developers:** The project will provide a reference for developing attendance support and web-based validation systems.

### Alignment with Institutional Research Agenda and Sustainable Development Goals
- **Institutional Research Agenda Alignment:** The project will support the institutional priority on Digital Transformation and Smart Campus Management by providing tools for attendance monitoring and record organization while retaining human administrative oversight.
- **SDG 4 (Quality Education):** The system will support attendance monitoring and help reduce repetitive validation and report preparation work, where applicable, while teachers retain responsibility for instruction and student support.
- **SDG 9 (Industry, Innovation, and Infrastructure):** The project will apply web technologies to support a classroom administrative process without replacing the personnel who perform it.

---

## SCOPE AND LIMITATIONS

### SYSTEM SCOPE AND TECHNICAL ARCHITECTURE
The project will cover attendance monitoring and validation as support for students, instructors, and academic administrators. It will not automate or replace manual academic administration, teacher-led classroom procedures, or decisions reserved for authorized personnel.

| Component | Description & Coverage |
| :--- | :--- |
| **Core Modules** | Account authentication and role-based access with an administrator-review queue; manually managed academic setup and scheduling; dynamic TOTP QR badges; faculty-operated browser camera scanning; single-use forty-eight-hour offline badges and scan buffering; time-bound validation that assists attendance classification; student attendance records, compliance information, profile tools, and excuse slip submission for instructor review; anomaly indicators and audit records; and CSV/Excel reports for review by teachers and administrators. Manual encoding, approval decisions, attendance exception review, and academic interventions will remain with authorized personnel. |
| **Technology Stack** | **Backend:** Python 3.11 as the planned deployment runtime and Django 4.2.<br>**Database:** MySQL through XAMPP for the default local development setup; SQLite3 may be used in environments explicitly configured for SQLite.<br>**Frontend:** HTML5, CSS3 with a responsive dark theme using CSS Grid and Flexbox, and Vanilla JavaScript (ES6+), with Lucide and Font Awesome 6 icons.<br>**Key Libraries:** PyOTP for RFC 6238 TOTP, an HTML5 QR-scanning library, QRCode and Pillow for badge rendering, and OpenPyXL for Excel reports. |
| **Target Users** | Enrolled students, subject faculty and instructors, and authorized academic system administrators within the institution. |

### LIMITATIONS
- **Student Connectivity and Offline Badge:** A single-use offline badge will be issued while the student is connected and will remain valid for up to forty-eight (48) hours or until its first redemption. The student will be able to present the badge as a saved or screenshotted image. An expired or redeemed badge will not be accepted, and a replacement will require a new issuance while connected. Because the badge will act as a bearer credential, another person may present a copied badge within its validity window. Single-use redemption, one active badge per student, duplicate-stamp rejection, and audit logging will help limit this exposure. Binding a badge to a specific class session or physical device will be outside the scope of this phase.
- **Real-Time Validation Boundary:** The server will remain the authority for accepting or rejecting scans. Time-window checks will use the server clock set to Asia/Manila (UTC+8), regardless of the client device time; the server will need to remain synchronized with an institutional time source. Scans captured while the scanning device is disconnected will be queued and submitted after connectivity returns, provided the session remains open. A queued live badge code will normally have expired by then, so the offline badge will be the practical credential for student connectivity gaps. Queued entries will be classified according to synchronization time, not original scan time. Entries submitted after a session closes will be rejected and recorded through the authorized manual override path. Reconstruction of offline scan times will be outside the scope of this phase.
- **Device and Hardware Requirements:** Faculty scanning will require a device with a working camera and a browser that supports the HTML5 MediaDevices API. Dedicated biometrics, including fingerprint scanners and facial-recognition gates, and RFID turnstiles will be outside the scope of this project.
- **Administrative and Notification Boundaries:** The system will not integrate with an external Student Information System or registrar database and will not automatically create instructors, subjects, or schedules. Authorized personnel will encode and maintain academic master data manually; CSV bulk upload will be provided only as a convenience for student directories. The system will organize approval requests, but administrators will make approval decisions. Teachers will review attendance exceptions and excuse slips and retain responsibility for their classes. Approval and rejection notices will be delivered through in-system notifications and registered e-mail, subject to the SMTP configuration at deployment. Automated SMS broadcasting will be excluded.
