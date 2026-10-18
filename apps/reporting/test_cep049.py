"""CEP-049 Project Controls read-model and source-lineage checks."""

import os
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase
from django.urls import reverse

from apps.projects.models import (
    BudgetAllocation,
    Project,
    ProjectCostFact,
    ProjectCostFactKind,
)
from apps.reporting.services import (
    _budget,
    _cost,
    drillthrough_manifest,
    refresh_metric,
)
from apps.reporting.test_p10_s02_s06 import P10S02S06AcceptanceTests


class ProjectControlsAdapterTests(SimpleTestCase):
    def test_commitment_relief_is_subtracted_and_versions_are_pinned(self) -> None:
        project_id = uuid4()
        facts = [
            (uuid4(), project_id, ProjectCostFactKind.COMMITMENT_AUTHORIZED,
             Decimal("100.00"), "IRR", "PO-1", "1", "L1", "po", 1),
            (uuid4(), project_id, ProjectCostFactKind.COMMITMENT_ADJUSTMENT,
             Decimal("20.00"), "IRR", "PO-1", "2", "L1", "po", 1),
            (uuid4(), project_id, ProjectCostFactKind.COMMITMENT_RELIEF,
             Decimal("30.00"), "IRR", "PO-1", "3", "L1", "po", 1),
        ]
        rows = MagicMock()
        rows.order_by.return_value.values_list.return_value = facts
        projects = MagicMock()
        projects.count.return_value = 1
        with patch("apps.reporting.services.ProjectCostFact.objects.filter", return_value=rows) as source:
            result = _cost(object(), projects, actual=False)
        self.assertEqual(result.value, {"amount": "90.00"})
        self.assertEqual(result.coverage["source_count"], 3)
        self.assertFalse(result.coverage["complete"])
        self.assertEqual(
            [item["source_version"] for item in result.sources["source_versions"]],
            ["1", "2", "3"],
        )
        self.assertEqual(len(result.sources["ids"]), 3)
        self.assertIn("recognition_date__lte", source.call_args.kwargs)

    def test_actual_reversal_and_mixed_currency_fail_closed(self) -> None:
        project_id = uuid4()
        facts = [
            (uuid4(), project_id, ProjectCostFactKind.ACTUAL_RECOGNIZED,
             Decimal("50.00"), "IRR", "BILL", "1", "L1", "bill", 2),
            (uuid4(), project_id, ProjectCostFactKind.ACTUAL_REVERSAL,
             Decimal("-10.00"), "IRR", "BILL", "2", "L1", "bill", 2),
        ]
        rows = MagicMock()
        rows.order_by.return_value.values_list.return_value = facts
        projects = MagicMock()
        projects.count.return_value = 1
        with patch("apps.reporting.services.ProjectCostFact.objects.filter", return_value=rows):
            result = _cost(object(), projects, actual=True)
            self.assertEqual(result.value["amount"], "40.00")
            rows.order_by.return_value.values_list.return_value = [
                *facts, (uuid4(), project_id, ProjectCostFactKind.ACTUAL_RECOGNIZED,
                         Decimal("5.00"), "USD", "BILL-2", "1", "L2", "bill", 2),
            ]
            mixed = _cost(object(), projects, actual=True)
        self.assertIsNone(mixed.value["amount"])
        self.assertEqual(mixed.currency, "")

    def test_only_governing_accepted_budget_lines_are_queried(self) -> None:
        budget_id = uuid4()
        project_id = uuid4()
        lines = [(uuid4(), Decimal("70.00"), budget_id, 2, "IRR", project_id)]
        rows = MagicMock()
        rows.order_by.return_value.values_list.return_value = lines
        projects = MagicMock()
        projects.count.return_value = 1
        with patch("apps.reporting.services.BudgetAllocation.objects.filter", return_value=rows) as source:
            result = _budget(object(), projects)
        self.assertEqual(result.value["amount"], "70.00")
        self.assertEqual(result.sources["budget_versions"], [f"{budget_id}:v2"])
        self.assertEqual(result.currency, "IRR")
        self.assertIn("manifest_line__manifest__budget__status", source.call_args.kwargs)
        projects.count.return_value = 2
        with patch("apps.reporting.services.BudgetAllocation.objects.filter", return_value=rows):
            missing_project = _budget(object(), projects)
        self.assertIsNone(missing_project.value["amount"])
        projects.count.return_value = 1
        rows.order_by.return_value.values_list.return_value = [
            *lines, (uuid4(), Decimal("10.00"), uuid4(), 1, "USD", project_id)
        ]
        with patch("apps.reporting.services.BudgetAllocation.objects.filter", return_value=rows):
            mixed = _budget(object(), projects)
        self.assertIsNone(mixed.value["amount"])
        self.assertFalse(mixed.coverage["complete"])


class ProjectControlsRuntimeTests(P10S02S06AcceptanceTests):
    """Reuse the governed P10 tenant, permission and versioned-result fixture."""

    def test_cep049_empty_cost_is_traceable_and_incomplete(self) -> None:
        source_counts = (BudgetAllocation.objects.count(), ProjectCostFact.objects.count())
        result = refresh_metric(
            organization=self.organization,
            actor=self.user,
            metric_code="committed_cost",
            idempotency_key="cep049-empty-cost",
            project=self.project_a,
        )
        self.assertIsNone(result.value["amount"])
        self.assertEqual(result.source_manifest["source_versions"], [])
        self.assertFalse(result.coverage["complete"])
        self.assertEqual(result.coverage["eligible_projects"], 1)
        self.assertEqual(result.run.metric_version.version, 1)
        self.assertEqual(
            (BudgetAllocation.objects.count(), ProjectCostFact.objects.count()),
            source_counts,
        )

    def test_cep049_cross_tenant_project_denied_before_aggregation(self) -> None:
        foreign_project = Project.objects.create(
            organization=self.other_organization,
            code="OTHER-CEP049",
            name="Other",
            created_by=self.other_user,
            updated_by=self.other_user,
        )
        with self.assertRaises(PermissionDenied):
            refresh_metric(
                organization=self.organization,
                actor=self.user,
                metric_code="approved_budget",
                idempotency_key="cep049-cross-tenant",
                project=foreign_project,
            )

    def test_cep049_drillthrough_template_shows_coverage_and_version(self) -> None:
        result = refresh_metric(
            organization=self.organization,
            actor=self.user,
            metric_code="actual_cost_coverage",
            idempotency_key="cep049-drill",
            project=self.project_a,
        )
        visible = drillthrough_manifest(
            organization=self.organization, actor=self.user, result_id=str(result.pk)
        )
        self.assertEqual(visible.pk, result.pk)
        self.client.force_login(self.user)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()
        response = self.client.get(
            reverse("reporting:drillthrough", kwargs={"result_id": result.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "پوشش کامل منابع کنترل پروژه هنوز تأیید نشده است")
        self.assertContains(response, "نسخه 1")
        if screenshot_html := os.environ.get("CEP049_SCREENSHOT_HTML"):
            Path(screenshot_html).write_bytes(response.content)
