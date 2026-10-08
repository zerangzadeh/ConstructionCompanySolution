from importlib import import_module

from django.apps import apps
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase


class ExpenseControlMigrationTests(TestCase):
    def test_expense_control_migration_is_reversible_and_applied(self) -> None:
        executor = MigrationExecutor(connection)
        migration = executor.loader.get_migration(
            "expenses", "0005_p4_s26_s30_expense_controls"
        )

        self.assertTrue(all(operation.reversible for operation in migration.operations))
        self.assertIn(
            ("expenses", "0005_p4_s26_s30_expense_controls"),
            executor.loader.applied_migrations,
        )
        tables = connection.introspection.table_names()
        self.assertIn("expenses_expenseallocation", tables)
        self.assertIn("expenses_expensebudgetassessment", tables)
        self.assertIn("expenses_recurringexpensetemplate", tables)

    def test_expense_permission_data_migrations_are_idempotent(self) -> None:
        permission_model = apps.get_model("organizations", "BusinessPermission")
        permission_model.objects.filter(code="expenses.recurrences_manage").delete()

        import_module(
            "apps.organizations.migrations.0068_p4_s26_s30_expense_permissions"
        ).forward(apps, None)
        import_module(
            "apps.organizations.migrations.0069_normalize_expense_recurrence_permission"
        ).forward(apps, None)

        self.assertTrue(
            permission_model.objects.filter(code="expenses.recurrences_manage").exists()
        )
        self.assertFalse(
            permission_model.objects.filter(code="expense_recurrences.manage").exists()
        )
