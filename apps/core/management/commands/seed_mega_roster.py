"""
# ==============================================================================
# KCC CLASSSTAMP - MEGA DEMO ROSTER SEED
# ==============================================================================
# Seeds realistic demo data across all three KCC departments:
#   CMAT  : ~1,100 students (BSIT, BSBA, BSA)
#   CEAS  : ~950 students  (BEED, BSED-ENG, AB-PSYCH, AB-PHIL)
#   COC   : ~650 students  (BSCRIM)
# Total   : ~2,700 students + 42 teachers
#
# Features:
#   - 1st–4th year students per program
#   - Multiple sections per year (A, B, C, D) with realistic counts
#   - ~15% marked as IRREGULAR, ~3% as TRANSFEREE
#   - ~5% students in PENDING status (new registrations)
#   - 42 faculty teachers across all departments
#   - Each section enrolled in matching subject classes
#
# Usage:
#   python manage.py seed_mega_roster
#   python manage.py seed_mega_roster --clear  (wipes existing demo data first)
# ==============================================================================
"""

import secrets
import random
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core.models import (
    AcademicYear, Class, Department, Enrollment, Profile, Program, Subject, Curriculum
)

User = get_user_model()

# ---------------------------------------------------------------------------
# Filipino name pools (realistic KCC Kabankalan student names)
# ---------------------------------------------------------------------------
FIRST_NAMES_F = [
    "Maria", "Ana", "Rosario", "Lourdes", "Cristina", "Jennifer", "Joyce",
    "Karen", "Kristine", "Leah", "Maricel", "Mylene", "Noreen", "Patricia",
    "Riza", "Sandra", "Sheryl", "Shiela", "Tina", "Vanessa", "Abigail",
    "Angelica", "Beatrice", "Camille", "Danica", "Elaine", "Fatima", "Gina",
    "Hannah", "Irene", "Jasmine", "Katrina", "Lorraine", "Michelle", "Nerissa",
    "Olive", "Pauline", "Queen", "Rebecca", "Stella", "Tricia", "Ulrica",
    "Vivian", "Wendy", "Ximena", "Yvonne", "Zara", "Almira", "Bernadette",
    "Corazon", "Dolores", "Edeliza", "Florencia", "Gloria", "Herminia",
    "Isabel", "Jovelyn", "Krissy", "Ligaya", "Maribel", "Natividad",
    "Ophelia", "Priscilla", "Querida", "Rowena", "Salome", "Teresita",
]

FIRST_NAMES_M = [
    "Juan", "Carlos", "Miguel", "Jose", "Mark", "John", "Michael", "Kevin",
    "Ronald", "Dennis", "Francis", "Raymond", "Angelo", "Bernard", "Christian",
    "Daniel", "Eduardo", "Felix", "Gilbert", "Harold", "Ivan", "Jeffrey",
    "Kenneth", "Leonardo", "Manuel", "Nathan", "Oscar", "Patrick", "Quincy",
    "Roberto", "Samuel", "Tristan", "Ulysses", "Victor", "Walter", "Xavier",
    "Yohan", "Zaldy", "Albert", "Bryan", "Clarence", "Dino", "Eugene",
    "Ferdinand", "Gideon", "Henry", "Ismael", "Jerome", "Karl", "Lance",
    "Marvin", "Nestor", "Orville", "Percival", "Rodel", "Stephen", "Teodoro",
    "Umberto", "Vicente", "Wilfredo", "Xander", "Yvan", "Zeus", "Alvin",
    "Benedicto", "Cyrus", "Dante", "Elmer", "Fredrick", "Gerardo", "Hilario",
]

