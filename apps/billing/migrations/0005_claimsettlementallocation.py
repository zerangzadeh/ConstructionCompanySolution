import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0004_f64_claim_approval"),
        ("payments", "0005_backfill_paymentallocation_reversal_reason"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ClaimSettlementAllocation",
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
                (
                    "updated_at",
                    models.DateTimeField(
                        auto_now=True, verbose_name="زمان آخرین به‌روزرسانی"
                    ),
                ),
                ("amount", models.DecimalField(decimal_places=2, max_digits=18)),
                ("reason", models.TextField()),
                (
                    "status",
                    models.CharField(
                        choices=[("active", "فعال"), ("reversed", "برگشت‌خورده")],
                        default="active",
                        max_length=20,
                    ),
                ),
                ("reversed_at", models.DateTimeField(blank=True, null=True)),
                ("reversal_reason", models.TextField(blank=True)),
                (
                    "claim",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="settlement_allocations",
                        to="billing.progressclaim",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="claim_settlement_allocations_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="claim_settlement_allocations",
                        to="organizations.organization",
                    ),
                ),
                (
                    "payment_allocation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="claim_settlement_allocations",
                        to="payments.paymentallocation",
                    ),
                ),
                (
                    "reversed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="claim_settlement_allocations_reversed",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "تخصیص تسویه صورت‌وضعیت",
                "verbose_name_plural": "تخصیص‌های تسویه صورت‌وضعیت",
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("amount__gt", 0)),
                        name="claim_settlement_amount_positive",
                    )
                ],
            },
        ),
        migrations.AddIndex(
            model_name="claimsettlementallocation",
            index=models.Index(
                fields=["organization", "claim", "status"],
                name="clm_set_org_clm_stat_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="claimsettlementallocation",
            index=models.Index(
                fields=["organization", "payment_allocation", "status"],
                name="clm_set_org_pay_stat_idx",
            ),
        ),
    ]
