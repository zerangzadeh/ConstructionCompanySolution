import django.core.validators
from django.db import migrations, models

import apps.organizations.models

SUPPORTED_BASE_CURRENCY = "IRR"


def establish_settings_authority(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    OrganizationSettings = apps.get_model("organizations", "OrganizationSettings")

    existing_organization_ids = set(
        OrganizationSettings.objects.values_list("organization_id", flat=True)
    )
    for organization in Organization.objects.exclude(
        pk__in=existing_organization_ids
    ).iterator():
        currency = str(organization.currency).strip().upper()
        if currency != SUPPORTED_BASE_CURRENCY:
            raise RuntimeError(
                "P1-S14A cannot infer or convert a missing Tenant base currency; "
                f"resolve Organization {organization.pk} before migration."
            )
        OrganizationSettings.objects.create(
            organization_id=organization.pk,
            timezone=organization.timezone,
            currency=SUPPORTED_BASE_CURRENCY,
        )

    unsupported = OrganizationSettings.objects.exclude(
        currency=SUPPORTED_BASE_CURRENCY
    ).values_list("organization_id", flat=True)
    unsupported_ids = list(unsupported[:20])
    if unsupported_ids:
        raise RuntimeError(
            "P1-S14A found unsupported authoritative base currencies; resolve "
            f"Tenant settings before migration: {unsupported_ids}"
        )


class Migration(migrations.Migration):
    dependencies = [("organizations", "0035_p1_1_role_catalog_closeout")]  # noqa: RUF012

    operations = [  # noqa: RUF012
        migrations.AlterField(
            model_name="organizationsettings",
            name="currency",
            field=models.CharField(
                default="IRR",
                max_length=3,
                validators=[
                    django.core.validators.RegexValidator(
                        message=("واحد پول باید یک کد سه‌حرفی با حروف بزرگ لاتین باشد."),
                        regex="^[A-Z]{3}$",
                    ),
                    apps.organizations.models.validate_supported_base_currency,
                ],
                verbose_name="واحد پول پیش‌فرض",
            ),
        ),
        migrations.RunPython(
            establish_settings_authority,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
