# 👨‍🏫 KCC ClassStamp — Teacher Experience & Feature Roadmap

This document outlines the strategic enhancements, architectural vision, and quality-of-life roadmap for the **KCC ClassStamp Teacher & Faculty Portal**.

---

## 🔒 Role Separation & Scope Boundary

In KCC ClassStamp, responsibilities are strictly compartmentalized across user personas:

| Persona | Core Responsibility | Classroom & Attendance Role |
|---|---|---|
| **Admin** | Institutional Structure, Account Validation, Masterlists, Academic Years, Security Audits | **NO QR scanning, NO active session control.** Administrative oversight only. |
| **Teacher** | Class Delivery, Subject Instruction, Classroom Attendance | **Opens/closes class sessions, operates live QR camera scanner, adjudicates manual attendance overrides, monitors student attendance rates.** |
| **Student** | Academic Attendance & Schedule | **Presents dynamic TOTP QR badge**, views personal attendance records, absence warnings, and class schedules. |

> [!IMPORTANT]
> **Teacher Scope Boundary:** Teachers are the primary frontline operators of the attendance validation engine. Every second spent opening a session or troubleshooting camera scans detracts from instructional time. The improvements below focus **100% on classroom speed, ergonomic scanner UX, student risk identification, and registrar-compliant reporting**.

---

## 📌 Executive Summary

The Teacher Portal is designed around the classroom lifecycle: **Pre-Class (Schedule & Preparation) ➔ In-Class (Live QR Scanning & Overrides) ➔ Post-Class (Summary, Analytics & Institutional Reporting)**.

The enhancement roadmap is organized into **5 Core Pillars**:

1. **Classroom Live Scanner Experience & Resilience** (Zero-friction scanning, audio feedback, rapid batch processing, projector mode)
2. **Session Roster & Attendance Adjudication** (Visual attendee grid, one-click manual status toggle with audit reasons, walk-in/add-drop handling)
3. **Student Retention & Early-Warning Radar** (CHED absence threshold alerts, 3-consecutive absence alerts, chronic latecomer detection)
4. **Registrar-Compliant Export & Analytics** (Official KCC grading sheet Excel exports, date-range summaries, class section attendance heatmaps)
5. **Classroom Logistics & Substitute Workflows** (Makeup class scheduling, combined section sessions, substitute teacher delegation)

---

## 1. 📷 Live Scanner Experience & Classroom Ergonomics

*Current State: Scanner operates on `/teacher/session/<id>/scan/` with HTML5 camera input and basic JSON verification.*

### 1.1 Audio-Visual Scan Feedback & Ergonomic HUD
* **Problem:** In noisy classrooms or bright lecture halls, teachers cannot easily tell if a student's QR was successfully read without staring at small text on the screen.
* **Enhancements:**
  * **Distinct Web Audio Chimes:**
    * 🎵 High double-beep for **Present** (success)
    * 🔔 Single warm chime for **Late** (within grace window)
    * ⚠️ Low buzzing tone for **Already Scanned / Duplicate**
    * 🚨 Alert tone for **Invalid QR / Not Enrolled in this Class**
  * **Full-Screen Flash Indicator:** Subtle green/amber/red border pulse on screen so the teacher can see scan state from several feet away.
  * **Haptic Vibration:** If running on teacher's mobile/tablet browser, trigger short vibration on successful registration.

### 1.2 "Kiosk / Projector Mode" for Student Self-Scanning
* **Enhancements:**
  * Toggle **"Kiosk Mode"** that strips sidebar navigation, enlarges the camera viewfinder, and shows a privacy-respecting scan confirmation card:
    * Displays student's first name, avatar/photo thumbnail, timestamp, and status.
    * Automatically masks student number / personal details for privacy compliance.
    * Automatically hides confirmation after 2.5 seconds to ready the viewfinder for the next student.

### 1.3 Offline Camera Buffer & Network Blip Resilience
* **Problem:** Fluctuating campus Wi-Fi can stall the live scan pipeline, forcing students to wait in line.
* **Enhancements:**
  * Implement an **IndexedDB scan queue** in JavaScript.
  * If the network drops for 10–30 seconds, decoded QR tokens are queued locally with exact millisecond device timestamps.
  * As soon as connection recovers, the client silently flushes the queue to the backend `/teacher/session/<id>/scan/` endpoint with replay-attack protection.

---

## 2. 👥 Session Roster & Live Adjudication

*Current State: Teachers view a basic list of attendees after closing the session or in the summary view.*

### 2.1 Live Interactive Attendance Matrix
* **Enhancements:**
  * Real-time grid of all enrolled students directly beneath or beside the scanner viewfinder.
  * **Color-Coded Status Pills:**
    * 🟢 **Present** (Scanned on time)
    * 🟡 **Late** (Scanned within grace period)
    * 🔴 **Absent** (Unscanned / Default)
    * 🔵 **Excused** (Medical slip or official school activity)
  * Live counters in the header: `Present: 28 | Late: 4 | Absent: 3 | Total: 35 (91.4%)`.