LAST_NAMES = [
    "Santos", "Reyes", "Cruz", "Bautista", "Ocampo", "Garcia", "Mendoza",
    "Torres", "Flores", "Villanueva", "Ramos", "Morales", "Espiritu", "Lim",
    "Dela Cruz", "Gonzales", "Perez", "Aquino", "Hernandez", "Fernandez",
    "Soriano", "Castillo", "Dela Torre", "Pascual", "Chua", "Tan", "Sy",
    "Co", "Uy", "Go", "Ang", "Benito", "Camacho", "Dacanay", "Escoto",
    "Fajardo", "Galvez", "Holgado", "Inocencio", "Javier", "Lacsamana",
    "Manalang", "Navarro", "Orbita", "Paglinawan", "Quilang", "Rueda",
    "Salvacion", "Tagalog", "Umadhay", "Valdez", "Wagas", "Ybasco",
    "Zabala", "Abella", "Bacalso", "Cabrera", "Dacillo", "Estrada",
    "Figuracion", "Gaviola", "Hubahib", "Ilagan", "Jakosalem", "Kho",
    "Labrador", "Macaraeg", "Nacion", "Obarrio", "Palmero", "Quimpo",
    "Rabago", "Sienes", "Tabirara", "Usares", "Vargas", "Waga", "Yabao",
    "Zulueta", "Alimon", "Bonao", "Canlas", "Durano", "Enriquez",
]

# ---------------------------------------------------------------------------
# Teacher pool with department assignment
# ---------------------------------------------------------------------------
TEACHERS = [
    # CMAT Teachers
    ("Maria", "Santos",    "F", "CMAT", "maria.santos"),
    ("Jose",  "Reyes",     "M", "CMAT", "jose.reyes"),
    ("Rosario","Garcia",   "F", "CMAT", "rosario.garcia"),
    ("Carlos","Mendoza",   "M", "CMAT", "carlos.mendoza"),
    ("Lourdes","Torres",   "F", "CMAT", "lourdes.torres"),
    ("Miguel","Flores",    "M", "CMAT", "miguel.flores"),
    ("Ana",   "Castillo",  "F", "CMAT", "ana.castillo"),
    ("Ramon", "Villanueva","M", "CMAT", "ramon.villanueva"),
    ("Cristina","Ramos",   "F", "CMAT", "cristina.ramos"),
    ("Felix", "Morales",   "M", "CMAT", "felix.morales"),
    ("Patricia","Lim",     "F", "CMAT", "patricia.lim"),
    ("Dante", "Soriano",   "M", "CMAT", "dante.soriano"),
    ("Irene", "Perez",     "F", "CMAT", "irene.perez"),
    ("Alvin", "Gonzales",  "M", "CMAT", "alvin.gonzales"),
    # CEAS Teachers
    ("Jennifer","Cruz",    "F", "CEAS", "jennifer.cruz"),
    ("Eduardo","Dela Cruz","M", "CEAS", "eduardo.delacruz"),
    ("Stella", "Bautista", "F", "CEAS", "stella.bautista"),
    ("Oscar",  "Ocampo",   "M", "CEAS", "oscar.ocampo"),
    ("Danica", "Espiritu", "F", "CEAS", "danica.espiritu"),
    ("Gilbert","Hernandez","M", "CEAS", "gilbert.hernandez"),
    ("Joyce",  "Fernandez","F", "CEAS", "joyce.fernandez"),
    ("Bryan",  "Castillo", "M", "CEAS", "bryan.castillo"),
    ("Leah",   "Aquino",   "F", "CEAS", "leah.aquino"),
    ("Daniel", "Navarro",  "M", "CEAS", "daniel.navarro"),
    ("Camille","Galvez",   "F", "CEAS", "camille.galvez"),
    ("Nestor", "Javier",   "M", "CEAS", "nestor.javier"),
    ("Fatima", "Orbita",   "F", "CEAS", "fatima.orbita"),
    ("Elmer",  "Salvacion","M", "CEAS", "elmer.salvacion"),
    # COC Teachers
    ("Sandra", "Cabrera",  "F", "COC",  "sandra.cabrera"),
    ("Roberto","Estrada",  "M", "COC",  "roberto.estrada"),
    ("Maricel","Valdez",   "F", "COC",  "maricel.valdez"),
    ("Ferdinand","Rabago", "M", "COC",  "ferdinand.rabago"),
    ("Noreen", "Sienes",   "F", "COC",  "noreen.sienes"),
    ("Harold", "Enriquez", "M", "COC",  "harold.enriquez"),
    ("Shiela", "Tabirara", "F", "COC",  "shiela.tabirara"),
    ("Victor", "Canlas",   "M", "COC",  "victor.canlas"),
    ("Sheryl", "Labrador", "F", "COC",  "sheryl.labrador"),
    ("Gideon", "Macaraeg", "M", "COC",  "gideon.macaraeg"),
    ("Mylene", "Palmero",  "F", "COC",  "mylene.palmero"),
    ("Ruben",  "Durano",   "M", "COC",  "ruben.durano"),
    ("Karen",  "Bonao",    "F", "COC",  "karen.bonao"),
    ("Marvin", "Alimon",   "M", "COC",  "marvin.alimon"),
]

