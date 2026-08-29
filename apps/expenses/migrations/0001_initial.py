import uuid
from decimal import Decimal

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("organizations", "0003_organizationinvitation"),
        ("projects", "0001_initial"),
        ("audit", "0002_alter_auditevent_action"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Expense",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("materials", "Materials"),
                            ("labor", "Labor"),
                            ("equipment", "Equipment"),
                            ("subcontractor", "Subcontractor"),
                            ("permit", "Permit"),
                            ("other", "Other"),
                        ],
                        db_index=True,
                        default="other",
                        max_length=30,
                    ),
                ),
                ("description", models.CharField(max_length=255)),
                ("vendor_name", models.CharField(blank=True, max_length=255)),
                (
                    "amount",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0.00"),
                        max_digits=18,
                    ),
                ),
                ("incurred_on", models.DateField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("recorded", "Recorded"),
                            ("void", "Void"),
                        ],
                        db_index=True,
                        default="recorded",
                        max_length=20,
                    ),
                ),
                (
                    "receipt_reference",
                    models.CharField(blank=True, max_length=120),
                ),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="expenses_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="expenses",
                        to="organizations.organization",
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="expenses",
                        to="projects.project",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="expenses_updated",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-incurred_on", "-created_at"]},
        ),
        migrations.AddIndex(
            model_name="expense",
            index=models.Index(
                fields=["organization", "project", "incurred_on"],
                name="expense_org_project_date_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="expense",
            index=models.Index(
                fields=["organization", "category"],
                name="expense_org_category_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="expense",
            index=models.Index(
                fields=["organization", "deleted_at"],
                name="expense_org_deleted_idx",
            ),
        ),
    ]
