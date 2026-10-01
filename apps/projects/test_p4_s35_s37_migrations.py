from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class ProjectCostHardeningMigrationTests(TransactionTestCase):
    reset_sequences = False

    def test_permission_and_audit_migrations_roll_back_and_reapply(self) -> None:
        executor = MigrationExecutor(connection)
        executor.migrate(
            [("organizations", "0070_p4_s31_s34_project_controls_permissions")]
        )
        old_apps = executor.loader.project_state(
            [("organizations", "0070_p4_s31_s34_project_controls_permissions")]
        ).apps
        Permission = old_apps.get_model("organizations", "BusinessPermission")
        self.assertFalse(
            Permission.objects.filter(code="project_cost.reconciliations_view").exists()
        )

        executor = MigrationExecutor(connection)
        executor.migrate(
            [("organizations", "0071_p4_s35_s37_reconciliation_permissions")]
        )
        new_apps = executor.loader.project_state(
            [("organizations", "0071_p4_s35_s37_reconciliation_permissions")]
        ).apps
        Permission = new_apps.get_model("organizations", "BusinessPermission")
        self.assertTrue(
            Permission.objects.filter(code="project_cost.reconciliations_view").exists()
        )
        self.assertTrue(
            Permission.objects.filter(
                code="project_cost.reconciliations_export"
            ).exists()
        )

        executor = MigrationExecutor(connection)
        executor.migrate([("audit", "0050_p4_s31_s34_project_control_export_action")])
        executor = MigrationExecutor(connection)
        executor.migrate([("audit", "0051_p4_s35_s37_reconciliation_actions")])
        audit_apps = executor.loader.project_state(
            [("audit", "0051_p4_s35_s37_reconciliation_actions")]
        ).apps
        AuditEvent = audit_apps.get_model("audit", "AuditEvent")
        actions = dict(AuditEvent._meta.get_field("action").choices)
        self.assertIn("project_cost.reconciliation_viewed", actions)
        self.assertIn("project_cost.reconciliation_exported", actions)
