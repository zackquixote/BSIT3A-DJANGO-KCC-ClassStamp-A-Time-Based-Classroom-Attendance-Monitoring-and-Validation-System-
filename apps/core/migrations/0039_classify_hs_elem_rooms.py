# Classify existing HS-* / ELEM-* rooms with the new building-specific types.

from django.db import migrations


def forwards(apps, schema_editor):
    Room = apps.get_model('core', 'Room')
    Room.objects.filter(code__startswith='HS-').update(room_type='HS')
    Room.objects.filter(name__icontains='high school').update(room_type='HS')
    Room.objects.filter(code__startswith='ELEM-').update(room_type='ELEM')
    Room.objects.filter(name__icontains='elementary').update(room_type='ELEM')


def backwards(apps, schema_editor):
    Room = apps.get_model('core', 'Room')
    Room.objects.filter(room_type__in=['HS', 'ELEM']).update(room_type='LECTURE')


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0038_facilitytype_hs_elem'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
