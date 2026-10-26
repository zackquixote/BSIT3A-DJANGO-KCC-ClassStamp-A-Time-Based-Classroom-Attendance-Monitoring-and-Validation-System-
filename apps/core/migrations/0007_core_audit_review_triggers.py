# // Manual migration: ports the append-only DB triggers for the audit and
# // anomaly review tables (defined in sql/bsitcrud.sql) into the migration
# // chain so fresh deployments get the same enforcement as the SQL dump.
# // Guarded by connection vendor: SQLite (tests) and other backends skip it.

from django.db import migrations

TRIGGERS = {
    'trg_cs_audit_bu': (
        "CREATE TRIGGER `trg_cs_audit_bu` BEFORE UPDATE ON `tblcs_audit_event` "
        "FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Audit events are append-only'"
    ),
    'trg_cs_audit_bd': (
        "CREATE TRIGGER `trg_cs_audit_bd` BEFORE DELETE ON `tblcs_audit_event` "
        "FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Audit events are append-only'"
    ),
    'trg_cs_review_bu': (
        "CREATE TRIGGER `trg_cs_review_bu` BEFORE UPDATE ON `tblcs_review_action` "
        "FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Review actions are append-only'"
    ),
    'trg_cs_review_bd': (
        "CREATE TRIGGER `trg_cs_review_bd` BEFORE DELETE ON `tblcs_review_action` "
        "FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Review actions are append-only'"
    ),
}


def _apply_triggers(schema_editor, create=True):
    if schema_editor.connection.vendor != 'mysql':
        return
    for name, ddl in TRIGGERS.items():
        if create:
            try:
                schema_editor.execute(f'DROP TRIGGER IF EXISTS `{name}`')
            except Exception:
                pass
            schema_editor.execute(ddl)
        else:
            schema_editor.execute(f'DROP TRIGGER IF EXISTS `{name}`')


def apply_triggers(apps, schema_editor):
    _apply_triggers(schema_editor, create=True)


def remove_triggers(apps, schema_editor):
    _apply_triggers(schema_editor, create=False)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_anomalyflag_session_anomalyflag_student_profile_and_more'),
    ]

    operations = [
        migrations.RunPython(apply_triggers, remove_triggers),
    ]
