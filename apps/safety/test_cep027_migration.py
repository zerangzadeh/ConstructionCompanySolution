"""CEP-027 migration permission catalog check.

Legacy data backfill is reconciled against the development database. Rolling
back schemas inside pytest would revert unrelated application migrations.
"""

from django.test import TestCase

from apps.organizations.models import BusinessPermission


class RecordReviewMigrationTests(TestCase):
    def test_permission_catalog_is_present(self) -> None:
        codes = {
            "safety_incidents.record_submit",
            "safety_incidents.record_decide",
            "quality_issues.record_submit",
            "quality_issues.record_decide",
        }
        self.assertEqual(
            set(
                BusinessPermission.objects.filter(code__in=codes).values_list(
                    "code", flat=True
                )
            ),
            codes,
        )
