# 🎓 KCC ClassStamp — Student Experience & Feature Roadmap

This document outlines the strategic enhancements, architectural vision, and initial roadmap for the **KCC ClassStamp Student Portal**.

---

## 🔒 Role Separation & Scope Boundary

In KCC ClassStamp, responsibilities are strictly compartmentalized across user personas:

| Persona | Core Responsibility | Classroom & Attendance Role |
|---|---|---|
| **Admin** | Institutional Structure, Account Validation, Masterlists, Academic Years, Security Audits | **NO QR scanning, NO active session control.** Administrative oversight only. |
| **Teacher** | Class Delivery, Subject Instruction, Classroom Attendance | **Opens/closes class sessions, operates live QR camera scanner, adjudicates manual attendance overrides.** |
| **Student** | Academic Attendance & Schedule | **Holds dynamic TOTP QR badge**, views personal attendance records, monitors absence risk thresholds, and tracks enrolled class schedules. |

> [!IMPORTANT]
> **Student Scope Boundary:** Students are attendees. They do **not** take attendance, open sessions, or alter records. Their portal must be **frictionless on mobile phones**, high-contrast for quick scanning under fluorescent classroom lights, and transparent about their attendance standing.

---

## 📌 Executive Summary

The Student Portal is built around three core student moments:
1. **Entering the Classroom:** Instant access to their dynamic, rotating QR badge with zero loading lag.
2. **Checking Academic Standing:** Clear transparency on absences, tardiness, and risk levels per enrolled subject.
3. **Weekly Schedule Navigation:** Knowing where their classes are, what rooms to go to, and who is teaching.

The enhancement roadmap is organized into **4 Core Pillars**:

1. **Dynamic TOTP Badge Chamber** (Anti-screenshot rotating QR, 30s countdown ring, offline TOTP generation)
2. **Personal Academic Ledger & History** (Subject-by-subject attendance logs, date filters, status breakdown)
3. **Absence Warning & CHED 20% Sentinel** (Proactive alerts before reaching Failure Due to Absences / FDA)
4. **Enrolled Classes & Timetable Hub** (Weekly schedule view, subject instructor info, room assignments)

---

## 1. 📱 Dynamic TOTP QR Badge Chamber

*Current State: Dashboard displays a placeholder mentioning Phases 3 & 5.*

### 1.1 Live Rotating TOTP QR Code
* **How It Works:**
  * Backend provisions a 64-character hex secret (`qr_secret`) upon profile approval.
  * Student portal generates a 6-digit TOTP token using `pyotp` (or client-side JS with HMAC-SHA1).
  * Payload format: `classstamp:<student_number>:<6-digit-token>`.
  * Rotates every **30 seconds** with an animated SVG countdown ring.
* **Anti-Cheating / Anti-Proxy Protections:**
  * QR expires after 30 seconds — prevents students from texting screenshots to absent friends.
  * Watermark with student photo/avatar, student ID, and live pulsing digital clock.

### 1.2 Offline-Ready QR Badge (PWA / Local Storage)
* **Problem:** Weak or dead cell service inside campus ground-floor classrooms or basements.
* **Solution:**
  * Store the student's encrypted badge secret in local browser storage on approved login.
  * Generate the rotating 30-second token entirely in client-side JavaScript (`otplib` or lightweight HMAC).
  * Works 100% offline without cellular data or Wi-Fi.

---

## 2. 📊 Subject Attendance Ledger & History

*Current State: Dashboard shows simple counts (Present: 0, Late: 0, Absent: 0, Enrolled: 0).*

### 2.1 Per-Subject Attendance Breakdown
* **Enhancements:**
  * Card or table per enrolled class showing:
    * Subject Code & Title (e.g., `IT 311 — Systems Analysis & Design`)
    * Instructor Name & Room
    * Present / Late / Absent / Excused counts
    * Individual Subject Compliance Rate (e.g., `92.5%`)
* **Detailed Session Audit Log:**
  * Expandable history of every class meeting:
    * Meeting Date & Time
    * Status (`PRESENT` at 08:04 AM, `LATE` at 08:22 AM, `EXCUSED`)
    * Method: `QR Scan` vs `Manual Teacher Overridden`

---

## 3. ⚠️ CHED 20% Early-Warning Sentinel

*Current State: No risk indicators.*

### 3.1 Visual Absence Warning Progression
* In Philippine Higher Education (CHED), exceeding 20% unexcused absences of total class hours leads to **Dropped / FDA (Failure Due to Absences)**.
* **Student Sentinel Indicator:**
  * 🟢 **Good Standing (< 10% absences):** Clean green badge *"Excellent Attendance"*.
  * 🟡 **Caution (10% – 15% absences):** Amber alert *"1 more absence until official warning"*.
  * 🟠 **Warning (16% – 19% absences):** Orange warning banner with guidance advisory.
  * 🔴 **Critical (≥ 20% absences):** Red alert *"Exceeded maximum absences threshold — Contact Instructor/Dean"*.

### 3.2 Absence Excuse Request Workflow
* Allow students to submit an online excuse slip:
  * Select class session missed.
  * Upload photo of Medical Certificate or Official School Activity Form.
  * Status: `Pending Review` ➔ Teacher receives notification and can approve to `EXCUSED`.

---

## 4. 🗓️ Enrolled Classes & Weekly Timetable

### 4.1 Visual Weekly Schedule Matrix
* Clean Monday–Saturday schedule grid:
  * Color-coded class blocks showing starts_at to ends_at.
  * Displays today's upcoming class highlighted in gold with room number.
* Quick-action button: *"Today's Badge"* jumping directly to the rotating QR code.

---

## 🚀 Phased Implementation Matrix

| Phase | Milestone | Features | Estimated Effort |
|---|---|---|---|
| **Phase 1 (Initial)** | **Dynamic QR Badge & Dashboard** | Rotating TOTP QR badge (`/student/dashboard/`), 30s countdown ring, student ID badge card, KPI counters | 1 day |
| **Phase 2** | **Subject Ledger & History** | Enrolled subjects breakdown, meeting-by-meeting log, status filters | 1–2 days |
| **Phase 3** | **Retention & CHED Warning** | Visual 4-stage color progression bar, absence risk alert banners | 1 day |
| **Phase 4** | **Weekly Timetable & Schedule** | Weekly calendar grid, room guide, instructor contacts | 1–2 days |
| **Phase 5** | **Excuse Slip Ingestion** | Student medical slip photo upload, teacher review modal | 2 days |
