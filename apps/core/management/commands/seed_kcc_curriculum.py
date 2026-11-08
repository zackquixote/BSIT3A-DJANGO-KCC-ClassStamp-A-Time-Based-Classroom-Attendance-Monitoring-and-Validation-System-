"""
Management command to seed realistic curriculum matrix and subjects
for the three KCC college departments: CMAT, CEAS, and COC.
"""

from datetime import date

from django.core.management.base import BaseCommand
from apps.core.models import (
    AcademicYear, Department, Program, Subject, Curriculum, CurriculumVersion,
)
from apps.core.services.curriculum_version_service import (
    approve_curriculum_draft,
    create_curriculum_draft,
    current_draft_version,
    latest_curriculum_version,
)


class Command(BaseCommand):
    help = "Seeds comprehensive curriculum matrix mappings for CMAT, CEAS, and COC departments."

    def add_arguments(self, parser):
        parser.add_argument(
            '--batches', nargs='*', type=int, default=None, metavar='YEAR',
            help="Opt-in: also create an entering-batch prospectus version for each "
                 "school year given (e.g. --batches 2024 2025). Each batch clones the "
                 "approved curriculum and is approved effective its own entering term.",
        )
        parser.add_argument(
            '--programs', nargs='*', default=None, metavar='CODE',
            help="Limit --batches to these program codes (default: all seeded programs).",
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help="With --batches: report what would be created without writing anything.",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== Seeding KCC Curriculum Matrix for CMAT, CEAS, and COC ==="))

        # Ensure departments exist
        dept_cmat, _ = Department.objects.get_or_create(
            code="CMAT",
            defaults={"name": "College of Management, Accountancy, and Technology", "is_active": True}
        )
        dept_ceas, _ = Department.objects.get_or_create(
            code="CEAS",
            defaults={"name": "College of Education, Arts, and Sciences", "is_active": True}
        )
        dept_coc, _ = Department.objects.get_or_create(
            code="COC",
            defaults={"name": "College of Criminology", "is_active": True}
        )

        # Ensure primary programs exist
        programs_meta = [
            ("BSIT", "Bachelor of Science in Information Technology", dept_cmat),
            ("BSBA", "Bachelor of Science in Business Administration", dept_cmat),
            ("BSA", "Bachelor of Science in Accountancy", dept_cmat),
            ("BEED", "Bachelor of Elementary Education", dept_ceas),
            ("BSED-ENG", "Bachelor of Secondary Education major in English", dept_ceas),
            ("AB-PSYCH", "Bachelor of Arts in Psychology", dept_ceas),
            ("BSCRIM", "Bachelor of Science in Criminology", dept_coc),
        ]

        programs = {}
        for code, name, dept in programs_meta:
            prog, _ = Program.objects.get_or_create(
                code=code,
                defaults={"name": name, "department": dept, "years_total": 4, "is_active": True}
            )
            programs[code] = prog

        # Curriculum Data definition: (ProgCode, Year, Semester, SubjectCode, SubjectTitle, Units, Description)
        curriculum_dataset = [
            # ─────────────────────────────────────────────────────────────
            # 1. CMAT — BSIT (Information Technology - Official KCC Curriculum)
            # ─────────────────────────────────────────────────────────────
            # 1st Year - 1st Semester (25 units, 9 subjects)
            ("BSIT", 1, 1, "GE 4", "Mathematics in the Modern World", 3, "Core General Education mathematics and problem solving."),
            ("BSIT", 1, 1, "GE 3", "The Contemporary World", 3, "Globalization, international relations, and contemporary issues."),
            ("BSIT", 1, 1, "GE 2", "Readings in Philippine History", 3, "Critical analysis of primary sources in Philippine history."),
            ("BSIT", 1, 1, "PATHfit 1", "Movement Competency Training", 2, "Physical Activities Toward Health and Fitness 1: Movement Competency Training."),
            ("BSIT", 1, 1, "CC 101", "Introduction to Computing", 3, "Fundamental concepts of computer architecture, software, and digital literacy."),
            ("BSIT", 1, 1, "CC 102", "Computer Programming 1", 3, "Fundamentals of problem solving, logic, and programming constructs."),
            ("BSIT", 1, 1, "ACCT 1", "Principles of Accounting", 3, "Basic accounting principles and financial recording."),
            ("BSIT", 1, 1, "GE 1", "Understanding the Self", 3, "Exploration of issues and concerns concerning self and personal identity."),
            ("BSIT", 1, 1, "Theology 1", "Revelation and Faith", 2, "Christian foundation, biblical revelation, and doctrinal understanding."),

            # 1st Year - 2nd Semester
            ("BSIT", 1, 2, "CC 103", "Intermediate Programming", 3, "Advanced modular programming, exception handling, and data encapsulation."),
            ("BSIT", 1, 2, "IT 104", "Discrete Mathematics for IT", 3, "Discrete mathematical structures, set theory, graph theory, and boolean algebra."),

            # 2nd Year - 1st Semester (22 units, 8 subjects)
            ("BSIT", 2, 1, "CC 105", "Application Development and Emerging Technologies", 3, "Modern software platforms, web APIs, and emerging tech stacks."),
            ("BSIT", 2, 1, "IT 201", "Integrative Programming and Technologies 1", 3, "Inter-system communication, scripting, and component integration."),
            ("BSIT", 2, 1, "GE 9", "Rizals Life and Works", 3, "Life, works, and writings of the national hero Jose Rizal."),
            ("BSIT", 2, 1, "GE 7", "Science, Technology and Society", 3, "Interactions between scientific advancements and modern society."),
            ("BSIT", 2, 1, "PATHfit 3", "Physical Activities Toward Health and Fitness 3: Menu of Dance", 2, "Dance forms, rhythmic movement, and physical fitness."),
            ("BSIT", 2, 1, "Theology 3", "Sacraments and Liturgy", 2, "Theological principles of church liturgy and sacraments."),
            ("BSIT", 2, 1, "ITE 103", "Human Computer Interaction 2", 3, "Advanced UI/UX paradigms, usability testing, and accessibility."),
            ("BSIT", 2, 1, "CC 104", "Data Structures and Algorithms", 3, "Core algorithms, complexity, trees, graphs, and linear data structures."),

            # 2nd Year - 2nd Semester
            ("BSIT", 2, 2, "IT 203", "Database Management Systems", 3, "Relational database models, normalization, SQL queries, and ACID transactions."),
            ("BSIT", 2, 2, "IT 202", "Networking 1 - Fundamentals", 3, "OSI model, TCP/IP networking, subnetting, IPv4/IPv6, and switch configuration."),

            # 3rd Year - 1st Semester (23 units, 8 subjects)
            ("BSIT", 3, 1, "IT 302", "Networking 2", 3, "Advanced routing, switching, VLANs, and network infrastructure."),
            ("BSIT", 3, 1, "ITE 106", "Information Assurance and Security 2", 3, "Network defense, security governance, and vulnerability mitigation."),
            ("BSIT", 3, 1, "IT 204", "Information Assurance and Security 1", 3, "Security principles, CIA triad, access controls, and risk management."),
            ("BSIT", 3, 1, "ITE 107", "Web Systems and Technologies 2", 3, "Full-stack enterprise web frameworks, authentication, and state."),
            ("BSIT", 3, 1, "IT 304", "Social and Professional Issues 1", 3, "Ethics, intellectual property, cyber law, and IT professional code."),
            ("BSIT", 3, 1, "IT 303", "Advanced Database Systems", 3, "Query optimization, indexing, distributed databases, and transaction ACID."),
            ("BSIT", 3, 1, "IT 301", "Quantitative Methods", 3, "Statistical techniques, modeling, and data-driven decision making."),
            ("BSIT", 3, 1, "Theology 5", "Moral Theology", 2, "Ethical decision-making, moral norms, and Christian social teaching."),

            # 3rd Year - 2nd Semester
            ("BSIT", 3, 2, "IT 321", "Mobile Application Development", 3, "Cross-platform mobile development, UI gestures, and sensor integration."),
            ("BSIT", 3, 2, "IT 322", "Capstone Project & Research 1", 3, "Problem scoping, proposal writing, and technological project defense."),

            # 4th Year - 1st Semester (9 units, 3 subjects)
            ("BSIT", 4, 1, "IT 401", "System Administration and Maintenance", 3, "Server operations, Linux/Windows administration, automation, and backup."),
            ("BSIT", 4, 1, "ITE 112", "Integrative Programming and Technologies 2", 3, "Enterprise architecture, microservices, and system scaling."),
            ("BSIT", 4, 1, "CAP 102", "Capstone and Project Research 2", 3, "Implementation, testing, deployment, and final oral defense of capstone system."),

            # 4th Year - 2nd Semester
            ("BSIT", 4, 2, "IT 402", "Practicum / Industry Internship", 6, "Industry immersion, software development internship, and technical documentation."),

            # ─────────────────────────────────────────────────────────────
            # 2. CMAT — BSBA (Business Administration)
            # ─────────────────────────────────────────────────────────────
            ("BSBA", 1, 1, "BA101", "Principles of Management", 3, "Fundamental principles, organizational structure, planning, and managerial functions."),
            ("BSBA", 1, 2, "BA102", "Marketing Management", 3, "Market research, consumer behavior, product design, pricing, and promotion strategies."),
            ("BSBA", 2, 1, "BA201", "Human Resource Management", 3, "Talent acquisition, employee retention, labor laws, and workplace performance."),
            ("BSBA", 2, 2, "BA202", "Operations Management & TQM", 3, "Supply chain optimization, inventory control, and Total Quality Management."),

            # ─────────────────────────────────────────────────────────────
            # 3. CMAT — BSA (Accountancy)
            # ─────────────────────────────────────────────────────────────
            ("BSA", 1, 1, "ACT101", "Financial Accounting & Reporting 1", 3, "Accounting equation, journal entries, ledger posting, and balance sheet preparation."),
            ("BSA", 1, 2, "ACT102", "Conceptual Framework & Accounting Standards", 3, "Philippine Financial Reporting Standards (PFRS) and international frameworks."),
            ("BSA", 2, 1, "ACT201", "Cost Accounting & Control", 3, "Job order costing, process costing, activity-based costing, and budget forecasting."),

            # ─────────────────────────────────────────────────────────────
            # 4. CEAS — BEED (Elementary Education)
            # ─────────────────────────────────────────────────────────────
            ("BEED", 1, 1, "ED101", "Child and Adolescent Learners", 3, "Developmental stages, psycho-emotional growth, and learning theories for young learners."),
            ("BEED", 1, 2, "ED102", "The Teaching Profession", 3, "Professional teacher standards, Philippine ethical code, and institutional policies."),
            ("BEED", 2, 1, "ED201", "Facilitating Learner-Centered Teaching", 3, "Contemporary instructional methodologies, differentiated learning, and classroom dynamics."),
            ("BEED", 2, 2, "ED202", "Assessment in Learning 1", 3, "Formative and summative assessment tools, rubrics, and educational measurement."),
            ("BEED", 3, 1, "ED301", "Technology for Teaching and Learning", 3, "Digital classroom media, instructional tech, and interactive learning tools."),

            # ─────────────────────────────────────────────────────────────
            # 5. CEAS — BSED-ENG (Secondary Education major in English)
            # ─────────────────────────────────────────────────────────────
            ("BSED-ENG", 1, 1, "ENG101", "Introduction to Linguistics", 3, "Phonology, morphology, syntax, and semantics of the English language."),
            ("BSED-ENG", 1, 2, "ENG102", "Structure of English", 3, "Advanced grammatical systems, pedagogical grammar, and language analysis."),
            ("BSED-ENG", 2, 1, "ENG201", "Teaching of Listening and Reading", 3, "Comprehension methodologies, literacy strategies, and instructional assessment."),

            # ─────────────────────────────────────────────────────────────
            # 6. CEAS — AB-PSYCH (Psychology)
            # ─────────────────────────────────────────────────────────────
            ("AB-PSYCH", 1, 1, "PSY101", "General Psychology", 3, "Foundations of human behavioral psychology, perception, cognition, and emotion."),
            ("AB-PSYCH", 1, 2, "PSY102", "Theories of Personality", 3, "Psychodynamic, cognitive, humanistic, and trait theories of personality."),

            # ─────────────────────────────────────────────────────────────
            # 7. COC — BSCRIM (Criminology)
            # ─────────────────────────────────────────────────────────────
            ("BSCRIM", 1, 1, "CRIM101", "Introduction to Criminology", 3, "Scientific study of crimes, criminals, victimology, and societal reactions."),
            ("BSCRIM", 1, 1, "CRIM102", "Theories of Crime Causation", 3, "Biological, psychological, sociological, and economic causes of criminality."),
            ("BSCRIM", 1, 2, "CRIM103", "Philippine Criminal Justice System", 3, "Law enforcement, prosecution, courts, penology, and community corrections."),
            ("BSCRIM", 1, 2, "CRIM104", "Human Rights Education for Law Enforcement", 3, "Constitutional rights, custodial investigation rights, and anti-torture protocols."),
            ("BSCRIM", 2, 1, "CRIM201", "Criminal Law (Book 1) - General Principles", 3, "Revised Penal Code rules, felony elements, mitigating and aggravating circumstances."),
            ("BSCRIM", 2, 1, "CRIM202", "Forensic Photography & Digital Imaging", 3, "Crime scene documentation, exposure calculation, and courtroom photographic evidence."),
            ("BSCRIM", 2, 2, "CRIM203", "Dactyloscopy & Fingerprint Analysis", 3, "Ridge characteristics, latent print lifting, AFIS technology, and forensic comparison."),
            ("BSCRIM", 2, 2, "CRIM204", "Police Patrol Operations & Dispatch", 3, "Strategic patrol tactics, dispatch communication, emergency response, and community policing."),
            ("BSCRIM", 3, 1, "CRIM301", "Fundamentals of Criminal Investigation", 3, "Chain of custody, forensic interrogation, surveillance, and evidence handling."),
            ("BSCRIM", 3, 1, "CRIM302", "Traffic Management & Accident Investigation", 3, "Traffic laws, collision reconstruction, field sketches, and driver licensing protocols."),
        ]

        created_subjects = 0
        created_curriculum = 0

        dry_run = options.get('dry_run', False)
        for prog_code, year, sem, sub_code, sub_name, units, desc in ([] if dry_run else curriculum_dataset):
            # 1. Subject get_or_create
            subject, s_created = Subject.objects.get_or_create(
                code=sub_code,
                defaults={
                    "name": sub_name,
                    "units": units,
                    "description": desc,
                    "is_active": True,
                }
            )
            if s_created:
                created_subjects += 1

            # 2. Curriculum mapping get_or_create (both versioned and fallback)
            prog = programs[prog_code]
            version_obj, _ = CurriculumVersion.objects.get_or_create(
                program=prog,
                version_number=1,
                defaults={"status": CurriculumVersion.STATUS_APPROVED, "notes": f"Official {prog.code} Curriculum"}
            )
            # Versioned row
            Curriculum.objects.get_or_create(
                program=prog,
                version=version_obj,
                year_level=year,
                semester=sem,
                subject=subject,
            )
            # Legacy fallback row
            curriculum_entry, c_created = Curriculum.objects.get_or_create(
                program=prog,
                version=None,
                year_level=year,
                semester=sem,
                subject=subject,
            )
            if c_created:
                created_curriculum += 1
                self.stdout.write(f"  + [{prog.code}] Year {year} Sem {sem}: {subject.code} — {subject.name}")

        self.stdout.write(self.style.SUCCESS(
            f"\nDONE! Successfully created/verified {created_subjects} new subjects and {created_curriculum} curriculum mappings across COC, CEAS, and CMAT!"
        ))

        batch_years = options.get('batches')
        if batch_years:
            self._seed_batches(
                programs,
                batch_years,
                program_codes=options.get('programs'),
                dry_run=options.get('dry_run', False),
            )

    def _seed_batches(self, programs, batch_years, program_codes=None, dry_run=False):
        """
        // Opt-in: give each program a prospectus version per entering batch.
        // Idempotent: a batch whose effective term already exists is skipped.
        // Programs with a pending draft or no approved subjects are left untouched
        // so in-progress editorial work and the one-approved invariant stay safe.
        """
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"=== Seeding batch prospectuses for {sorted(set(batch_years))} ==="
        ))
        template = AcademicYear.objects.filter(is_active=True).first()
        codes = [c.upper() for c in program_codes] if program_codes else list(programs.keys())
        created = 0
        for code in codes:
            prog = programs.get(code)
            if prog is None:
                self.stdout.write(self.style.WARNING(f"  ! {code}: not a seeded program, skipped."))
                continue
            approved = latest_curriculum_version(prog, statuses=(CurriculumVersion.STATUS_APPROVED,))
            if approved is None or not approved.entries.exists():
                self.stdout.write(self.style.WARNING(f"  ! {code}: no approved subjects to clone, skipped."))
                continue
            if current_draft_version(prog) is not None:
                self.stdout.write(self.style.WARNING(f"  ! {code}: has a pending draft, skipped (approve or discard it first)."))
                continue
            for year in sorted(set(batch_years)):
                term_name = f"{year}-{year + 1} 1st Sem"
                if CurriculumVersion.objects.filter(program=prog, effective_from__name=term_name).exists():
                    self.stdout.write(f"  = [{code}] Batch {year} already exists, skipped.")
                    continue
                if template is not None:
                    starts_on = date(year, template.starts_on.month, template.starts_on.day)
                    ends_on = date(year, template.ends_on.month, template.ends_on.day)
                    if ends_on <= starts_on:
                        ends_on = date(year + 1, template.ends_on.month, template.ends_on.day)
                else:
                    starts_on, ends_on = date(year, 8, 1), date(year, 12, 31)
                if dry_run:
                    self.stdout.write(f"  ~ [{code}] would create Batch {year} ({term_name}).")
                    continue
                term, _ = AcademicYear.objects.get_or_create(
                    name=term_name,
                    defaults={"starts_on": starts_on, "ends_on": ends_on, "is_active": False},
                )
                draft = create_curriculum_draft(None, prog, notes=f"Batch {year} prospectus")['instance']
                result = approve_curriculum_draft(None, draft, effective_from=term)
                created += 1
                self.stdout.write(self.style.SUCCESS(f"  + [{code}] {result['message']}"))
        verb = "would create" if dry_run else "created"
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Batch prospectuses: {verb} {created} version(s)."))
