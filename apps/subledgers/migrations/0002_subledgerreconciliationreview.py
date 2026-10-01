import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0063_p3_s30_s31_reconciliation_review_permissions"),
        ("subledgers", "0001_initial"),
    ]
    operations = [
        migrations.CreateModel(
            name="SubledgerReconciliationReview",
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
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="زمان ایجاد")),
                ("reason", models.TextField()),
                ("run_evidence_hash", models.CharField(max_length=64)),
                ("signed_evidence_hash", models.CharField(max_length=64)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="organizations.organization",
                    ),
                ),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="organizations.organizationmembership",
                    ),
                ),
                (
                    "run",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="review",
                        to="subledgers.subledgerreconciliationrun",
                    ),
                ),
            ],
        )
    ]
