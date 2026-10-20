# 🏛️ KCC ClassStamp — Admin Improvement & Feature Roadmap

This document outlines the strategic enhancements and quality-of-life roadmap for the **KCC ClassStamp Administrative Portal**.

---

## 🔒 System Boundaries & Role Separation

In KCC ClassStamp, responsibilities are strictly compartmentalized across roles:

| Persona | Core Responsibility | QR / Attendance Responsibility |
|---|---|---|
| **Admin** | Institutional Structure, Account Lifecycle, Validation, Masterlists, User Management, Security Audit | **NO QR code, NO attendance scanning, NO session handling.** (Purely administrative oversight of institutional data). |
| **Teacher** | Class Delivery, Subject Instruction, Classroom Attendance | **Opens/closes class sessions, scans student QR codes**, marks Present/Late/Absent/Excused. |
| **Student** | Academic Attendance & Schedule | **Holds dynamic TOTP QR badge**, views personal attendance history and absence warnings. |

> [!IMPORTANT]
> **Admin Scope Boundary:** The Admin portal does **not** generate QR codes, scan QR badges, or oversee day-to-day attendance sessions. Attendance tracking is strictly the Teacher's responsibility in the classroom. The improvements below focus **100% on administrative, institutional, account management, and security capabilities**.

---

## 📌 Executive Summary

The Admin side handles the foundational backbone of the college. The enhancement roadmap focuses on **5 core administrative pillars**:

1. **Account Validation & Registration Pipeline** (Batch Approvals, Document Preview Drawers, Rejection Templates)
2. **Student Masterlist & Lifecycle Management** (In-Place Profile Editing, Batch CSV Ingestion, Term Promotion)
3. **Faculty & Department Administration** (Teacher Provisioning, Department Load Mapping, Account Credentials)
4. **Academic Organisation & Curriculum Matrix** (Program-Centric Curriculum Builder, Academic Year Rollover)
5. **Security, User Management & System Diagnostics** (Advanced Audit Filtering, Live Badges, Database Snapshots)

---

## 1. 📋 Account Validation Queue Enhancements

*Currently: Admins inspect pending student dossiers one-by-one by navigating to individual detail pages.*

### 1.1 Batch / Bulk Approval Actions
* **Problem:** At the start of a semester, hundreds of students register. Approving them one-by-one is tedious.
* **Enhancement:**
  * Add multi-select checkboxes to `/validation/pending/`.
  * **Batch Action Toolbar:**
    * 🟢 **Bulk Approve Selected (N):** Approves profiles, provisions their 64-char QR secrets, and emits batch audit logs in a single atomic transaction.
    * 🔴 **Bulk Reject Selected:** Opens a modal to select a standard rejection reason (e.g., "Blurry COR proof", "Invalid Student ID") and applies it to selected students.

### 1.2 Slide-Over Dossier Preview Drawer
* **Problem:** Clicking a student redirects away to `/validation/<student_number>/`.
* **Enhancement:**
  * Add a slide-over off-canvas drawer or modal right on the validation queue.
  * Preview Certificate of Registration (COR) image/PDF and physical badge proof without page reloads.
  * Keyboard navigation: `A` to Approve, `R` to Reject, `J`/`K` to move between students, `Esc` to close.

### 1.3 Predefined Rejection Reason Templates
* **Enhancement:**
  * Dropdown of standard registrar rejection reasons ("COR Unreadable", "Student ID Mismatch", "Wrong Program Selected", "Duplicate Registration").
  * Admins can click a template to auto-populate the rejection note.

---

## 2. 🎓 Student Masterlist & Directory Enhancements

*Currently: `/students/` provides a filterable table of students with CSV export and import.*

### 2.1 In-Place Student Profile Editor
* **Problem:** If a student enters a typo in their student number, name, or selects the wrong program/year level during registration, there is currently no admin edit modal.
* **Enhancement:**
  * Add an **"Edit Profile"** action modal in the Student Directory.
  * Allow admins to:
    * Correct Student ID number.
    * Reassign enrolled Program or Department.
    * Update Standing Year Level (1st, 2nd, 3rd, 4th Year).
    * Reset / re-rotate the student's 64-character TOTP QR secret seed if compromised.

### 2.2 End-of-Year Student Promotion Utility
* **Problem:** Advancing students to the next academic year requires manual updating.
* **Enhancement:**
  * 1-click batch promotion tool:
    * Select Program and Current Year (e.g., BSIT 1st Year).
    * Promote all approved students to 2nd Year (`year_level += 1`).
    * Graduating 4th-year students transition to an "Alumni / Completed" status.

### 2.3 Advanced CSV Import with Validation Preview
* **Problem:** Uploading a CSV directly ingests records without a visual confirmation step.
* **Enhancement:**
  * **Step 1: Upload CSV** $\to$ **Step 2: Preview & Map** (shows table of rows, flags invalid rows, highlights duplicates) $\to$ **Step 3: Confirm Import**.

### 2.4 Official PVC Student ID Badge Generator
* **Enhancement:**
  * 1-click batch generation of official printable KCC Student ID cards (CR80 PVC card format).
  * Auto-renders student photo, barcode/QR containing institutional `student_number`, program name, and emergency contact details for physical badge printing.

