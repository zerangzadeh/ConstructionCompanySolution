import uuid
from typing import ClassVar

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies: ClassVar[list[tuple[str, str]]] = [
        ("accounting", "0007_reconciliationexceptiondisposition"),
        ("audit", "0039_p2_reconciliation_sign_off_action"),
        ("organizations", "0054_p2_reconciliation_sign_off"),
    ]
    operations: ClassVar[list[migrations.operations.base.Operation]] = [
        migrations.CreateModel(
            name="ReconciliationReview",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        verbose_name="شناسه",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="زمان ایجاد"),
                ),
                ("reason", models.TextField()),
                ("scope_hash", models.CharField(max_length=64)),
                ("input_hash", models.CharField(max_length=64)),
                ("result_hash", models.CharField(max_length=64)),
                ("disposition_hash", models.CharField(max_length=64)),
                ("signed_evidence_hash", models.CharField(max_length=64)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="accounting_reconciliation_reviews",
                        to="organizations.organization",
                    ),
                ),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="accounting_reconciliations_reviewed",
                        to="organizations.organizationmembership",
                    ),
                ),
                (
                    "run",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="review",
                        to="accounting.reconciliationrun",
                    ),
                ),
            ],
            options={
                "ordering": ["run"],
                "constraints": [
                    models.CheckConstraint(
                        condition=~models.Q(reason=""),
                        name="reconciliation_review_reason_nonempty",
                    )
                ],
            },
        )
    ]
