from decimal import Decimal
from typing import ClassVar

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies: ClassVar[list] = [
        ("contracts", "0006_p6_s07_s13_payment_due_days"),
    ]

    operations: ClassVar[list] = [
        migrations.RemoveConstraint(
            model_name="contracttermversion",
            name="contract_term_caps_nonnegative",
        ),
        migrations.AddField(
            model_name="contracttermversion",
            name="retention_release_cap",
            field=models.DecimalField(
                decimal_places=4, default=Decimal(0), max_digits=18
            ),
        ),
        migrations.AddField(
            model_name="contracttermversion",
            name="retention_release_requirement",
            field=models.CharField(
                choices=[
                    ("unconfigured", "تعریف‌نشده"),
                    ("evidence_only", "با شواهد قراردادی"),
                    ("approved_clearance", "با مفاصاحساب تأییدشده"),
                ],
                default="unconfigured",
                max_length=30,
            ),
        ),
        migrations.AddConstraint(
            model_name="contracttermversion",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(retention_cap__gte=0)
                    & models.Q(advance_recovery_cap__gte=0)
                    & models.Q(contractual_insurance_cap__gte=0)
                    & models.Q(retention_release_cap__gte=0)
                ),
                name="contract_term_caps_nonnegative",
            ),
        ),
    ]
