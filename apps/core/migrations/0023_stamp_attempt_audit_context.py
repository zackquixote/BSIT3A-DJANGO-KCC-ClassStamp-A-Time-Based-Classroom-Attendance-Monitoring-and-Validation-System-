from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0022_curriculum_major_flag'),
    ]

    operations = [
        migrations.AddField(
            model_name='stampattempt',
            name='client_ip',
            field=models.GenericIPAddressField(blank=True, help_text='// Scanner network address captured at scan time', null=True),
        ),
        migrations.AddField(
            model_name='stampattempt',
            name='user_agent',
            field=models.CharField(blank=True, help_text='// Scanner browser or device user agent', max_length=500, null=True),
        ),
    ]
