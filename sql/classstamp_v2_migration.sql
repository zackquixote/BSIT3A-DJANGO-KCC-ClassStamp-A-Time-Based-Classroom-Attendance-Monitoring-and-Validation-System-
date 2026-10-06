-- ClassStamp AI database design v2: additive migration
-- Target: MariaDB 10.4+, database `bsitcrud`. Reuses the existing Django auth_user table.
-- Adds ClassStamp tables, triggers, and views alongside the existing application tables.
-- Existing tables and data are not dropped, renamed, or altered by this script.
--
-- EMPTY-DATABASE SETUP:
-- 1. Create the `bsitcrud` database and configure its credentials in mysite/settings.py.
-- 2. From the project root run: python manage.py migrate
--    This creates Django's required tables, including auth_user.
-- 3. Run this file against that same `bsitcrud` database.
-- This file is not a replacement for Django migrations and will fail if auth_user
-- does not exist. It adds the ClassStamp tables with their own tblcs_* names.
-- Written for MariaDB; test against a backup before applying to a live database.
-- Run with the mysql/mariadb client (the trigger section uses DELIMITER).

-- ============================================================
-- 1. ORGANISATION: department > program (course) > year level > subjects
-- ============================================================
CREATE TABLE tblcs_department (
  id         BIGINT NOT NULL AUTO_INCREMENT,
  code       VARCHAR(20)  NOT NULL,
  name       VARCHAR(150) NOT NULL,
  is_active  TINYINT(1)   NOT NULL DEFAULT 1,
  created_at DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uq_cs_department_code (code),
  UNIQUE KEY uq_cs_department_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE tblcs_program (
  id            BIGINT NOT NULL AUTO_INCREMENT,
  department_id BIGINT NOT NULL,
  code          VARCHAR(20)  NOT NULL,
  name          VARCHAR(150) NOT NULL,
  years_total   TINYINT UNSIGNED NOT NULL DEFAULT 4,
  is_active     TINYINT(1)   NOT NULL DEFAULT 1,
  created_at    DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at    DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uq_cs_program_code (code),
  KEY idx_cs_program_department (department_id),
  CONSTRAINT fk_cs_program_department FOREIGN KEY (department_id) REFERENCES tblcs_department (id) ON DELETE RESTRICT,
  CONSTRAINT chk_cs_program_years CHECK (years_total BETWEEN 1 AND 8)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE tblcs_subject (
  id          BIGINT NOT NULL AUTO_INCREMENT,
  code        VARCHAR(40)  NOT NULL,
  name        VARCHAR(150) NOT NULL,
  description TEXT NULL,
  is_active   TINYINT(1)   NOT NULL DEFAULT 1,
  created_at  DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at  DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uq_cs_subject_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Which subjects a program offers in which year level
CREATE TABLE tblcs_curriculum (
  id         BIGINT NOT NULL AUTO_INCREMENT,
  program_id BIGINT NOT NULL,
  year_level TINYINT UNSIGNED NOT NULL,
  subject_id BIGINT NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uq_cs_curriculum (program_id, year_level, subject_id),
  KEY idx_cs_curriculum_subject (subject_id),
  CONSTRAINT fk_cs_curriculum_program FOREIGN KEY (program_id) REFERENCES tblcs_program (id) ON DELETE RESTRICT,
  CONSTRAINT fk_cs_curriculum_subject FOREIGN KEY (subject_id) REFERENCES tblcs_subject (id) ON DELETE RESTRICT,
  CONSTRAINT chk_cs_curriculum_year CHECK (year_level >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE tblcs_academic_year (
  id            BIGINT NOT NULL AUTO_INCREMENT,
  name          VARCHAR(40) NOT NULL,
  starts_on     DATE NOT NULL,
  ends_on       DATE NOT NULL,
  is_active     TINYINT(1) NOT NULL DEFAULT 0,
  active_marker TINYINT(1) AS (IF(is_active = 1, 1, NULL)) PERSISTENT,
  created_at    DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at    DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uq_cs_academic_year_name (name),
  UNIQUE KEY uq_cs_academic_year_one_active (active_marker),
  CONSTRAINT chk_cs_academic_year_dates CHECK (ends_on >= starts_on)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 2. PEOPLE: one profile per auth_user, three roles
--   ADMIN   no department, program or student fields
--   TEACHER belongs to a department
--   STUDENT belongs to a program and year level, is validated by an admin,
--           and owns a secret that signs their rotating QR code
-- Teachers are deactivated with auth_user.is_active = 0, never deleted.
-- ============================================================
CREATE TABLE tblcs_profile (
  id                     BIGINT NOT NULL AUTO_INCREMENT,
  user_id                INT NOT NULL,
  role                   VARCHAR(7) NOT NULL,
  department_id          BIGINT NULL,
  program_id             BIGINT NULL,
  year_level             TINYINT UNSIGNED NULL,
  student_number         VARCHAR(50) NULL,
  approval_status        VARCHAR(8) NULL,
  approval_note          TEXT NULL,
  approved_by_id         INT NULL,
  approved_at            DATETIME(6) NULL,
  privacy_consent_at     DATETIME(6) NULL,
  privacy_notice_version VARCHAR(20) NULL,
  qr_secret              CHAR(64) NULL,
  qr_rotated_at          DATETIME(6) NULL,
  created_at             DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at             DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uq_cs_profile_user (user_id),
  UNIQUE KEY uq_cs_profile_student_number (student_number),
  KEY idx_cs_profile_role_status (role, approval_status),
  KEY idx_cs_profile_department (department_id),
  KEY idx_cs_profile_program_year (program_id, year_level),
  KEY idx_cs_profile_approver (approved_by_id),
  CONSTRAINT fk_cs_profile_user       FOREIGN KEY (user_id)        REFERENCES auth_user (id) ON DELETE CASCADE,
  CONSTRAINT fk_cs_profile_department FOREIGN KEY (department_id) REFERENCES tblcs_department (id) ON DELETE RESTRICT,
  CONSTRAINT fk_cs_profile_program    FOREIGN KEY (program_id)    REFERENCES tblcs_program (id) ON DELETE RESTRICT,
  CONSTRAINT fk_cs_profile_approver   FOREIGN KEY (approved_by_id) REFERENCES auth_user (id) ON DELETE SET NULL,
  CONSTRAINT chk_cs_profile_shape CHECK (
    (role = 'STUDENT'
       AND approval_status IN ('PENDING','APPROVED','REJECTED')
       AND student_number IS NOT NULL AND program_id IS NOT NULL AND year_level IS NOT NULL
       AND department_id IS NULL
       AND qr_secret IS NOT NULL AND CHAR_LENGTH(qr_secret) = 64)
    OR (role = 'TEACHER'
       AND department_id IS NOT NULL
       AND approval_status IS NULL AND student_number IS NULL AND program_id IS NULL
       AND year_level IS NULL AND qr_secret IS NULL)
    OR (role = 'ADMIN'
       AND department_id IS NULL
       AND approval_status IS NULL AND student_number IS NULL AND program_id IS NULL
       AND year_level IS NULL AND qr_secret IS NULL)
  )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 3. CLASSES (no sections): a class is a subject taught by one teacher in one year.
-- It can meet on several weekdays (slots). Students enroll in the class.
-- ============================================================
CREATE TABLE tblcs_class (
  id                 BIGINT NOT NULL AUTO_INCREMENT,
  academic_year_id   BIGINT NOT NULL,
  class_code         VARCHAR(40) NOT NULL,
  subject_id         BIGINT NOT NULL,
  teacher_profile_id BIGINT NOT NULL,
  capacity           INT UNSIGNED NULL,
  grace_minutes      SMALLINT UNSIGNED NOT NULL DEFAULT 10,
  is_active          TINYINT(1) NOT NULL DEFAULT 1,
  created_at         DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at         DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uq_cs_class_year_code (academic_year_id, class_code),
  KEY idx_cs_class_subject (subject_id),
  KEY idx_cs_class_teacher (teacher_profile_id, is_active),
  CONSTRAINT fk_cs_class_year    FOREIGN KEY (academic_year_id)   REFERENCES tblcs_academic_year (id) ON DELETE RESTRICT,
  CONSTRAINT fk_cs_class_subject FOREIGN KEY (subject_id)         REFERENCES tblcs_subject (id) ON DELETE RESTRICT,
  CONSTRAINT fk_cs_class_teacher FOREIGN KEY (teacher_profile_id) REFERENCES tblcs_profile (id) ON DELETE RESTRICT,
  CONSTRAINT chk_cs_class_capacity CHECK (capacity IS NULL OR capacity > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE tblcs_class_slot (
  id        BIGINT NOT NULL AUTO_INCREMENT,
  class_id  BIGINT NOT NULL,
  weekday   TINYINT UNSIGNED NOT NULL,          -- 0 = Monday ... 6 = Sunday
  starts_at TIME NOT NULL,
  ends_at   TIME NOT NULL,
  room      VARCHAR(100) NOT NULL DEFAULT '',
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uq_cs_slot (class_id, weekday, starts_at),
  KEY idx_cs_slot_day (weekday, is_active),
  CONSTRAINT fk_cs_slot_class FOREIGN KEY (class_id) REFERENCES tblcs_class (id) ON DELETE RESTRICT,
  CONSTRAINT chk_cs_slot_weekday CHECK (weekday <= 6),
  CONSTRAINT chk_cs_slot_times CHECK (ends_at > starts_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE tblcs_enrollment (
  id                 BIGINT NOT NULL AUTO_INCREMENT,
  student_profile_id BIGINT NOT NULL,
  class_id           BIGINT NOT NULL,
  status             VARCHAR(9) NOT NULL DEFAULT 'PENDING',
  starts_on          DATE NULL,
  ends_on            DATE NULL,
  approved_by_id     INT NULL,
  approved_at        DATETIME(6) NULL,
  created_at         DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at         DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uq_cs_enroll_student_class (student_profile_id, class_id),
  KEY idx_cs_enroll_class_status (class_id, status),
  KEY idx_cs_enroll_approver (approved_by_id),
  CONSTRAINT fk_cs_enroll_student  FOREIGN KEY (student_profile_id) REFERENCES tblcs_profile (id) ON DELETE RESTRICT,
  CONSTRAINT fk_cs_enroll_class    FOREIGN KEY (class_id)           REFERENCES tblcs_class (id) ON DELETE RESTRICT,
  CONSTRAINT fk_cs_enroll_approver FOREIGN KEY (approved_by_id)     REFERENCES auth_user (id) ON DELETE SET NULL,
  CONSTRAINT chk_cs_enroll_status CHECK (status IN ('PENDING','ACTIVE','COMPLETED','WITHDRAWN')),
  CONSTRAINT chk_cs_enroll_dates CHECK (ends_on IS NULL OR starts_on IS NULL OR ends_on >= starts_on)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 4. ATTENDANCE
-- ============================================================
CREATE TABLE tblcs_class_session (
  id                  BIGINT NOT NULL AUTO_INCREMENT,
  slot_id             BIGINT NOT NULL,
  session_date        DATE NOT NULL,
  status              VARCHAR(9) NOT NULL DEFAULT 'SCHEDULED',
  opened_at           DATETIME(6) NULL,
  closed_at           DATETIME(6) NULL,
  created_by_id       INT NULL,
  opened_by_id        INT NULL,
  closed_by_id        INT NULL,
  auto_closed         TINYINT(1) NOT NULL DEFAULT 0,
  cancellation_reason TEXT NULL,
  created_at          DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at          DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uq_cs_session_slot_date (slot_id, session_date),
  KEY idx_cs_session_date_status (session_date, status),
  KEY idx_cs_session_closer (closed_by_id),
  CONSTRAINT fk_cs_session_slot   FOREIGN KEY (slot_id)      REFERENCES tblcs_class_slot (id) ON DELETE RESTRICT,
  CONSTRAINT fk_cs_session_closer FOREIGN KEY (closed_by_id) REFERENCES auth_user (id) ON DELETE SET NULL,
  CONSTRAINT chk_cs_session_status CHECK (status IN ('SCHEDULED','OPEN','CLOSED','CANCELED')),
  CONSTRAINT chk_cs_session_times CHECK (closed_at IS NULL OR opened_at IS NULL OR closed_at >= opened_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- One result per student per session.
-- method QR/CODE = the teacher scanned the student's QR or typed their code (marked_by = that teacher).
-- method MANUAL  = teacher or admin set it by hand.   method SYSTEM = created when the class closed.
CREATE TABLE tblcs_attendance_record (
  id                 BIGINT NOT NULL AUTO_INCREMENT,
  session_id         BIGINT NOT NULL,
  student_profile_id BIGINT NOT NULL,
  status             VARCHAR(8) NOT NULL,
  method             VARCHAR(6) NOT NULL,
  stamped_at         DATETIME(6) NULL,
  late_minutes       SMALLINT UNSIGNED NOT NULL DEFAULT 0,
  correction_reason  TEXT NULL,
  marked_by_id       INT NULL,
  created_at         DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at         DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uq_cs_attendance_session_student (session_id, student_profile_id),
  KEY idx_cs_att_student_time (student_profile_id, stamped_at),
  KEY idx_cs_att_session_status (session_id, status),
  KEY idx_cs_att_marker (marked_by_id),
  CONSTRAINT fk_cs_att_session FOREIGN KEY (session_id)         REFERENCES tblcs_class_session (id) ON DELETE RESTRICT,
  CONSTRAINT fk_cs_att_student FOREIGN KEY (student_profile_id) REFERENCES tblcs_profile (id) ON DELETE RESTRICT,
  CONSTRAINT fk_cs_att_marker  FOREIGN KEY (marked_by_id)       REFERENCES auth_user (id) ON DELETE RESTRICT,
  CONSTRAINT chk_cs_att_status CHECK (status IN ('PRESENT','LATE','ABSENT','EXCUSED')),
  CONSTRAINT chk_cs_att_method CHECK (method IN ('QR','CODE','MANUAL','SYSTEM')),
  CONSTRAINT chk_cs_att_stamp_state CHECK (
    (status IN ('PRESENT','LATE') AND stamped_at IS NOT NULL)
    OR (status = 'ABSENT' AND stamped_at IS NULL)
    OR status = 'EXCUSED'
  ),
  CONSTRAINT chk_cs_att_marker_rule CHECK (
    (method = 'SYSTEM' AND marked_by_id IS NULL)
    OR (method <> 'SYSTEM' AND marked_by_id IS NOT NULL)
  ),
  CONSTRAINT chk_cs_att_late_minutes CHECK (
    (status = 'LATE' AND late_minutes > 0)
    OR (status <> 'LATE' AND late_minutes = 0)
  )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Every scan or typed code, accepted or not. scanned_by = the teacher, student = the person scanned.
CREATE TABLE tblcs_stamp_attempt (
  id                 BIGINT NOT NULL AUTO_INCREMENT,
  session_id         BIGINT NULL,
  student_profile_id BIGINT NULL,
  scanned_by_id      INT NULL,
  attempted_at       DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  method             VARCHAR(4) NOT NULL,
  outcome            VARCHAR(14) NOT NULL,
  token_bucket       BIGINT NULL,
  token_age_s        SMALLINT UNSIGNED NULL,
  PRIMARY KEY (id),
  KEY idx_cs_attempt_session_time (session_id, attempted_at),
  KEY idx_cs_attempt_student_time (student_profile_id, attempted_at),
  KEY idx_cs_attempt_scanner_time (scanned_by_id, attempted_at),
  KEY idx_cs_attempt_outcome_time (outcome, attempted_at),
  CONSTRAINT fk_cs_attempt_session FOREIGN KEY (session_id)         REFERENCES tblcs_class_session (id) ON DELETE SET NULL,
  CONSTRAINT fk_cs_attempt_student FOREIGN KEY (student_profile_id) REFERENCES tblcs_profile (id) ON DELETE SET NULL,
  CONSTRAINT fk_cs_attempt_scanner FOREIGN KEY (scanned_by_id)      REFERENCES auth_user (id) ON DELETE SET NULL,
  CONSTRAINT chk_cs_attempt_method CHECK (method IN ('QR','CODE')),
  CONSTRAINT chk_cs_attempt_outcome CHECK (outcome IN ('ACCEPTED','INVALID','EXPIRED','DUPLICATE','INELIGIBLE','SESSION_CLOSED'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 5. REVIEW AND AUDIT
-- ============================================================
CREATE TABLE tblcs_anomaly_flag (
  id                   BIGINT NOT NULL AUTO_INCREMENT,
  attendance_record_id BIGINT NOT NULL,
  rule_code            VARCHAR(50) NOT NULL,
  reason               TEXT NOT NULL,
  risk_score           DECIMAL(5,4) NULL,
  status               VARCHAR(9) NOT NULL DEFAULT 'OPEN',
  created_at           DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  resolved_at          DATETIME(6) NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_cs_flag_record_rule (attendance_record_id, rule_code),
  KEY idx_cs_flag_status_time (status, created_at),
  CONSTRAINT fk_cs_flag_attendance FOREIGN KEY (attendance_record_id) REFERENCES tblcs_attendance_record (id) ON DELETE RESTRICT,
  CONSTRAINT chk_cs_flag_risk CHECK (risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 1)),
  CONSTRAINT chk_cs_flag_status CHECK (status IN ('OPEN','DISMISSED','CONFIRMED','EXCUSED'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE tblcs_review_action (
  id             BIGINT NOT NULL AUTO_INCREMENT,
  anomaly_flag_id BIGINT NOT NULL,
  reviewer_id    INT NOT NULL,
  decision       VARCHAR(14) NOT NULL,
  reason         TEXT NOT NULL,
  created_at     DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  KEY idx_cs_review_flag_time (anomaly_flag_id, created_at),
  KEY idx_cs_review_reviewer_time (reviewer_id, created_at),
  CONSTRAINT fk_cs_review_flag     FOREIGN KEY (anomaly_flag_id) REFERENCES tblcs_anomaly_flag (id) ON DELETE RESTRICT,
  CONSTRAINT fk_cs_review_reviewer FOREIGN KEY (reviewer_id)     REFERENCES auth_user (id) ON DELETE RESTRICT,
  CONSTRAINT chk_cs_review_decision CHECK (decision IN ('DISMISS','CONFIRM_PROXY','EXCUSE','OTHER'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE tblcs_audit_event (
  id          BIGINT NOT NULL AUTO_INCREMENT,
  actor_id    INT NULL,
  action      VARCHAR(80) NOT NULL,
  object_type VARCHAR(80) NOT NULL,
  object_id   VARCHAR(80) NULL,
  old_value   TEXT NULL,
  new_value   TEXT NULL,
  reason      TEXT NULL,
  created_at  DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  KEY idx_cs_audit_object_time (object_type, object_id, created_at),
  KEY idx_cs_audit_actor_time (actor_id, created_at),
  KEY idx_cs_audit_action_time (action, created_at),
  CONSTRAINT fk_cs_audit_actor FOREIGN KEY (actor_id) REFERENCES auth_user (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 6. INTEGRITY TRIGGERS
-- ============================================================
DELIMITER $$

-- 6.1 Curriculum year must exist in the program
CREATE OR REPLACE TRIGGER trg_cs_curriculum_bi BEFORE INSERT ON tblcs_curriculum
FOR EACH ROW
BEGIN
  DECLARE v_years TINYINT UNSIGNED;
  SELECT years_total INTO v_years FROM tblcs_program WHERE id = NEW.program_id;
  IF v_years IS NULL OR NEW.year_level > v_years THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Year level is beyond the program length';
  END IF;
END$$

CREATE OR REPLACE TRIGGER trg_cs_curriculum_bu BEFORE UPDATE ON tblcs_curriculum
FOR EACH ROW
BEGIN
  DECLARE v_years TINYINT UNSIGNED;
  SELECT years_total INTO v_years FROM tblcs_program WHERE id = NEW.program_id;
  IF v_years IS NULL OR NEW.year_level > v_years THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Year level is beyond the program length';
  END IF;
END$$

-- 6.2 Profile: year level fits the program; registration must be validated by an admin
CREATE OR REPLACE TRIGGER trg_cs_profile_bi BEFORE INSERT ON tblcs_profile
FOR EACH ROW
BEGIN
  DECLARE v_years TINYINT UNSIGNED;
  IF NEW.role = 'STUDENT' THEN
    SELECT years_total INTO v_years FROM tblcs_program WHERE id = NEW.program_id;
    IF v_years IS NULL OR NEW.year_level < 1 OR NEW.year_level > v_years THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Year level does not fit the selected program';
    END IF;
    IF NEW.approval_status <> 'PENDING' AND NEW.approved_by_id IS NULL THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Only an admin can create an approved or rejected student';
    END IF;
  END IF;
END$$

CREATE OR REPLACE TRIGGER trg_cs_profile_bu BEFORE UPDATE ON tblcs_profile
FOR EACH ROW
BEGIN
  DECLARE v_years TINYINT UNSIGNED;
  DECLARE v_approver_role VARCHAR(7);
  IF OLD.role <> NEW.role THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'A profile role cannot be changed';
  END IF;
  IF NEW.role = 'STUDENT' THEN
    SELECT years_total INTO v_years FROM tblcs_program WHERE id = NEW.program_id;
    IF v_years IS NULL OR NEW.year_level < 1 OR NEW.year_level > v_years THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Year level does not fit the selected program';
    END IF;
    IF OLD.approval_status <> NEW.approval_status
       AND NEW.approval_status IN ('APPROVED','REJECTED') THEN
      IF NEW.approved_by_id IS NULL OR NEW.approved_at IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'A decision needs the approving admin and time';
      END IF;
      SELECT role INTO v_approver_role FROM tblcs_profile WHERE user_id = NEW.approved_by_id;
      IF v_approver_role IS NULL OR v_approver_role <> 'ADMIN' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Only an admin can validate a registration';
      END IF;
      IF NEW.approval_status = 'REJECTED' AND (NEW.approval_note IS NULL OR NEW.approval_note = '') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'A rejection needs a reason';
      END IF;
    END IF;
  END IF;
END$$

-- 6.3 Class: teacher must have the TEACHER role
CREATE OR REPLACE TRIGGER trg_cs_class_bi BEFORE INSERT ON tblcs_class
FOR EACH ROW
BEGIN
  DECLARE v_role VARCHAR(7);
  SELECT role INTO v_role FROM tblcs_profile WHERE id = NEW.teacher_profile_id;
  IF v_role IS NULL OR v_role <> 'TEACHER' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Class teacher must have the TEACHER role';
  END IF;
END$$

CREATE OR REPLACE TRIGGER trg_cs_class_bu BEFORE UPDATE ON tblcs_class
FOR EACH ROW
BEGIN
  DECLARE v_role VARCHAR(7);
  SELECT role INTO v_role FROM tblcs_profile WHERE id = NEW.teacher_profile_id;
  IF v_role IS NULL OR v_role <> 'TEACHER' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Class teacher must have the TEACHER role';
  END IF;
END$$

-- 6.4 Slot: no overlap for the same teacher or room within one academic year
CREATE OR REPLACE TRIGGER trg_cs_slot_bi BEFORE INSERT ON tblcs_class_slot
FOR EACH ROW
BEGIN
  DECLARE v_year BIGINT;
  DECLARE v_teacher BIGINT;
  SELECT academic_year_id, teacher_profile_id INTO v_year, v_teacher
    FROM tblcs_class WHERE id = NEW.class_id;
  IF NEW.is_active = 1 AND EXISTS (
    SELECT 1 FROM tblcs_class_slot x JOIN tblcs_class cx ON cx.id = x.class_id
    WHERE x.is_active = 1 AND x.weekday = NEW.weekday
      AND x.starts_at < NEW.ends_at AND x.ends_at > NEW.starts_at
      AND cx.academic_year_id = v_year
      AND (cx.teacher_profile_id = v_teacher OR (NEW.room <> '' AND x.room = NEW.room))
  ) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Slot overlaps another class for this teacher or room';
  END IF;
END$$

CREATE OR REPLACE TRIGGER trg_cs_slot_bu BEFORE UPDATE ON tblcs_class_slot
FOR EACH ROW
BEGIN
  DECLARE v_year BIGINT;
  DECLARE v_teacher BIGINT;
  SELECT academic_year_id, teacher_profile_id INTO v_year, v_teacher
    FROM tblcs_class WHERE id = NEW.class_id;
  IF NEW.is_active = 1 AND EXISTS (
    SELECT 1 FROM tblcs_class_slot x JOIN tblcs_class cx ON cx.id = x.class_id
    WHERE x.id <> NEW.id AND x.is_active = 1 AND x.weekday = NEW.weekday
      AND x.starts_at < NEW.ends_at AND x.ends_at > NEW.starts_at
      AND cx.academic_year_id = v_year
      AND (cx.teacher_profile_id = v_teacher OR (NEW.room <> '' AND x.room = NEW.room))
  ) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Slot overlaps another class for this teacher or room';
  END IF;
END$$

-- 6.5 Enrollment: students only; only approved students become ACTIVE; class capacity
CREATE OR REPLACE TRIGGER trg_cs_enrollment_bi BEFORE INSERT ON tblcs_enrollment
FOR EACH ROW
BEGIN
  DECLARE v_role VARCHAR(7);
  DECLARE v_appr VARCHAR(8);
  DECLARE v_cap INT UNSIGNED;
  DECLARE v_cnt INT;
  SELECT role, approval_status INTO v_role, v_appr FROM tblcs_profile WHERE id = NEW.student_profile_id;
  IF v_role IS NULL OR v_role <> 'STUDENT' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Only student profiles can be enrolled';
  END IF;
  IF NEW.status = 'ACTIVE' THEN
    IF v_appr <> 'APPROVED' THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Only approved students can be actively enrolled';
    END IF;
    SELECT capacity INTO v_cap FROM tblcs_class WHERE id = NEW.class_id;
    IF v_cap IS NOT NULL THEN
      SELECT COUNT(*) INTO v_cnt FROM tblcs_enrollment WHERE class_id = NEW.class_id AND status = 'ACTIVE';
      IF v_cnt >= v_cap THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Class is at capacity';
      END IF;
    END IF;
  END IF;
END$$

CREATE OR REPLACE TRIGGER trg_cs_enrollment_bu BEFORE UPDATE ON tblcs_enrollment
FOR EACH ROW
BEGIN
  DECLARE v_appr VARCHAR(8);
  DECLARE v_cap INT UNSIGNED;
  DECLARE v_cnt INT;
  IF NEW.status = 'ACTIVE' AND (OLD.status <> 'ACTIVE' OR OLD.class_id <> NEW.class_id) THEN
    SELECT approval_status INTO v_appr FROM tblcs_profile WHERE id = NEW.student_profile_id;
    IF v_appr <> 'APPROVED' THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Only approved students can be actively enrolled';
    END IF;
    SELECT capacity INTO v_cap FROM tblcs_class WHERE id = NEW.class_id;
    IF v_cap IS NOT NULL THEN
      SELECT COUNT(*) INTO v_cnt FROM tblcs_enrollment
        WHERE class_id = NEW.class_id AND status = 'ACTIVE' AND id <> NEW.id;
      IF v_cnt >= v_cap THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Class is at capacity';
      END IF;
    END IF;
  END IF;
END$$

-- 6.6 Session: date matches the slot's weekday; status changes follow the lifecycle
CREATE OR REPLACE TRIGGER trg_cs_session_bi BEFORE INSERT ON tblcs_class_session
FOR EACH ROW
BEGIN
  DECLARE v_weekday TINYINT UNSIGNED;
  SELECT weekday INTO v_weekday FROM tblcs_class_slot WHERE id = NEW.slot_id;
  IF v_weekday IS NULL OR WEEKDAY(NEW.session_date) <> v_weekday THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Session date does not match the slot weekday';
  END IF;
END$$

CREATE OR REPLACE TRIGGER trg_cs_session_bu BEFORE UPDATE ON tblcs_class_session
FOR EACH ROW
BEGIN
  IF OLD.status <> NEW.status THEN
    IF NOT (
      (OLD.status = 'SCHEDULED' AND NEW.status IN ('OPEN','CANCELED'))
      OR (OLD.status = 'OPEN' AND NEW.status IN ('CLOSED','CANCELED'))
    ) THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Invalid class session status change';
    END IF;
  END IF;
  IF NEW.status = 'CANCELED' AND (NEW.cancellation_reason IS NULL OR NEW.cancellation_reason = '') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'A cancellation reason is required';
  END IF;
END$$

-- 6.7 Attendance:
--   * the person marked is an enrolled student
--   * QR/CODE only while the session is OPEN
--   * only the class teacher or an admin can mark (so teachers cannot stamp other teachers' classes)
CREATE OR REPLACE TRIGGER trg_cs_attendance_bi BEFORE INSERT ON tblcs_attendance_record
FOR EACH ROW
BEGIN
  DECLARE v_status VARCHAR(9);
  DECLARE v_date DATE;
  DECLARE v_class BIGINT;
  DECLARE v_teacher BIGINT;
  DECLARE v_srole VARCHAR(7);
  DECLARE v_mprofile BIGINT;
  DECLARE v_mrole VARCHAR(7);

  SELECT s.status, s.session_date, sl.class_id, c.teacher_profile_id
    INTO v_status, v_date, v_class, v_teacher
  FROM tblcs_class_session s
  JOIN tblcs_class_slot sl ON sl.id = s.slot_id
  JOIN tblcs_class c ON c.id = sl.class_id
  WHERE s.id = NEW.session_id;

  SELECT role INTO v_srole FROM tblcs_profile WHERE id = NEW.student_profile_id;
  IF v_srole IS NULL OR v_srole <> 'STUDENT' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Attendance is only recorded for student profiles';
  END IF;
  IF v_status = 'CANCELED' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Cannot record attendance for a canceled session';
  END IF;
  IF NEW.method IN ('QR','CODE') AND v_status <> 'OPEN' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Class session is not open for stamping';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM tblcs_enrollment e
    WHERE e.student_profile_id = NEW.student_profile_id
      AND e.class_id = v_class
      AND e.status = 'ACTIVE'
      AND (e.starts_on IS NULL OR e.starts_on <= v_date)
      AND (e.ends_on IS NULL OR e.ends_on >= v_date)
  ) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Student is not actively enrolled in this class';
  END IF;

  IF NEW.method <> 'SYSTEM' THEN
    SELECT id, role INTO v_mprofile, v_mrole FROM tblcs_profile WHERE user_id = NEW.marked_by_id;
    IF v_mrole IS NULL OR NOT (v_mrole = 'ADMIN' OR (v_mrole = 'TEACHER' AND v_mprofile = v_teacher)) THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Only the class teacher or an admin can mark attendance';
    END IF;
  END IF;
END$$

-- 6.8 Append-only history
CREATE OR REPLACE TRIGGER trg_cs_audit_bu BEFORE UPDATE ON tblcs_audit_event
FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Audit events are append-only'$$
CREATE OR REPLACE TRIGGER trg_cs_audit_bd BEFORE DELETE ON tblcs_audit_event
FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Audit events are append-only'$$
CREATE OR REPLACE TRIGGER trg_cs_review_bu BEFORE UPDATE ON tblcs_review_action
FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Review actions are append-only'$$
CREATE OR REPLACE TRIGGER trg_cs_review_bd BEFORE DELETE ON tblcs_review_action
FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Review actions are append-only'$$

DELIMITER ;

-- ============================================================
-- 7. VIEWS
-- Student screens must always filter by the signed-in student's profile id.
-- Reports count only CLOSED sessions; canceled and never-opened sessions are excluded.
-- attendance_rate = (present + late + excused) / counted sessions.
-- ============================================================

-- Admin: registrations waiting for validation
CREATE OR REPLACE VIEW vw_cs_pending_students AS
SELECT p.id AS profile_id, u.first_name, u.last_name, u.email,
       p.student_number, d.name AS department, pr.name AS program, p.year_level,
       p.privacy_consent_at, p.created_at
FROM tblcs_profile p
JOIN auth_user u ON u.id = p.user_id
JOIN tblcs_program pr ON pr.id = p.program_id
JOIN tblcs_department d ON d.id = pr.department_id
WHERE p.role = 'STUDENT' AND p.approval_status = 'PENDING';

-- Student: classes they could enroll in this year (their program and year level)
CREATE OR REPLACE VIEW vw_cs_eligible_classes AS
SELECT p.id AS student_profile_id, c.id AS class_id, c.class_code,
       sub.code AS subject_code, sub.name AS subject_name,
       c.teacher_profile_id, c.capacity
FROM tblcs_profile p
JOIN tblcs_curriculum cu ON cu.program_id = p.program_id AND cu.year_level = p.year_level
JOIN tblcs_class c ON c.subject_id = cu.subject_id AND c.is_active = 1
JOIN tblcs_academic_year ay ON ay.id = c.academic_year_id AND ay.is_active = 1
JOIN tblcs_subject sub ON sub.id = c.subject_id
WHERE p.role = 'STUDENT' AND p.approval_status = 'APPROVED';

-- Student: each attendance line
CREATE OR REPLACE VIEW vw_cs_student_attendance_detail AS
SELECT r.student_profile_id, c.id AS class_id, c.class_code,
       sub.code AS subject_code, sub.name AS subject_name,
       s.session_date, sl.starts_at, sl.ends_at,
       r.status, r.method, r.stamped_at, r.late_minutes, s.status AS session_status
FROM tblcs_attendance_record r
JOIN tblcs_class_session s ON s.id = r.session_id
JOIN tblcs_class_slot sl ON sl.id = s.slot_id
JOIN tblcs_class c ON c.id = sl.class_id
JOIN tblcs_subject sub ON sub.id = c.subject_id;

-- Student and teacher: totals per student per class
CREATE OR REPLACE VIEW vw_cs_student_attendance AS
SELECT r.student_profile_id, c.id AS class_id, c.class_code, c.subject_id,
       COUNT(*) AS sessions_counted,
       SUM(r.status = 'PRESENT') AS present_count,
       SUM(r.status = 'LATE')    AS late_count,
       SUM(r.status = 'EXCUSED') AS excused_count,
       SUM(r.status = 'ABSENT')  AS absent_count,
       ROUND(100 * SUM(r.status IN ('PRESENT','LATE','EXCUSED')) / COUNT(*), 2) AS attendance_rate
FROM tblcs_attendance_record r
JOIN tblcs_class_session s ON s.id = r.session_id AND s.status = 'CLOSED'
JOIN tblcs_class_slot sl ON sl.id = s.slot_id
JOIN tblcs_class c ON c.id = sl.class_id
GROUP BY r.student_profile_id, c.id, c.class_code, c.subject_id;

-- Teacher: counts per session
CREATE OR REPLACE VIEW vw_cs_session_summary AS
SELECT s.id AS session_id, s.session_date, s.status, sl.class_id,
       SUM(r.status = 'PRESENT') AS present_count,
       SUM(r.status = 'LATE')    AS late_count,
       SUM(r.status = 'EXCUSED') AS excused_count,
       SUM(r.status = 'ABSENT')  AS absent_count
FROM tblcs_class_session s
JOIN tblcs_class_slot sl ON sl.id = s.slot_id
LEFT JOIN tblcs_attendance_record r ON r.session_id = s.id
GROUP BY s.id, s.session_date, s.status, sl.class_id;

-- Teacher and admin: flags waiting for review
CREATE OR REPLACE VIEW vw_cs_open_flags AS
SELECT f.id AS flag_id, f.rule_code, f.risk_score, f.reason, f.created_at,
       r.id AS attendance_record_id, r.session_id, r.student_profile_id
FROM tblcs_anomaly_flag f
JOIN tblcs_attendance_record r ON r.id = f.attendance_record_id
WHERE f.status = 'OPEN';

-- ============================================================
-- 8. RETENTION (run weekly)
-- ============================================================
-- DELETE FROM tblcs_stamp_attempt WHERE attempted_at < NOW() - INTERVAL 120 DAY;
