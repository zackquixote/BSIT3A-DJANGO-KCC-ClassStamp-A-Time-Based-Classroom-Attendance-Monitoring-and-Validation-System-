# KCC ClassStamp — Demo Script (Sample Demo)

**Flow na ipapakita:** Admin approves accounts → Teacher opens session → Student shows QR → Teacher scans → Attendance appears.

**Live site:** https://kccclassstamp.pythonanywhere.com/
**Target duration:** 10–12 minutes (may 5-minute buffer)
**Minimum cast:** 1 admin, 1 teacher (phone na may camera), 2–3 students (phone)

---

## 0. Bago mag-demo (gawin 30 minuto bago magsimula)

| # | Gawin | Dapat |
|---|---|---|
| 1 | Buksan ang live site sa laptop at sa phone | 200, lumalabas ang login page |
| 2 | I-check na may **account** ka sa 3 roles | Admin, Teacher, Student |
| 3 | I-check ang **class section** | May subject, teacher, academic year |
| 4 | I-check ang **roster** | May enrolled students (hindi 0) |
| 5 | Teacher phone: i-allow ang **camera** | HTTPS na site (may padlock) |
| 6 | Student phone: **brightness = high** | Para mabilis ang scan |
| 7 | Backup: **data** sa phone | Kung mahina ang Wi-Fi |

> ⚠️ **Pinaka-madalas na sablay:** walang **enrolled** na student sa section, o **walang slot para sa araw ng demo**. Tingnan ang Step 3 at ang Troubleshooting sa dulo.

---

## 1. Quem do que (roles)

| Role | Device | Gagawin |
|---|---|---|
| **Admin** | laptop | Approve students, create teacher, create class, enlist roster |
| **Teacher** | phone (camera) | Open session, scan QR, close session |
| **Student** | phone | Show QR badge |

---

## 2. Step-by-step (may oras)

### STEP 1 — Admin: approve ang students (2 min)

1. Login bilang admin → sidebar → **Account Validation**
2. Makikita ang **Pending** queue (may COR/ID preview at **Document Inspector**)
3. I-click ang student → **Approve**
4. Ulitin sa 2–3 students na kasali sa demo

**Sabihin sa panel:** "Students cannot sign in until an administrator validates their COR/ID."

---

### STEP 2 — Admin: gawin ang teacher account (1 min, kung wala pa)

1. Sidebar → **Faculty Directory** → **+ Add Faculty**
2. Fill: First Name, Last Name, **Faculty ID *** (e.g. `KCC-FAC-0142`), Email, Department, Password
3. Save → ibigay ang password sa teacher

**Sabihin sa panel:** "Faculty ID is required — teachers sign in with it, same as students use their Student ID."

---

### STEP 3 — Admin: class + roster (3 min) ← **huwag laktawan**

1. Sidebar → **Class Sections** → **+ New Class**
   - Class Code: `BSIT-3A-IT311` (o kahit anong meron kayo)
   - Subject, Teacher, Program, Year Level, Academic Year, **Grace (minutes)** = 10
2. Sa row ng class → **Class Roster** (modal)
3. **Enlist Approved Student** → piliin ang student → **Enlist**
   - Ulitin sa lahat ng demo students (o gamitin ang **Generate Student Join Code** → ipasok ng students sa **Join a Class**)

**Dapat makita:** `Enrolled Students: 3` (o kung ilan man)

> 💡 **Alternative (mas mabilis):** Generate Student Join Code → student → **Join a Class** → ilagay ang code. Pending ang enrollment kung hindi auto-approved — gamitin ang admin roster kung kailangang sigurado.

---

### STEP 4 — Teacher: open attendance session (2 min)

1. Teacher logs in (Faculty ID o email)
2. **Teacher Dashboard** → **Open Attendance Session**
3. Piliin ang class → **Open**
4. Dadalhin sa **Live Attendance Scanner** page (`/teacher/session/<id>/scan/`)
   - Makikita: **"Ready for Scans"**, roster sa gilid, camera panel

**Sabihin sa panel:** "Kung wala pang schedule ngayong araw, gumagawa ang system ng ad-hoc session para sa oras na ito — kaya puwedeng mag-demo kahit walang naka-set na timetable."

> ⚠️ Kung may lumabas na *"does not meet today"* — ang slot na pinili ay ibang araw. Iwan na walang slot (ad-hoc) o gumawa ng slot na tugma sa araw ng demo.

---

### STEP 5 — Student: show the QR (30 sec)

1. Student phone → Dashboard → **Show My QR** (o bottom nav **My QR**)
2. Nakikita: pangalan, Student ID, program, **QR code**, countdown ring (**30s** refresh)
3. Itaas ang brightness → ipakita sa teacher

