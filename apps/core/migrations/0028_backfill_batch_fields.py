from django.db import migrations


def backfill_batch_fields(apps, schema_editor):
    """Derive entry_year from the student ID prefix and pin the batch prospectus.

    Idempotent and tolerant: only fills NULL fields, skips malformed ID prefixes,
    and updates just the two new columns so the profile approval/role triggers
    (which fire on approval_status / role / year_level changes) are never tripped.
    """
    Profile = apps.get_model('core', 'Profile')
    CurriculumVersion = apps.get_model('core', 'CurriculumVersion')
    db = schema_editor.connection.alias
    for profile in Profile.objects.using(db).filter(role='STUDENT').iterator():
        updates = {}
        entry_year = profile.entry_year
        if entry_year is None and profile.student_number:
            head = str(profile.student_number).strip().split('-', 1)[0]
            digits = ''.join(c for c in head if c.isdigit())[:4]
            if len(digits) == 4:
                year = int(digits)
                if 1900 <= year <= 2100:
                    entry_year = year
                    updates['entry_year'] = year
        if profile.curriculum_version_id is None and entry_year and profile.program_id:
            version = (
                CurriculumVersion.objects.using(db)
                .filter(
                    program_id=profile.program_id,
                    effective_from__starts_on__year=entry_year,
                    status__in=['APPROVED', 'ARCHIVED'],
                )
                .order_by('-version_number')
                .first()
            )
            if version is not None:
                updates['curriculum_version_id'] = version.pk
        if updates:
            Profile.objects.using(db).filter(pk=profile.pk).update(**updates)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0027_profile_batch_fields'),
    ]

    operations = [
        migrations.RunPython(backfill_batch_fields, migrations.RunPython.noop),
    ]