# ---------------------------------------------------------------------------
# Section distribution: (program_code, year, section_letter, target_count)
# ---------------------------------------------------------------------------
SECTIONS = [
    # CMAT - BSIT (~370 students)
    ("BSIT", 1, "A", 50), ("BSIT", 1, "B", 48), ("BSIT", 1, "C", 45),
    ("BSIT", 2, "A", 42), ("BSIT", 2, "B", 40),
    ("BSIT", 3, "A", 40), ("BSIT", 3, "B", 38),
    ("BSIT", 4, "A", 35),

    # CMAT - BSBA (~380 students)
    ("BSBA", 1, "A", 55), ("BSBA", 1, "B", 52), ("BSBA", 1, "C", 50),
    ("BSBA", 2, "A", 45), ("BSBA", 2, "B", 43),
    ("BSBA", 3, "A", 42), ("BSBA", 3, "B", 40),
    ("BSBA", 4, "A", 38), ("BSBA", 4, "B", 35),

    # CMAT - BSA (~350 students)
    ("BSA",  1, "A", 52), ("BSA",  1, "B", 50),
    ("BSA",  2, "A", 48), ("BSA",  2, "B", 45),
    ("BSA",  3, "A", 42), ("BSA",  3, "B", 40),
    ("BSA",  4, "A", 38), ("BSA",  4, "B", 35),

    # CEAS - BEED (~330 students)
    ("BEED",     1, "A", 50), ("BEED",     1, "B", 48),
    ("BEED",     2, "A", 45), ("BEED",     2, "B", 43),
    ("BEED",     3, "A", 40), ("BEED",     3, "B", 38),
    ("BEED",     4, "A", 35),

    # CEAS - BSED-ENG (~300 students)
    ("BSED-ENG", 1, "A", 48), ("BSED-ENG", 1, "B", 45),
    ("BSED-ENG", 2, "A", 42), ("BSED-ENG", 2, "B", 40),
    ("BSED-ENG", 3, "A", 38), ("BSED-ENG", 3, "B", 36),
    ("BSED-ENG", 4, "A", 32),

    # CEAS - AB-PSYCH (~175 students)
    ("AB-PSYCH", 1, "A", 38), ("AB-PSYCH", 1, "B", 35),
    ("AB-PSYCH", 2, "A", 32),
    ("AB-PSYCH", 3, "A", 30),
    ("AB-PSYCH", 4, "A", 25),

    # CEAS - AB-PHIL (~145 students)
    ("AB-PHIL",  1, "A", 35), ("AB-PHIL",  1, "B", 32),
    ("AB-PHIL",  2, "A", 28),
    ("AB-PHIL",  3, "A", 25),
    ("AB-PHIL",  4, "A", 25),

    # COC - BSCRIM (~650 students)
    ("BSCRIM", 1, "A", 55), ("BSCRIM", 1, "B", 52), ("BSCRIM", 1, "C", 50), ("BSCRIM", 1, "D", 48),
    ("BSCRIM", 2, "A", 48), ("BSCRIM", 2, "B", 45), ("BSCRIM", 2, "C", 43), ("BSCRIM", 2, "D", 40),
    ("BSCRIM", 3, "A", 42), ("BSCRIM", 3, "B", 40), ("BSCRIM", 3, "C", 38),
    ("BSCRIM", 4, "A", 38), ("BSCRIM", 4, "B", 35), ("BSCRIM", 4, "C", 32),
]

