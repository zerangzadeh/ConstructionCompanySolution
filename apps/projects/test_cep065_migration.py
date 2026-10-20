"""Conditional expand/reverse/reapply preserves existing planning history."""

import json

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from apps.projects import test_cep020_forecast_budget_control as fixtures
from apps.projects.models import BudgetAllocation, BudgetVersion, ProjectCostForecast


class CashflowMigrationTests(TransactionTestCase):
    serialized_rollback = True
    setUp = fixtures.ForecastGovernanceTests.setUp
    _draft = fixtures.ForecastGovernanceTests._draft
    _classify_and_submit = fixtures.ForecastGovernanceTests._classify_and_submit
    _forecast = fixtures.ForecastGovernanceTests._forecast

    def test_reverse_reapply_retains_accepted_budget_and_forecast(self):
        forecast = self._forecast()

        def retained():
            return json.dumps(
                {
                    "budget": list(
                        BudgetVersion.objects.filter(pk=self.budget.pk).values()
                    ),
                    "allocations": list(
                        BudgetAllocation.objects.filter(
                            manifest_line__manifest__budget=self.budget
                        )
                        .order_by("pk")
                        .values()
                    ),
                    "forecast": list(
                        ProjectCostForecast.objects.filter(pk=forecast.pk).values()
                    ),
                },
                default=str,
                sort_keys=True,
            )

        before = retained()
        old = [
            (
                "projects",
                "0010_projectforecastreview_projectforecasttransition_and_more",
            )
        ]
        new = [("projects", "0011_cep065_cashflow_evidence")]
        try:
            MigrationExecutor(connection).migrate(old)
            self.assertNotIn(
                "projects_projectcashflowsupplement",
                connection.introspection.table_names(),
            )
            self.assertEqual(before, retained())
            MigrationExecutor(connection).migrate(new)
            self.assertIn(
                "projects_projectcashflowsnapshot",
                connection.introspection.table_names(),
            )
            self.assertEqual(before, retained())
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM pg_trigger WHERE tgname IN ('cashflow_supplement_insert', 'cashflow_supplement_immutable', 'cashflow_snapshot_immutable')"
                )
                self.assertEqual(cursor.fetchone()[0], 3)
        finally:
            MigrationExecutor(connection).migrate(new)
