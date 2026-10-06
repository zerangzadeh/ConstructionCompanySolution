import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('daily_reports', '0005_fieldobservation_fielddownstreamproposal_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='fieldobservationevidencelink',
            name='operation_key',
            field=models.UUIDField(default=uuid.uuid4),
        ),
        migrations.AlterField(
            model_name='fieldobservationevidencelink',
            name='payload_hash',
            field=models.CharField(default='', max_length=64),
        ),
        migrations.AlterField(
            model_name='fieldobservationevidencelink',
            name='sha256',
            field=models.CharField(default='', max_length=64),
        ),
    ]
