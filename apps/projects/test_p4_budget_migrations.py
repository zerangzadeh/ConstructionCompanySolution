from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase


class BudgetPreparationMigrationTests(TestCase):
    def assert_migration_contract(
        self, migration_name: str, expected_tables: tuple[str, ...]
    ) -> None:
        executor = MigrationExecutor(connection)
        migration = executor.loader.get_migration("projects", migration_name)

        self.assertTrue(all(operation.reversible for operation in migration.operations))
        self.assertIn(("projects", migration_name), executor.loader.applied_migrations)
        tables = set(connection.introspection.table_names())
        for table in expected_tables:
            self.assertIn(table, tables)

    def test_projects_budget_migration_is_reversible_and_applied(self) -> None:
        self.assert_migration_contract(
            "0006_p4_s07_s13_budget_preparation",
            ("projects_budgetversion", "projects_budgetallocation"),
        )

    def test_integrated_cost_migration_is_reversible_and_applied(self) -> None:
        self.assert_migration_contract(
            "0007_projectcostsourcecontract_projectcostfact_and_more",
            (
                "projects_projectcostsourcecontract",
                "projects_projectcostfact",
                "projects_projectcostforecast",
            ),
        )

    def test_schedule_control_migration_is_reversible_and_applied(self) -> None:
        self.assert_migration_contract(
            "0008_p4_s21_s25_schedule_change_controls",
            (
                "projects_projectschedulerevision",
                "projects_projectcontrolitem",
                "projects_schedulerebaselineproposal",
            ),
        )
