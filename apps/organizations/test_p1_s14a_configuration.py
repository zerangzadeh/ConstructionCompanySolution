from importlib import import_module

from django.apps import apps
from django.test import TestCase

from apps.organizations.models import Organization, OrganizationSettings


class ConfigurationAuthorityMigrationTests(TestCase):
    migration = import_module(
        "apps.organizations.migrations.0036_p1_s14a_configuration_authority"
    )

    def test_backfill_uses_legacy_evidence_only_for_a_missing_settings_row(
        self,
    ) -> None:
        organization = Organization.objects.create(
            name="Missing Settings",
            slug="missing-settings",
            timezone="Asia/Tehran",
            currency="IRR",
        )

        self.migration.establish_settings_authority(apps, schema_editor=None)

        settings_record = OrganizationSettings.objects.get(organization=organization)
        self.assertEqual(settings_record.timezone, "Asia/Tehran")
        self.assertEqual(settings_record.currency, "IRR")

    def test_backfill_preserves_an_existing_authoritative_row(self) -> None:
        organization = Organization.objects.create(
            name="Existing Settings",
            slug="existing-settings",
            timezone="UTC",
            currency="USD",
        )
        settings_record = OrganizationSettings.objects.create(
            organization=organization,
            timezone="Asia/Tehran",
            currency="IRR",
        )

        self.migration.establish_settings_authority(apps, schema_editor=None)

        settings_record.refresh_from_db()
        self.assertEqual(settings_record.timezone, "Asia/Tehran")
        self.assertEqual(settings_record.currency, "IRR")

    def test_backfill_fails_closed_instead_of_converting_unsupported_currency(
        self,
    ) -> None:
        organization = Organization.objects.create(
            name="Unsupported Legacy Currency",
            slug="unsupported-legacy-currency",
            currency="USD",
        )

        with self.assertRaisesMessage(RuntimeError, str(organization.pk)):
            self.migration.establish_settings_authority(apps, schema_editor=None)

        self.assertFalse(
            OrganizationSettings.objects.filter(organization=organization).exists()
        )
