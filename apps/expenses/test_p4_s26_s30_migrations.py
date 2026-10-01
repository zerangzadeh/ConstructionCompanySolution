from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class ExpenseControlMigrationTests(TransactionTestCase):
    reset_sequences = False

    def test_expense_control_migration_rolls_back_and_reapplies(self) -> None:
        executor = MigrationExecutor(connection)
        executor.migrate([("expenses", "0004_expensedocumentlink")])
        self.assertNotIn("expenses_expenseallocation", connection.introspection.table_names())

        executor = MigrationExecutor(connection)
        executor.migrate([("expenses", "0005_p4_s26_s30_expense_controls")])
        tables = connection.introspection.table_names()
        self.assertIn("expenses_expenseallocation", tables)
        self.assertIn("expenses_expensebudgetassessment", tables)
        self.assertIn("expenses_recurringexpensetemplate", tables)

    def test_expense_permission_migration_rolls_back_and_reapplies(self) -> None:
        executor = MigrationExecutor(connection)
        executor.migrate([("organizations", "0067_p4_s21_s25_project_control_permissions")])
        old_apps = executor.loader.project_state(
            [("organizations", "0067_p4_s21_s25_project_control_permissions")]
        ).apps
        Permission = old_apps.get_model("organizations", "BusinessPermission")
        Permission.objects.filter(code="expenses.recurrences_manage").delete()
        self.assertFalse(Permission.objects.filter(code="expenses.recurrences_manage").exists())

        executor = MigrationExecutor(connection)
        executor.migrate([("organizations", "0069_normalize_expense_recurrence_permission")])
        new_apps = executor.loader.project_state(
            [("organizations", "0069_normalize_expense_recurrence_permission")]
        ).apps
        Permission = new_apps.get_model("organizations", "BusinessPermission")
        self.assertTrue(Permission.objects.filter(code="expenses.recurrences_manage").exists())
        self.assertFalse(Permission.objects.filter(code="expense_recurrences.manage").exists())
