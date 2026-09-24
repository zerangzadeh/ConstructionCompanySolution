from django.db import migrations, models

from apps.audit.models import AuditAction


class Migration(migrations.Migration):
    dependencies = [("audit", "0028_alter_auditevent_action")]  # noqa: RUF012

    operations = [  # noqa: RUF012
        migrations.AlterField(
            model_name="auditevent",
            name="action",
            field=models.CharField(
                choices=AuditAction.choices,
                max_length=64,
                verbose_name="عملیات",
            ),
        )
    ]
