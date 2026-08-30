import django.db.models.deletion
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("daily_reports", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="DailyReportEquipmentEntry",
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
                ("equipment_name", models.CharField(max_length=255)),
                ("hours_used", models.DecimalField(decimal_places=2, max_digits=8)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="daily_report_equipment_entries_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="daily_report_equipment_entries",
                        to="organizations.organization",
                    ),
                ),
                (
                    "report",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="equipment_entries",
                        to="daily_reports.dailyreport",
                    ),
                ),
            ],
            options={"ordering": ["created_at"]},
        ),
        migrations.CreateModel(
            name="DailyReportLaborEntry",
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
                ("team_name", models.CharField(max_length=120)),
                ("worker_count", models.PositiveIntegerField()),
                ("hours_worked", models.DecimalField(decimal_places=2, max_digits=8)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="daily_report_labor_entries_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="daily_report_labor_entries",
                        to="organizations.organization",
                    ),
                ),
                (
                    "report",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="labor_entries",
                        to="daily_reports.dailyreport",
                    ),
                ),
            ],
            options={"ordering": ["created_at"]},
        ),
        migrations.CreateModel(
            name="DailyReportMaterialEntry",
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
                ("material_name", models.CharField(max_length=255)),
                (
                    "quantity",
                    models.DecimalField(
                        decimal_places=4,
                        default=Decimal("0.0000"),
                        max_digits=18,
                    ),
                ),
                ("unit", models.CharField(max_length=30)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="daily_report_material_entries_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="daily_report_material_entries",
                        to="organizations.organization",
                    ),
                ),
                (
                    "report",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="material_entries",
                        to="daily_reports.dailyreport",
                    ),
                ),
            ],
            options={"ordering": ["created_at"]},
        ),
        migrations.AddIndex(
            model_name="dailyreportlaborentry",
            index=models.Index(
                fields=["organization", "report"],
                name="daily_labor_org_report_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="dailyreportequipmententry",
            index=models.Index(
                fields=["organization", "report"],
                name="daily_equipment_org_report_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="dailyreportmaterialentry",
            index=models.Index(
                fields=["organization", "report"],
                name="daily_material_org_report_idx",
            ),
        ),
    ]
