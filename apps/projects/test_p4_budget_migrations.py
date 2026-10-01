from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class BudgetPreparationMigrationTests(TransactionTestCase):
    reset_sequences = False

    def test_projects_budget_migration_rolls_back_and_reapplies(self) -> None:
        executor = MigrationExecutor(connection)
        executor.migrate([("projects", "0005_projectdocumentlink")])
        self.assertNotIn(
            "projects_budgetversion", connection.introspection.table_names()
        )

        executor = MigrationExecutor(connection)
        executor.migrate([("projects", "0006_p4_s07_s13_budget_preparation")])
        tables = connection.introspection.table_names()
        self.assertIn("projects_budgetversion", tables)
        self.assertIn("projects_budgetallocation", tables)

    def test_integrated_cost_migration_rolls_back_and_reapplies(self) -> None:
        executor = MigrationExecutor(connection)
        executor.migrate([("projects", "0006_p4_s07_s13_budget_preparation")])
        self.assertNotIn(
            "projects_projectcostfact", connection.introspection.table_names()
        )

        executor = MigrationExecutor(connection)
        executor.migrate(
            [("projects", "0007_projectcostsourcecontract_projectcostfact_and_more")]
        )
        tables = connection.introspection.table_names()
        self.assertIn("projects_projectcostsourcecontract", tables)
        self.assertIn("projects_projectcostfact", tables)
        self.assertIn("projects_projectcostforecast", tables)

    def test_schedule_control_migration_rolls_back_and_reapplies(self) -> None:
        executor = MigrationExecutor(connection)
        executor.migrate(
            [("projects", "0007_projectcostsourcecontract_projectcostfact_and_more")]
        )
        self.assertNotIn(
            "projects_projectschedulerevision", connection.introspection.table_names()
        )

        executor = MigrationExecutor(connection)
        executor.migrate([("projects", "0008_p4_s21_s25_schedule_change_controls")])
        tables = connection.introspection.table_names()
        self.assertIn("projects_projectschedulerevision", tables)
        self.assertIn("projects_projectcontrolitem", tables)
        self.assertIn("projects_schedulerebaselineproposal", tables)
