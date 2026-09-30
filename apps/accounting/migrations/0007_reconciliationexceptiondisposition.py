import uuid
from typing import ClassVar

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies: ClassVar[list[tuple[str, str]]] = [
        ("accounting", "0006_reconciliationtieoutsnapshot"),
        ("audit", "0038_p2_reconciliation_disposition_action"),
        ("organizations", "0053_p2_reconciliation_disposition_permission"),
    ]
    operations: ClassVar[list[migrations.operations.base.Operation]] = [
        migrations.CreateModel(
            name="ReconciliationExceptionDisposition",
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
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="زمان ایجاد"
                    ),
                ),
                (
                    "disposition",
                    models.CharField(
                        choices=[
                            ("correction_required", "نیازمند اصلاح"),
                            ("explained_variance", "اختلاف توضیح‌داده‌شده"),
                            ("not_applicable", "نامرتبط"),
                        ],
                        max_length=32,
                    ),
                ),
                ("reason", models.TextField()),
                (
                    "evidence_reference",
                    models.CharField(blank=True, max_length=500),
                ),
                (
                    "disposed_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="accounting_reconciliation_exceptions_disposed",
                        to="organizations.organizationmembership",
                    ),
                ),
                (
                    "exception",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="disposition",
                        to="accounting.reconciliationexceptionsnapshot",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="accounting_reconciliation_exception_dispositions",
                        to="organizations.organization",
                    ),
                ),
            ],
            options={
                "ordering": ["exception"],
                "constraints": [
                    models.CheckConstraint(
                        condition=~models.Q(reason=""),
                        name="reconciliation_disposition_reason_nonempty",
                    )
                ],
            },
        ),
    ]