### 2.2 Instant One-Click Manual Override
* **Problem:** If a student's phone died, screen cracked, or camera has glare, the teacher needs to mark them manually without leaving the scan flow.
* **Enhancements:**
  * Clicking any student card in the roster opens a **Quick Override Drawer**:
    * 1-click buttons: `Mark Present`, `Mark Late`, `Mark Excused`.
    * Reason dropdown: `"Phone Battery Dead"`, `"Broken Screen"`, `"Forgot ID"`, `"Medical Excuse Slip"`, `"Official College Duty"`.
    * Auto-saves via AJAX and logs to `AuditLog` with teacher user ID for accountability.

### 2.3 Guest / Walk-In & Add-Drop Student Support
* **Enhancements:**
  * For the first 2 weeks of the semester during Add/Drop period:
    * When an unregistered or recently enrolled student scans their QR, show: *"Student enrolled in Section B. Accept as Walk-In / Transferee?"*
    * Teacher can accept into current session with a single tap.

---

## 3. ⚠️ Student Retention & Early-Warning System (CHED Compliance)

*Current State: Attendance is recorded per session; aggregate danger levels are not proactively flagged to teachers.*

### 3.1 CHED 20% Absence Rule Radar
* **Institutional Rule:** Students who exceed 20% unexcused absences of the total scheduled hours are subject to Dropped / Failure Due to Absences (FDA).
* **Enhancements:**
  * **Risk Badge on Student Cards:**
    * 🟢 **Safe:** < 10% absences
    * 🟡 **Watchlist:** 10% – 19% absences
    * 🔴 **Critical (FDA Risk):** ≥ 20% absences
  * Visual warning badge appears next to student's name on the teacher's dashboard and scanner roster.

### 3.2 Consecutive Absence Sentinel
* **Enhancements:**
  * System alerts the teacher if a student misses **3 consecutive class meetings**.
  * Quick-action link: **"Generate Absence Notice"** or **"Refer to Guidance / Dean"**.

---

## 4. 📊 Analytics, Reports & Official Gradebook Export

*Current State: Session summaries are available individually, but exporting cumulative attendance across the entire term is limited.*

### 4.1 Official KCC Registrar Format Excel Export
* **Enhancements:**
  * Generate multi-tab Excel (`.xlsx`) and PDF reports formatted to match the KCC Registrar / Dean's Office requirements:
    * Columns: Student ID | Student Name | Week 1..18 Dates | Total Present | Total Late | Total Absent | % Attendance.
    * Conditional formatting highlighting students with high absence rates in red.
  * Export options:
    * **Single Session Summary** (for daily class documentation)
    * **Midterm Attendance Sheet** (Weeks 1–9)
    * **Final Term Cumulative Attendance Sheet** (Weeks 1–18)

### 4.2 Class Section Attendance Trends & Heatmaps
* **Enhancements:**
  * Day-of-week attendance trend chart (e.g., detecting if Monday morning 7:30 AM has significantly lower attendance than Wednesday).
  * Latecomer frequency analysis (identifying chronic 10-minute late arrivals).

---

## 5. 🗓️ Classroom Scheduling & Substitute Management

*Current State: Sessions must follow strict slot definitions created by Admins.*

### 5.1 Makeup / Special Session Logging
* **Enhancements:**
  * Enable teachers to schedule and open a **Special / Makeup Session** (e.g., due to typhoons, holidays, or academic events).
  * System prompts for original missed date and reason, linking the session to the class's curriculum record.

### 5.2 Temporary Substitute Teacher Handover
* **Enhancements:**
  * When a faculty member is on official leave, they or their Department Chair can assign a **Substitute Faculty Member** to a specific date/slot.
  * The substitute teacher gains session opening and scanning permissions for that class slot without altering permanent class ownership.

---

## 🚀 Phased Implementation Matrix

| Phase | Milestone | Features | Estimated Effort |
|---|---|---|---|
| **Phase 1** | **Scanner UX & Audio Polish** | Web audio chimes, full-screen HUD indicator, fast scan response, keyboard shortcuts | 1–2 days |
| **Phase 2** | **Live Roster & Overrides** | Real-time attendee grid during session, 1-click manual override modal with audit reasons | 2–3 days |
| **Phase 3** | **Registrar Excel Exports** | Term-wide attendance spreadsheet generator (`openpyxl`), single-session PDF slip | 2 days |
| **Phase 4** | **Early Warning Radar** | 20% absence threshold badges, 3-consecutive absence alerts, student profile drawer | 2 days |
| **Phase 5** | **Offline Scanner & Logistics** | IndexedDB client buffer for Wi-Fi drops, makeup session scheduler, substitute assignment | 3 days |

---

## 📂 Relevant Project Files & Endpoints

| Component | Path / Route |
|---|---|
| **Teacher Dashboard** | `apps/core/views/dashboard_views.py` ➔ `/teacher/dashboard/` |
| **Teacher Dashboard Template** | `templates/core/teacher/dashboard.html` |
| **Live Scanner View** | `apps/core/views/session_views.py` ➔ `/teacher/session/<id>/scan/` |
| **Scanner Template** | `templates/core/teacher/scanner.html` |
| **Session Summary Template** | `templates/core/teacher/summary.html` |
| **Dashboard Helpers** | `apps/core/views/helpers/dashboard_helpers.py` (`_teacher_dashboard_stats`) |
| **Audio Notification Chimes** | `static/js/core/app_audio.js` |
| **Attendance Models** | `Class`, `ClassSlot`, `ClassSession`, `AttendanceRecord`, `Enrollment` in `apps/core/models/` |