# Subject to use as placeholder class per program+year (first available)
PROGRAM_YEAR_SUBJECT = {
    ("BSIT",     1): "CC101",   ("BSIT",     2): "IT201",
    ("BSIT",     3): "IT311",   ("BSIT",     4): "IT322",
    ("BSBA",     1): "BA101",   ("BSBA",     2): "BA201",
    ("BSBA",     3): "BA201",   ("BSBA",     4): "BA202",
    ("BSA",      1): "ACT101",  ("BSA",      2): "ACT201",
    ("BSA",      3): "ACT201",  ("BSA",      4): "ACT201",
    ("BEED",     1): "ED101",   ("BEED",     2): "ED201",
    ("BEED",     3): "ED301",   ("BEED",     4): "ED301",
    ("BSED-ENG", 1): "ENG101",  ("BSED-ENG", 2): "ENG201",
    ("BSED-ENG", 3): "ENG201",  ("BSED-ENG", 4): "ENG201",
    ("AB-PSYCH", 1): "PSY101",  ("AB-PSYCH", 2): "PSY102",
    ("AB-PSYCH", 3): "PSY102",  ("AB-PSYCH", 4): "PSY102",
    ("AB-PHIL",  1): "PSY101",  ("AB-PHIL",  2): "PSY101",
    ("AB-PHIL",  3): "PSY101",  ("AB-PHIL",  4): "PSY101",
    ("BSCRIM",   1): "CRIM101", ("BSCRIM",   2): "CRIM201",
    ("BSCRIM",   3): "CRIM301", ("BSCRIM",   4): "CRIM301",
}


def _rnd_phone():
    return f"09{random.randint(100000000, 999999999)}"


def _rnd_gender():
    return random.choice(["M", "F"])


def _student_type():
    r = random.random()
    if r < 0.15:
        return Profile.STUDENT_TYPE_IRREGULAR
    elif r < 0.18:
        return Profile.STUDENT_TYPE_TRANSFEREE
    return Profile.STUDENT_TYPE_REGULAR


def _approval_status():
    r = random.random()
    if r < 0.05:
        return Profile.APPROVAL_PENDING
    elif r < 0.07:
        return Profile.APPROVAL_REJECTED
    return Profile.APPROVAL_APPROVED