**Sabihin sa panel:** "The code is a 30-second TOTP. A screenshot expires — replay is useless."

---

### STEP 6 — Teacher: scan (1 min)

1. Sa scanner page → **Start Camera** (allow permission)
2. Itutok sa QR ng student
3. Dapat lumabas agad ang **student details + timestamp** sa "Ready for Scans" panel
4. Ulitin sa ibang students

**Expected result:**

| Timing | Status |
|---|---|
| Within **grace minutes** (10) | **PRESENT** |
| After grace | **LATE** (may late minutes) |

**Sabihin sa panel:** "Server ang authority — hindi ang phone. Time window at duplicate check ay server-side."

---

### STEP 7 — Attendance appears (1 min)

Ipakita sa **tatlong** lugar:

1. **Scanner page** — roster: naging PRESENT/LATE ang student
2. **Student phone** → **Attendance** → lumalabas ang record (date, class, status, method: QR)
3. **Teacher** → **Session History** (o **Attendance Matrix**) → may record na

Tapos → **Finalize & Close Session** → makikita ang summary.

---

## 3. Optional na dagdag (kung may sobrang oras)

| Feature | Paano i-demo | Sabihin |
|---|---|---|
| **Late marker** | Ipalampas sa grace (10 min) bago i-scan | "Late is computed, not chosen" |
| **Excuse slip** | Student → Excuse Slips → file → Teacher → approve | "Absences are explained, not erased" |
| **Audit log** | Admin → Audit Log | "Every action is recorded" |
| **Anomaly indicator** | I-scan ang parehong QR nang dalawang beses mabilis | "Duplicate/replay is flagged" |
| **Manual override** | Scanner → student → override | "Teacher can correct with a reason" |
| **Bulk mark** | **Mark remaining** (may confirm) | "Camera failure fallback" |

---

## 4. Troubleshooting (exact error → fix)

| Error sa screen | Ibig sabihin | Fix |
|---|---|---|
| **"… is NOT enrolled in this class section"** | Wala sa roster | Admin → Class Roster → Enlist |
| **"This classroom attendance session is closed."** | Sarado na | Teacher → reopen session |
| **"This session is not scheduled for today…"** | Ibang araw ang slot | Gumawa ng slot na tugma sa araw ng demo |
| **"Invalid ClassStamp QR code format…"** | Hindi badge ang na-scan | Ipakita ang **My QR** page, hindi screenshot ng ibang app |
| **"Student has not activated their QR credential."** | Walang QR secret | Admin/registrar → i-activate/re-approve ang student |
| **"Too many scan attempts…"** (429) | Na-throttle | Hintayin ~1 minuto |
| **Camera hindi bumubukas** | Permission / HTTP | Allow camera; dapat **HTTPS** |
| **Blurred / ayaw mag-scan** | Brightness, layo | Brightness max, 15–25 cm ang layo, tuwid |
| **Walang lumalabas na record** | Sarado ang session o tapos na ang token | Refresh ang badge, i-scan agad |

---

## 5. Fallback kung mabagal ang internet o sira ang camera

1. **Mark remaining** → "Mark every un-scanned enrolled student as PRESENT?" → OK
2. O **manual override** sa student (PRESENT/LATE/ABSENT) — may reason
3. Ipakita na lang ang **Attendance Matrix** at **Audit Log** para may ebidensya pa rin

---

## 6. Script para sa panel (short lines)

> "KCC ClassStamp is a **time-based attendance monitoring and validation** system — support tool lang; teachers and admins keep the final decision."
>
> "Dynamic student badge: **30-second TOTP**, so a shared screenshot cannot mark someone else's attendance."
>
> "The teacher's browser camera scans; the **server** decides PRESENT/LATE using the class schedule, grace period, and duplicate/replay checks."
>
> "Every action lands in the **audit log**; admins validate accounts against the uploaded **COR/school ID** before approval."
>
> "Evaluated with **ISO/IEC 25010** (functional suitability, usability, operational reliability) via UAT."

---

## 7. Final checklist (i-print o i-screenshot)

- [ ] Live site bukas sa laptop
- [ ] Admin account gumagana
- [ ] Teacher account gumagana (Faculty ID + password)
- [ ] Class section may **slot para sa araw ng demo** (o gagamit ng ad-hoc)
- [ ] Roster may **≥3 enrolled students**
- [ ] Students **APPROVED** at may QR secret
- [ ] Student phones: login na, naka-**My QR**
- [ ] Teacher phone: naka-open ang scanner page, naka-allow ang camera
- [ ] Brightness max sa lahat ng phone
- [ ] Backup: data, at screenshot ng successful run