---

## 3. 👨‍🏫 Faculty & Department Administration

*Currently: `/teachers/` allows direct account creation, updating, and active/inactive toggling.*

### 3.1 Teacher Department Reassignment & Load Overview
* **Enhancement:**
  * Quick department transfer modal: Move a teacher between academic departments (e.g., General Education $\to$ CCS).
  * Direct overview of assigned courses/loads per faculty member.

### 3.2 One-Click Password Reset & Account Recovery
* **Problem:** If a teacher forgets their login password, an admin has to navigate into Django admin or run a CLI command.
* **Enhancement:**
  * Add a "Reset Password" button in the Teacher Directory that sets a temporary password and flags the account to require a password change on next login.

---

## 4. 🏛️ Academic Organisation & Curriculum Matrix

*Currently: Departments, Programs, Subjects, and Academic Years have separate CRUD interfaces.*

### 4.1 Program-Centric Curriculum Matrix Builder
* **Problem:** Adding subjects to programs is currently done per-subject at `/subjects/<id>/curriculum/`.
* **Enhancement:**
  * Inside each Program page (`/programs/<id>/`), provide a visual **Curriculum Matrix**:
    * Structured by Year Level (1st Year to 4th Year) and Semester (1st Sem / 2nd Sem).
    * Add/remove subjects directly into the program prospectus in one place.

### 4.2 Semester / Academic Term Rollover Wizard
* **Problem:** Transitioning between school years (e.g., `2024-2025 2nd Sem` $\to$ `2025-2026 1st Sem`) requires manual configuration.
* **Enhancement:**
  * A guided **Term Rollover Wizard**:
    1. Select the new term to activate.
    2. Deactivate the prior term.
    3. Option to trigger student year-level promotions.
    4. Log full transition in Audit Events.

### 4.3 Subject Code Conflict & Prerequisite Mapping
* **Enhancement:**
  * Prevent duplicate course codes across departments.
  * Optional prerequisite linking (e.g., `IT 211` requires `IT 101`).

---

## 5. 🛡️ Security, User Management & System Diagnostics

*Currently: System has an audit log viewer and standard user management.*

### 5.1 Advanced Audit Log Multi-Filtering & Export
* **Problem:** The audit log currently displays a linear list of recent events.
* **Enhancement:**
  * Multi-attribute filter bar:
    * **Actor:** Filter by specific admin or user.
    * **Action Type:** `APPROVE_STUDENT`, `REJECT_STUDENT`, `CREATE_TEACHER`, `DELETE_PROGRAM`, `LOGIN_FAILED`.
    * **Date Range:** Today, Last 7 Days, Month, or Custom Date Picker.
  * Export Audit Trail to CSV for institutional accreditation and security reviews.

### 5.2 Real-Time Badge Polling (No Reloads)
* **Enhancement:**
  * Background polling of `/api/admin/pending-count/` every 45 seconds.
  * Automatically updates the pending badge count in the sidebar and dashboard without requiring full page reloads.

### 5.3 Non-Blocking Toast Notifications & UI Polish
* **Enhancement:**
  * Replace native browser popups (`confirm()`, `alert()`) and harsh page reloads with smooth asynchronous toast alerts.
  * Micro-animations for card actions, status toggles, and modal openings.

### 5.4 Database Snapshot & Media Storage Maintenance
* **Enhancement:**
  * **1-Click Database Dump:** Admin button to download a compressed database backup (`.sql.gz`) prior to major updates.
  * **Storage Optimizer:** Automatic WebP compression for student registration proofs and ID photos to preserve server disk space.
  * **Dossier Cleanup Tool:** Purge rejected registration attachments older than 60 days to respect data privacy principles.

---

## 🗺️ Implementation Priority Matrix (Admin Scope Only)

| Priority | Feature / Module | Target Area | Effort |
|---|---|---|---|
| 🔴 **Urgent** | **Batch Validation & Quick Dossier Slide-Over** | Account Validation | Medium |
| 🔴 **Urgent** | **In-Place Student Profile Editor** | Student Directory | Low |
| 🟡 **High** | **Program-Centric Curriculum Matrix Builder** | Academic Organisation | Medium |
| 🟡 **High** | **End-of-Year Student Promotion Utility** | Student Directory | Low |
| 🟡 **High** | **Real-Time Sidebar Pending Count Polling** | UI / Sidebar | Low |
| 🟢 **Medium** | **Academic Term Rollover Wizard** | Academic Years | Medium |
| 🟢 **Medium** | **Advanced Audit Log Filters & Export** | Security & Auditing | Low |
| 🟢 **Medium** | **Predefined Rejection Reason Templates** | Account Validation | Low |
| ⚪ **Polish** | **1-Click Database Backup Tool** | System Maintenance | Low |
| ⚪ **Polish** | **Printable PVC Student ID Badge Generator** | Student Directory | Medium |
| ⚪ **Polish** | **Storage Optimizer & COR Proof Cleaner** | Maintenance & Storage | Low |
