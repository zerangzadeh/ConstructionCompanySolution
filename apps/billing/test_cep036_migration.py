from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from apps.organizations.models import BusinessPermission, OrganizationRole

from . import test_cep036 as fixtures
from .models import IndexationCalculation, IndexationRuleVersion


class IndexationMigrationTests(TransactionTestCase):
    serialized_rollback = True

    def test_rollback_reapply_preserves_existing_contract_source(self):
        fixture = fixtures.IndexationTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        before = type(fixture.contract).objects.values().get(pk=fixture.contract.pk)
        codes = [
            "indexation_rules.manage",
            "indexation.calculate",
            "indexation.correct",
        ]
        # Synthetic explicit fixture grants are unrelated to migration defaults.
        OrganizationRole.permissions.through.objects.filter(
            businesspermission__code__in=codes
        ).delete()
        previous = [
            ("billing", "0015_p6_s26_s32_taxpayer_submission_snapshot"),
            ("organizations", "0113_cep056_certificate_permissions"),
        ]
        current = [
            ("billing", "0016_cep036_indexation"),
            ("organizations", "0114_cep036_indexation_permissions"),
        ]
        try:
            MigrationExecutor(connection).migrate(previous)
            self.assertFalse(
                BusinessPermission.objects.filter(
                    code__in=codes, is_active=True
                ).exists()
            )
            self.assertEqual(
                type(fixture.contract).objects.values().get(pk=fixture.contract.pk),
                before,
            )
            MigrationExecutor(connection).migrate(current)
            self.assertEqual(
                BusinessPermission.objects.filter(
                    code__in=codes, is_active=True
                ).count(),
                3,
            )
            self.assertFalse(
                OrganizationRole.permissions.through.objects.filter(
                    businesspermission__code__in=codes
                ).exists()
            )
            self.assertEqual(
                type(fixture.contract).objects.values().get(pk=fixture.contract.pk),
                before,
            )
            self.assertEqual(IndexationRuleVersion.objects.count(), 0)
            self.assertEqual(IndexationCalculation.objects.count(), 0)
        finally:
            MigrationExecutor(connection).migrate(current)
