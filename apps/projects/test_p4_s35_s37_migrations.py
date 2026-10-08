from importlib import import_module

from django.apps import apps
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase


class ProjectCostHardeningMigrationTests(TestCase):
    def test_permission_and_audit_migration_contracts_are_applied(self) -> None:
        permission_migration = import_module(
            "apps.organizations.migrations.0071_p4_s35_s37_reconciliation_permissions"
        )
        permission_model = apps.get_model("organizations", "BusinessPermission")

        permission_migration.reverse(apps, None)
        self.assertFalse(
            permission_model.objects.filter(
                code="project_cost.reconciliations_view"
            ).exists()
        )
        permission_migration.forward(apps, None)
        self.assertTrue(
            permission_model.objects.filter(
                code="project_cost.reconciliations_view"
            ).exists()
        )
        self.assertTrue(
            permission_model.objects.filter(
                code="project_cost.reconciliations_export"
            ).exists()
        )

        executor = MigrationExecutor(connection)
        self.assertIn(
            ("audit", "0051_p4_s35_s37_reconciliation_actions"),
            executor.loader.applied_migrations,
        )
        audit_event = apps.get_model("audit", "AuditEvent")
        actions = dict(audit_event._meta.get_field("action").choices)
        self.assertIn("project_cost.reconciliation_viewed", actions)
        self.assertIn("project_cost.reconciliation_exported", actions)
