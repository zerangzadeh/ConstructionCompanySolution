from django.db import migrations, models

from apps.audit.models import AuditAction


class Migration(migrations.Migration):
    dependencies = [("audit", "0055_fiscal_year_closing_actions")]  # noqa: RUF012
    operations = [  # noqa: RUF012
        migrations.AlterField(
            model_name="auditevent",
            name="action",
            field=models.CharField(
                "عملیات", max_length=64, choices=AuditAction.choices
            ),
        )
    ]
