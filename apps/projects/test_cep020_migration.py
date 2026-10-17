"""Verify that historical forecast snapshots remain drafts through migration."""

from datetime import date
from decimal import Decimal

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from apps.accounts.models import User
from apps.organizations.models import BusinessPermission, Organization
from apps.projects.models import (
    BudgetVersion,
    CostStructureVersion,
    Project,
    ProjectCostForecast,
    ProjectForecastReview,
)


class ForecastReviewMigrationTests(TransactionTestCase):
    serialized_rollback = True

    def test_legacy_snapshot_survives_and_remains_draft(self) -> None:
        actor = User.objects.create_user(username="cep020-migration")
        organization = Organization.objects.create(
            name="CEP-020 migration", slug="cep020-migration"
        )
        project = Project.objects.create(
            organization=organization, code="MIG20", name="Forecast history"
        )
        structure = CostStructureVersion.objects.create(
            organization=organization,
            code="MIG20",
            version=1,
            name="Historic structure",
            governance_reference="CEP-020 test",
            created_by=actor,
        )
        budget = BudgetVersion.objects.create(
            organization=organization,
            project=project,
            structure_version=structure,
            version_number=1,
            handoff_id="MIG20",
            submission_version=1,
            currency="IRR",
            rounding_policy_reference="CEP-020 test",
            governance_reference="CEP-020 test",
            cost_center_required=False,
            reason="Historic forecast source",
            created_by=actor,
        )
        forecast = ProjectCostForecast.objects.create(
            organization=organization,
            project=project,
            budget=budget,
            version_number=1,
            cutoff_date=date(2026, 10, 1),
            currency="IRR",
            actual_cost=Decimal("10.00"),
            open_commitment=Decimal("5.00"),
            remaining_committed_etc=Decimal("5.00"),
            uncommitted_etc=Decimal("2.00"),
            eac=Decimal("17.00"),
            assumptions="Historic source assumptions",
            source_watermark="historic",
            created_by=actor,
        )
        previous = [("projects", "0009_projectsitedocumentlink")]
        current = [
            (
                "projects",
                "0010_projectforecastreview_projectforecasttransition_and_more",
            )
        ]
        try:
            MigrationExecutor(connection).migrate(previous)
            self.assertTrue(ProjectCostForecast.objects.filter(pk=forecast.pk).exists())
            MigrationExecutor(connection).migrate(current)
            review = ProjectForecastReview.objects.get(forecast_id=forecast.pk)
            self.assertEqual(review.status, "draft")
            self.assertIsNone(review.predecessor_id)
            self.assertEqual(
                ProjectForecastReview.objects.filter(forecast_id=forecast.pk).count(), 1
            )
        finally:
            MigrationExecutor(connection).migrate(current)

    def test_permission_catalog_migration_reverses_and_reapplies(self) -> None:
        codes = {
            "project_cost.forecasts_review",
            "project_cost.budget_overrides_approve",
        }
        previous = [("organizations", "0108_cep006_control_account_mapping_permission")]
        current = [("organizations", "0109_cep020_forecast_budget_control_permissions")]
        try:
            MigrationExecutor(connection).migrate(previous)
            self.assertFalse(BusinessPermission.objects.filter(code__in=codes).exists())
            MigrationExecutor(connection).migrate(current)
            self.assertEqual(
                set(
                    BusinessPermission.objects.filter(code__in=codes).values_list(
                        "code", flat=True
                    )
                ),
                codes,
            )
        finally:
            MigrationExecutor(connection).migrate(current)
