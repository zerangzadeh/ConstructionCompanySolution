import uuid

from django.db import migrations, models
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator


def backfill_organization_settings(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    OrganizationSettings = apps.get_model("organizations", "OrganizationSettings")

    for organization in Organization.objects.iterator():
        OrganizationSettings.objects.get_or_create(
            organization_id=organization.pk,
            defaults={
                "timezone": organization.timezone,
                "currency": organization.currency,
                "fiscal_year_start_month": 1,
            },
        )


class Migration(migrations.Migration):
    dependencies = [("organizations", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="OrganizationSettings",
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
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("timezone", models.CharField(default="UTC", max_length=64)),
                (
                    "currency",
                    models.CharField(
                        default="USD",
                        max_length=3,
                        validators=[
                            RegexValidator(
                                message="Currency must be a three-letter uppercase code.",
                                regex="^[A-Z]{3}$",
                            )
                        ],
                    ),
                ),
                (
                    "fiscal_year_start_month",
                    models.PositiveSmallIntegerField(
                        default=1,
                        validators=[MinValueValidator(1), MaxValueValidator(12)],
                    ),
                ),
                (
                    "organization",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.CASCADE,
                        related_name="settings",
                        to="organizations.organization",
                    ),
                ),
            ],
        ),
        migrations.RunPython(backfill_organization_settings, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="organizationsettings",
            name="organization",
            field=models.OneToOneField(
                on_delete=models.deletion.CASCADE,
                related_name="settings",
                to="organizations.organization",
            ),
        ),
    ]
