import hashlib

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def populate_endpoint_hashes(apps, schema_editor):
    PushSubscription = apps.get_model('core', 'PushSubscription')
    for subscription in PushSubscription.objects.all().iterator():
        subscription.endpoint_hash = hashlib.sha256(subscription.endpoint.encode('utf-8')).hexdigest()
        subscription.save(update_fields=['endpoint_hash'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0024_push_and_room_verification'),
    ]

    operations = [
        migrations.AddField(
            model_name='pushsubscription',
            name='endpoint_hash',
            field=models.CharField(editable=False, max_length=64, null=True),
        ),
        migrations.RunPython(populate_endpoint_hashes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='pushsubscription',
            name='endpoint',
            field=models.TextField(),
        ),
        migrations.AlterField(
            model_name='pushsubscription',
            name='endpoint_hash',
            field=models.CharField(editable=False, max_length=64, unique=True),
        ),
    ]
