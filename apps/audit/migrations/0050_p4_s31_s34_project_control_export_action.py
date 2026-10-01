from typing import ClassVar

from django.db import migrations, models

from apps.audit.models import AuditAction


class Migration(migrations.Migration):
    dependencies: ClassVar[list[tuple[str, str]]] = [
        ("audit", "0049_p4_s26_s30_expense_actions")
    ]
    operations: ClassVar[list] = [
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
