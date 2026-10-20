# 📋 KCC ClassStamp — Complete System Upgrade, Change Log & Defense Notes
**System Title:** *KCC ClassStamp: A Time-Based Classroom Attendance Monitoring & Validation System*  
**Date of Upgrade:** October 19–20, 2026  
**Target Roles:** Admin Console, Registrar Validation, Security & Anomaly Monitoring  

---

## 📑 Talaan ng Nilalaman (Table of Contents)
1. [Mga Bagong Files na Ginawa (Newly Created Files)](#1-mga-bagong-files-na-ginawa-newly-created-files)
2. [Mga Files na Binago at Na-Update (Modified Files by Module)](#2-mga-files-na-binago-at-na-update-modified-files-by-module)
3. [Paliwanag sa Bawat Feature (Defense & Member Reviewer Guide)](#3-paliwanag-sa-bawat-feature-defense--member-reviewer-guide)
4. [Paano I-test at I-verify sa Browser](#4-paano-i-test-at-i-verify-sa-browser)

---

## 1. 📂 Mga Bagong Files na Ginawa (Newly Created Files)

Ito ang mga bagong files na nilikha sa codebase:

| Bagong File Path | Module / Gamit | Detalye |
| :--- | :--- | :--- |
| **`static/js/admin_dashboard.js`** | Admin Frontend JS | Dedicated modular JavaScript file para sa Admin Dashboard. Hinati sa 5 controllers: Clock, Chart.js, Live Polling, Tab Switcher, at Active Sessions Modal Drawer. |
| **`static/css/dashboard.css`** | Admin UI Styling | Dedicated CSS stylesheet para sa Admin Command Center. Naglalaman ng Obsidian Dark Glass styling at 100% Zero-Scroll desktop fit tokens. |
| **`apps/core/views/class_views.py`** | Class & Schedules Controller | Backend Django views para sa Classroom Section creation, Weekly Timetable schedule allocation, at Student Roster enlistment/withdrawal. |
| **`templates/core/admin/classes.html`** | Class Management UI | Full administrative management page para sa mga klase, schedule slots, grace periods, at student master roster. |
| **`apps/core/views/anomaly_views.py`** | Security Anomaly Controller | Backend views para sa pagsusuri ng flagged/suspicious attendance scans (adjudication actions: Mark Reviewed, Dismiss, Flag Fraud). |
| **`templates/core/admin/anomalies.html`** | Security Alerts UI | Interactive administrative portal para sa adjudication ng fraudulent check-in attempts at geolocation/time violations. |
| **`apps/core/migrations/0004_profile_student_type.py`** | Database Schema Migration | Django ORM migration na opisyal na nagdagdag ng `student_type` column (`REGULAR`, `IRREGULAR`, `TRANSFEREE`) sa `core_profile` table. |
| **`apps/core/views/session_views.py`** | Session Lifecycle & Attendance Engine | Backend controller para sa pagbukas at pagsara ng class attendance sessions, live QR scan validation (`pyotp` TOTP cryptographic verification, grace period check), at manual instructor overrides. |
| **`templates/core/teacher/scanner.html`** | Live Camera Scanner Chamber | Split-screen teacher attendance studio na may in-browser webcam/rear camera scanner (`html5-qrcode`), live countdown timer ng grace period, Web Audio API sound chimes, at real-time roster grid checkoff. |
| **`templates/core/teacher/summary.html`** | Concluded Session Roll & Report | Printable official attendance roll na may breakdown ng Present, Late, Absent, at Excused students kasama ang compliance rate %. |
| **`static/js/vendor/html5-qrcode.min.js`** | Offline QR Library Asset | Local offline vendor JavaScript bundle para sa in-browser camera scanning kahit walang aktibong internet connection. |

---

## 2. 📝 Mga Files na Binago at Na-Update (Modified Files by Module)

### A. Authentication & Student Registration
* **`apps/core/models/profile.py`**
  * Idinagdag ang `student_type` field na may choices: `REGULAR`, `IRREGULAR`, `TRANSFEREE` (default: `REGULAR`).
* **`apps/core/services/auth_service.py`**
  * In-update ang registration payload at user registration service upang i-parse, i-validate, at i-save ang `student_type` ng bagong estudyante.
* **`apps/core/views/auth_views.py`** & **`apps/core/views/helpers/auth_helpers.py`**
  * Pinalakas ang credential checking, ID picture format validation, at duplicate checks sa sign-up flow.
* **`templates/auth/register.html`**
  * Nagdagdag ng **Student Classification Dropdown** sa registration form.
  * In-upgrade ang split-screen obsidian glass design na may real-time password match at student ID validation rules.

### B. Student Directory & Masterlist
* **`apps/core/views/student_views.py`**
  * Dynamic multi-parameter filtering (Department, Degree Program, Year Level, Status, Student Type).
* **`templates/core/admin/student_directory.html`**
  * Masterlist data table na may instant debounced search bar.
  * Nagpapakita ng Student Type badge (Regular/Irregular/Transferee), program pills, at direct profile drawer inspection.

### C. Account Validation Queue (Registrar / Admin Approval Flow)
* **`templates/core/admin/validation_queue.html`**
  * Dedicated queue para sa lahat ng newly registered student accounts na naghihintay ng verification ng Registrar.
* **`templates/core/admin/validation_detail.html`**
  * Side-by-side verification drawer kung saan pwedeng i-zoom at suriin ang in-upload na Certificate of Registration (COR) / School ID ng estudyante.
  * May one-click **Approve** button at **Reject** modal na may custom rejection reason / remarks.

### D. System Audit Logs & CSV Export
* **`apps/core/views/audit_views.py`**
  * Nagdagdag ng bagong view: `admin_audit_log_export_csv`.
  * Ginagawang CSV file ang audit entries habang nirerespeto ang active filter query (actor, action event, date ranges).
* **`templates/core/admin/audit_log.html`**
  * Naglagay ng **"Export CSV"** action button sa header ng table.

### E. Academic Units & User Management (IAM Console Upgrade)
* **`apps/core/views/program_views.py`** & **`templates/core/admin/programs.html`**
  * Pamamahala ng academic programs at kurso.
* **`apps/users/views.py`**, **`apps/users/urls.py`** & **`templates/users/list.html`**
  * **Top 4-Card KPI Telemetry Grid**: Real-time counter ng Total Accounts, Students, Faculty Members, Admins & Staff, at Inactive/Suspended accounts.
  * **Role-Tailored Table Columns**:
    * *Students*: Student ID, Degree Program & Standing, Student Type, Validation Status, Account Access switch.
    * *Teachers*: Faculty ID / Username, Department affiliation, Class Load badge (bilang ng hawak na sections).
    * *Admins*: Admin Username, Privilege Level (Superuser vs Staff), Last Login timestamp.
  * **1-Click Quick Status Toggle (AJAX)**: Direct active/inactive switch sa bawat row nang walang page reload na may audit logging.
  * **Quick Password Reset Modal**: Dedicated modal para sa 1-click generation ng secure temporary password (`KCC-xxxxxxx`) na may copy-to-clipboard card o manual custom password setting.
  * **Deep Operational Shortcuts**: Quick buttons patungo sa Student Directory (`/students/`), Validation Queue (`/admin/validation/`), at Teachers Roster (`/teachers/`).
  * **Role-Filtered CSV Export**: Pag-download ng custom CSV spreadsheet base sa active tab at search filters.

### F. URL Routing & Central Registry
* **`apps/core/urls.py`** & **`apps/core/views/__init__.py`**
  * Idinagdag ang mga bagong routes:
    * `/admin/classes/` (Classes & Schedules)
    * `/admin/anomalies/` (Security Alerts & Adjudication)
    * `/admin/audit-log/export-csv/` (CSV Audit Log Download)
    * `/api/admin/activity-feed/` (Real-Time Live Attendance Stream API)

### G. Admin Command Center (Dashboard Telemetry)
* **`apps/core/views/dashboard_views.py`** & **`apps/core/views/helpers/dashboard_helpers.py`**
  * Telemetry metric computation (Pending validations, Active students, Teaching faculty, Open classroom sessions, Departments, Degree programs).
  * Attendance Compliance Rate formula: `(Present + Late) / Total Recorded Scans * 100%`.
  * Open classroom live inspection sessions data provider.
  * Real-time `/api/admin/activity-feed/` endpoint para sa live attendance polling.
* **`templates/core/admin/dashboard.html`**
  * Inalis ang ~360 lines ng inline JavaScript at ikinabit ang `admin_dashboard.js`.
  * Dynamic Philippine Standard Time (PST) live digital clock.
  * Notification Bell dropdown na may live pending counter badge.
  * Interactive Attendance Analytics Pulse (Chart.js) na may 7D, 14D, 30D presets, specific historical date picker, at Day Inspection stats ribbon.
  * Dual-tab switcher: **Approved Registrations** vs **Live Attendance Stamps**.

### H. UI, Navigation & Shell Ergonomics
* **`templates/theme/sidebar.html`**
  * Idinagdag ang navigation links para sa **Security Alerts** (may live red badge counter), **Audit Log**, at **Classes & Schedules**.
* **`static/css/sidebar.css`**
  * Kinumpak ang spacing at padding pababa sa **~588px** total height upang hindi mag-scroll ang sidebar sa desktop/laptop viewports.
* **`static/css/app.css`** & **`templates/theme/base.html`**
  * In-update ang obsidian glass base design system.
  * Naglagay ng cache-busting query parameter (`?v=20261020_fit100`) para kusang ma-update ang browser nang hindi naipit sa lumang cache.

### I. Teacher Portal, Live Session Management & QR Scanner Chamber (Phase 4 Upgrade)
* **`apps/core/views/session_views.py`** & **`apps/core/urls.py`**
  * **Session Lifecycle**: Controller para mag-launch (`teacher_session_open`), mag-monitor, at mag-conclude (`teacher_session_close`) ng klase.
  * **Cryptographic TOTP Verification API (`/api/attendance/scan/`)**: Gumagamit ng `pyotp` upang i-validate ang 30-segundong rotating token ng estudyante (may ±1 step drift tolerance).
  * **Time-Based Grace Period Engine**: Awtomatikong nagkakalkula kung `PRESENT` (pasok sa scheduled start + grace minutes) o `LATE` (+X minutes tardy).
  * **Anti-Replay & Duplicate Protection**: Hinaharang ang duplicate stamps at nagtatala ng immutable `StampAttempt` log.
  * **Auto-Absent Finalization**: Sa pag-conclude ng session, lahat ng hindi nag-scan na naka-enroll na estudyante ay awtomatikong minamarkahang `ABSENT`.
  * **Manual Instructor Override**: Binibigyang-daan ang guro na i-adjust ang status (Present, Late, Excused, Absent) na may custom excuse remarks.
* **`templates/core/teacher/scanner.html`**
  * **Live Scanner Studio**: Split-screen interface na may camera switcher (Rear vs Front camera).
  * **Web Audio API Synthesized Chimes**: Built-in audio cues (Dual-tone harmonic bell para sa Present, warm chord para sa Late, buzzer para sa error) nang hindi nangangailangan ng panlabas na MP3 files.
  * **Grace Period Countdown Timer**: Live PST timer na nagpapakita kung ilang minuto/segundo na lang bago maging tardy ang mga papasok.
  * **Live Synchronized Roster**: Real-time checklist ng mga estudyante na may instant green pulse highlight sa bawat matagumpay na scan.
* **`templates/core/teacher/summary.html`**
  * Concluded session report na may compliance percentage, time stamps, at printable matrix.
* **`templates/core/teacher/dashboard.html`**
  * Upgraded Faculty Command Center na nagpapakita ng **Today's Teaching Schedule**, one-click session launcher, at pulsing alert banner kapag may live session na bukas.

---

## 3. 🧠 Paliwanag sa Bawat Feature (Defense & Member Reviewer Guide)

Gamitin itong gabay kapag tinanong kayo ng Panel, Thesis Adviser, o mga kapwa ninyo miyembro:

### 1. Bakit Zero-Scroll ang Layout sa 100% Zoom?
* **Sagot:**  
  Sa modernong enterprise at executive command centers, ang admin ay dapat makapag-monitor sa **isang tingin lamang (single-glance visibility)**. Kapag nag-i-scroll pa ang admin para lang makita ang Logout button o ang Live Feed sa ibaba, bumabagal ang workflow. Sa bagong layout, kasya ang 100% ng components sa `100vh` sa screen.

### 2. Bakit Inilipat ang JavaScript sa Dedicated File (`admin_dashboard.js`)?
* **Sagot:**  
  Sinusunod nito ang prinsipyo ng **Separation of Concerns (SoC)**. Mas madaling i-maintain ang HTML kapag walang halong daan-daang linya ng JS script. Bukod dito, naitatabi ito ng browser sa **Cache (Browser Caching)**, kaya mas mabilis mag-load ang page sa mga susunod na pagbisita.

### 3. Paano Gumagana ang Real-Time Live Stamps?
* **Sagot:**  
  Gumagamit ito ng **Asynchronous AJAX Polling**. Bawat 30 segundo (at tuwing iki-click ng admin ang *Live Stamps* tab), palihim na nagpapadala ang JavaScript ng request sa `/api/admin/activity-feed/`. Kapag may nag-scan na estudyante sa classroom, agad lalabas ang kanyang pangalan at status sa feed nang **hindi kinakailangang i-refresh ang buong web page**.

### 4. Para saan ang Security Anomaly & Adjudication System?
* **Sagot:**  
  Ito ang depensa ng KCC ClassStamp laban sa **Attendance Fraud at Proxy Attendance** (hal. pinasa ng estudyante ang QR screenshot sa kanyang kaklase). Kapag may na-detect na duplicate tap, time mismatch, o invalid token, awtomatiko itong fina-flag bilang security anomaly. Ang Admin ay may kapangyarihang mag-imbestiga at i-flag ito bilang **Fraudulent** upang ma-void ang attendance.

### 5. Paano Kino-compute ang Daily Attendance Compliance Rate (%)?
* **Sagot:**  
  $$\text{Attendance Compliance Rate} = \left(\frac{\text{Present} + \text{Late}}{\text{Total Scanned Attendance Records Today}}\right) \times 100\%$$  
  Ipinapakita nito sa admin kung gaano kataas ang student attendance turn-out para sa kasalukuyang araw.

### 6. Bakit Mahalaga ang Audit Log CSV Export?
* **Sagot:**  
  Para sa **Institutional Compliance at Accreditation**. Lahat ng kritikal na aksyon sa system (pag-approve ng estudyante, pagbago ng grado o attendance status, pag-delete ng user) ay may permanenteng digital audit trail na pwedeng i-download bilang CSV/Excel file para sa administrative records ng paaralan.

---

### G. Teacher Dashboard & Attendance Rolls
* **`apps/core/views/helpers/dashboard_helpers.py`**
  * Naayos ang `NameError: name 'ClassSlot' is not defined` sa pamamagitan ng pag-import ng `ClassSlot` mula sa `apps.core.models`.
  * Idinagdag ang `recent_sessions` statistical query na nag-a-annotate ng `present_count`, `late_count`, `absent_count`, at `attendance_rate` para sa huling 8 concluded meetings ng guro.
  * Idinagdag ang dynamic `overall_attendance_rate` (%) computation para sa buong faculty teaching history.
* **`templates/core/teacher/dashboard.html`**
  * Idinagdag ang **"Recent Attendance Sessions & Meeting Rolls"** table na may 1-click **"View Summary Roll"** link diretso sa official printable attendance roll (`/teacher/session/<id>/summary/`).
  * Na-upgrade ang 4th KPI card patungo sa **Faculty Compliance Rate (%)** na may historical meetings count.

### H. Subject Prospectus & Faculty Teaching Load Allocation
* **`apps/core/models/academic.py` & Database Seeding**
  * Na-seed ang standard College BSIT Subjects sa buong 1st at 2nd Year (1st & 2nd Sem): `IT111`, `GE101`, `IT121`, `GE102`, `IT211`, `IT212`, `IT221`, `IT222`, kasama ang existing `IT311`.
  * Na-seed ang bagong academic term na **`2025-2026 2nd Sem`** para sa kumpletong semester offerings.
* **`apps/core/views/teacher_views.py` & `apps/core/urls.py`**
  * Idinagdag ang AJAX endpoints:
    * `teacher_assign_class_ajax` (`/teachers/<pk>/assign-class/`) para sa mabilisang pag-allocate ng subject section sa guro.
    * `teacher_unassign_class_ajax` (`/teachers/<pk>/unassign-class/<class_id>/`) na may archival safeguard.
  * Na-optimize ang `teacher_list` query gamit ang `prefetch_related('taught_classes__subject', 'taught_classes__academic_year')` upang maiwasan ang N+1 queries.
* **`templates/core/admin/teachers.html`**
  * Na-upgrade ang column patungo sa **Teaching Load & Subjects** na nagpapakita ng visual badge pills para sa bawat hawak na asignatura.
  * Idinagdag ang interactive modal na **`#teachingLoadModal`** na may 1-click Allocate Section form at real-time listahan ng hawak na mga klase ng guro.

---

## 4. 🛠️ Paano I-test at I-verify sa Browser

1. **Subukan ang Teachers Management sa Admin (`http://127.0.0.1:8000/teachers/`):**
   * Makikita sa ilalim ng **"Teaching Load & Subjects"** ang mga pill badges ng subjects na hawak ng bawat guro.
   * Para kay **Glenn Azuelo (`FAC0-01`)**: Makikita ang `IT111 (BSIT-1A-IT111)`, `IT211 (BSIT-2A-IT211)`, at `IT212 (BSIT-2B-IT212)`.
   * Pindutin ang bagong **"Manage Teaching Load"** button (`<i class="fas fa-book-bookmark"></i>`) para magdagdag o magtanggal ng subjects sa load ng guro gamit ang modal.
2. **Mag-log in bilang Glenn Azuelo (Teacher):**
   * Username / Email: `glenn@gmail.com` o `FAC0-01`
   * Password: `teacher12345`
3. **Suriin ang Glenn Azuelo Dashboard (`http://127.0.0.1:8000/dashboard/`):**
   * Makikita ang **3 assigned classes** (1 sa 1st Year, 2 sa 2nd Year).
   * Makikita ang kanyang **Today's Teaching Schedule** na may nakalaang time windows.
   * Pwedeng pindutin ang **"Open Attendance Session"** sa kahit alin sa tatlong klase upang ilunsad ang Live Scanner Chamber!
