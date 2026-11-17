# Remove the unused AVR type and add the building-specific HS / Elem types.

from django.db import migrations


def forwards(apps, schema_editor):
    FacilityType = apps.get_model('core', 'FacilityType')
    Room = apps.get_model('core', 'Room')

    # No room should be left pointing at a deleted type.
    Room.objects.filter(room_type='AVR').update(room_type='OTHER')
    FacilityType.objects.filter(code='AVR').delete()

    FacilityType.objects.get_or_create(
        code='HS', defaults={'name': 'HS Room', 'sort_order': 30},
    )
    FacilityType.objects.get_or_create(
        code='ELEM', defaults={'name': 'Elem Room', 'sort_order': 40},
    )
    FacilityType.objects.filter(code='OTHER').update(sort_order=50)


def backwards(apps, schema_editor):
    FacilityType = apps.get_model('core', 'FacilityType')
    FacilityType.objects.filter(code__in=['HS', 'ELEM']).delete()
    FacilityType.objects.get_or_create(
        code='AVR',
        defaults={'name': 'Audio-Visual Room (AVR)', 'sort_order': 30},
    )
    FacilityType.objects.filter(code='OTHER').update(sort_order=40)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0037_facilitytype'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
