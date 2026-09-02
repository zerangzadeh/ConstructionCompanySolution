import django.db.models.deletion
import uuid

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("projects", "0002_projectsite"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProjectPhase",
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
                ("code", models.CharField(max_length=50)),
                ("name", models.CharField(max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("planning", "Planning"),
                            ("active", "Active"),
                            ("on_hold", "On hold"),
                            ("completed", "Completed"),
                        ],
                        db_index=True,
                        default="planning",
                        max_length=20,
                    ),
                ),
                ("planned_start_date", models.DateField(blank=True, null=True)),
                ("planned_end_date", models.DateField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="project_phases_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="project_phases",
                        to="organizations.organization",
                    ),
                ),
                (
                    "site",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="phases",
                        to="projects.projectsite",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="project_phases_updated",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.AddConstraint(
            model_name="projectphase",
            constraint=models.UniqueConstraint(
                fields=("organization", "site", "code"),
                name="unique_phase_code_per_site",
            ),
        ),
        migrations.AddIndex(
            model_name="projectphase",
            index=models.Index(
                fields=["organization", "site", "status"],
                name="phase_org_site_status_idx",
            ),
        ),
    ]
