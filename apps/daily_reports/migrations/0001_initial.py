import django.db.models.deletion
import uuid

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("organizations", "0003_organizationinvitation"),
        ("projects", "0002_projectsite"),
    ]

    operations = [
        migrations.CreateModel(
            name="DailyReport",
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
                ("reporting_date", models.DateField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("submitted", "Submitted"),
                            ("approved", "Approved"),
                        ],
                        db_index=True,
                        default="draft",
                        max_length=20,
                    ),
                ),
                ("weather_conditions", models.CharField(blank=True, max_length=255)),
                ("labor_count", models.PositiveIntegerField(default=0)),
                ("work_performed", models.TextField()),
                ("progress_summary", models.TextField(blank=True)),
                ("issues_and_delays", models.TextField(blank=True)),
                ("safety_notes", models.TextField(blank=True)),
                ("quality_notes", models.TextField(blank=True)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "approved_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="daily_reports_approved",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="daily_reports_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="daily_reports",
                        to="organizations.organization",
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="daily_reports",
                        to="projects.project",
                    ),
                ),
                (
                    "site",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="daily_reports",
                        to="projects.projectsite",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="daily_reports_updated",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-reporting_date", "-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="dailyreport",
            constraint=models.UniqueConstraint(
                fields=("organization", "site", "reporting_date"),
                name="daily_report_org_site_date_uq",
            ),
        ),
        migrations.AddIndex(
            model_name="dailyreport",
            index=models.Index(
                fields=["organization", "reporting_date"],
                name="daily_report_org_date_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="dailyreport",
            index=models.Index(
                fields=["organization", "status"],
                name="daily_report_org_status_idx",
            ),
        ),
    ]