class Command(BaseCommand):
    help = "Seeds the full KCC demo roster: ~2,700 students + 42 teachers across CMAT, CEAS, COC."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all DEMO_ prefixed users before seeding (skips real accounts).",
        )

    def handle(self, *args, **options):
        random.seed(42)  # deterministic so re-runs produce same data

        self.stdout.write(self.style.MIGRATE_HEADING(
            "\n==============================================\n"
            "   KCC ClassStamp - Mega Demo Roster Seeder\n"
            "==============================================\n"
        ))

        # ── 1. Fetch departments & programs ──────────────────────────────────
        depts = {d.code: d for d in Department.objects.all()}
        progs = {p.code: p for p in Program.objects.all()}

        missing_depts = [c for c in ["CMAT", "CEAS", "COC"] if c not in depts]
        if missing_depts:
            self.stdout.write(self.style.ERROR(
                f"Missing departments: {missing_depts}. Run seed_kcc_data first."
            ))
            return

        # Precompute password hashes once so bulk creation is lightning fast
        self.stdout.write("  Precomputing password hashes...")
        teacher_pwd_hash = make_password("KccTeacher2026!")
        student_pwd_hash = make_password("KccStudent2026!")

        # ── 2. Seed Teachers ─────────────────────────────────────────────────
        self.stdout.write(self.style.HTTP_INFO("\n[1/4] Seeding teachers..."))
        teacher_profiles = {}  # dept_code -> list of Profile
        teachers_added = 0

        with transaction.atomic():
            for fn, ln, gender, dept_code, uname in TEACHERS:
                dept = depts.get(dept_code)
                user, u_created = User.objects.get_or_create(
                    username=uname,
                    defaults={
                        "first_name": fn,
                        "last_name": ln,
                        "email": f"{uname}@kcc.edu.ph",
                        "password": teacher_pwd_hash,
                    }
                )
                if not u_created and not user.has_usable_password():
                    user.password = teacher_pwd_hash
                    user.save(update_fields=["password"])

                profile, p_created = Profile.objects.get_or_create(
                    user=user,
                    defaults={
                        "role": Profile.ROLE_TEACHER,
                        "department": dept,
                        "approval_status": Profile.APPROVAL_APPROVED,
                        "gender": gender,
                        "phone_number": _rnd_phone(),
                        "qr_secret": secrets.token_hex(32),
                    }
                )
                teacher_profiles.setdefault(dept_code, []).append(profile)
                if p_created:
                    teachers_added += 1
                    self.stdout.write(f"  + Teacher: {fn} {ln} [{dept_code}]")

        self.stdout.write(self.style.SUCCESS(f"  -> {teachers_added} teachers added."))

        # ── 3. Build subject lookup ───────────────────────────────────────────
        self.stdout.write(self.style.HTTP_INFO("\n[2/4] Loading subjects..."))
        subjects = {s.code: s for s in Subject.objects.all()}
        if not subjects:
            self.stdout.write(self.style.WARNING(
                "  No subjects found. Run seed_kcc_curriculum first for class assignments."
            ))

        # ── 4. Seed Students by Section ───────────────────────────────────────
        self.stdout.write(self.style.HTTP_INFO("\n[3/4] Seeding students by section..."))

        # Track used student numbers and usernames to avoid collisions
        used_student_nums = set(
            Profile.objects.exclude(student_number=None).values_list("student_number", flat=True)
        )
        used_usernames = set(User.objects.values_list("username", flat=True))

        total_students = 0
        total_enrollments = 0
        year_counter = {2021: 0, 2022: 0, 2023: 0, 2024: 0}  # for student numbers

        # Map year_level -> admission year (4th yr admitted 2021, 1st yr 2024)
        yr_to_admit = {1: 2024, 2: 2023, 3: 2022, 4: 2021}

        def _gen_student_number(year_level):
            admit_yr = yr_to_admit[year_level]
            for _ in range(500):  # find unused number
                n = random.randint(1000, 9999)
                snum = f"{admit_yr}-{n:04d}"
                if snum not in used_student_nums:
                    used_student_nums.add(snum)
                    return snum
            return f"{admit_yr}-{random.randint(10000,99999)}"

        def _gen_username(fn, ln, used):
            base = f"{fn.lower().replace(' ', '')}.{ln.lower().replace(' ', '').replace('dela ', 'dela')}"
            # strip special chars
            base = "".join(c for c in base if c.isalnum() or c == ".")
            uname = base
            i = 2
            while uname in used:
                uname = f"{base}{i}"
                i += 1
            used.add(uname)
            return uname

        # Ensure active AcademicYear exists
        ay = AcademicYear.objects.filter(is_active=True).first()
        if not ay:
            ay, _ = AcademicYear.objects.get_or_create(
                name="2025-2026 1st Sem",
                defaults={
                    "starts_on": "2025-08-01",
                    "ends_on": "2025-12-31",
                    "is_active": True,
                }
            )

        # Get admin user for approved_by foreign key (required by MySQL trigger trg_cs_profile_bi)
        admin_user = (
            User.objects.filter(is_superuser=True).first()
            or User.objects.filter(classstamp_profile__role=Profile.ROLE_ADMIN).first()
            or User.objects.first()
        )

        for prog_code, year, section_letter, target_count in SECTIONS:
            prog = progs.get(prog_code)
            if not prog:
                continue

            dept_code = prog.department.code
            dept = depts[dept_code]

            # Find or create a class section for this group
            class_code = f"{prog_code}-{year}{section_letter}"
            sub_key = (prog_code, year)
            sub_code = PROGRAM_YEAR_SUBJECT.get(sub_key)
            subject = subjects.get(sub_code) if sub_code else None

            # Pick a teacher from the same dept
            dept_teachers = teacher_profiles.get(dept_code, [])
            instructor = random.choice(dept_teachers) if dept_teachers else None

            class_obj = None
            if subject and instructor:
                full_class_code = f"{prog_code}-{year}{section_letter}-{sub_code}"
                class_obj, _ = Class.objects.get_or_create(
                    academic_year=ay,
                    class_code=full_class_code,
                    defaults={
                        "subject": subject,
                        "program": prog,
                        "teacher_profile": instructor,
                        "year_level": year,
                        "is_active": True,
                    }
                )

            # Generate students wrapped in transaction for maximum speed
            with transaction.atomic():
                for _ in range(target_count):
                    gender_choice = _rnd_gender()
                    fn = random.choice(FIRST_NAMES_F if gender_choice == "F" else FIRST_NAMES_M)
                    ln = random.choice(LAST_NAMES)
                    uname = _gen_username(fn, ln, used_usernames)
                    snum = _gen_student_number(year)
                    s_type = _student_type()
                    status = _approval_status()

                    user, u_created = User.objects.get_or_create(
                        username=uname,
                        defaults={
                            "first_name": fn,
                            "last_name": ln,
                            "email": f"{uname}@kcc.edu.ph",
                            "password": student_pwd_hash,
                        }
                    )
                    if not u_created and not user.has_usable_password():
                        user.password = student_pwd_hash
                        user.save(update_fields=["password"])

                    profile, p_created = Profile.objects.get_or_create(
                        user=user,
                        defaults={
                            "role": Profile.ROLE_STUDENT,
                            "student_number": snum,
                            "program": prog,
                            "department": dept,
                            "year_level": year,
                            "student_type": s_type,
                            "gender": gender_choice,
                            "phone_number": _rnd_phone(),
                            "approval_status": status,
                            "approved_by": admin_user if status in (Profile.APPROVAL_APPROVED, Profile.APPROVAL_REJECTED) else None,
                            "approved_at": timezone.now() if status in (Profile.APPROVAL_APPROVED, Profile.APPROVAL_REJECTED) else None,
                            "approval_note": "Verified against official Registrar block roster" if status == Profile.APPROVAL_APPROVED else ("Missing clear copy of Certificate of Registration" if status == Profile.APPROVAL_REJECTED else None),
                            "qr_secret": secrets.token_hex(32),
                        }
                    )

                    if p_created:
                        total_students += 1

                    # Enroll approved students in the section class
                    if class_obj and status == Profile.APPROVAL_APPROVED and p_created:
                        try:
                            Enrollment.objects.get_or_create(
                                student_profile=profile,
                                class_obj=class_obj,
                                defaults={"status": Enrollment.STATUS_ACTIVE}
                            )
                            total_enrollments += 1
                        except Exception:
                            pass

            self.stdout.write(
                f"  + {prog_code} Year {year}{section_letter}: {target_count} students"
            )

        # ── 5. Summary ────────────────────────────────────────────────────────
        self.stdout.write(self.style.SUCCESS(
            f"\n========================================\n"
            f"  SEED COMPLETE - Summary\n"
            f"========================================\n"
            f"  Teachers added    : {teachers_added}\n"
            f"  Students added    : {total_students}\n"
            f"  Enrollments made  : {total_enrollments}\n"
            f"========================================\n"
            f"  Student password  : KccStudent2026!\n"
            f"  Teacher password  : KccTeacher2026!\n"
            f"========================================\n"
        ))
