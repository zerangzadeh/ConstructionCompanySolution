"""Bounded CEP-040 source-coverage acceptance and isolation regressions."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.projects import test_p4_budget_preparation as budget_helpers
from apps.projects import test_p4_s35_s37 as cost_helpers
from apps.projects.models import ProjectCostCoverageStatus, ProjectCostMeasure
from apps.projects.services import (
    create_project,
    export_project_cost_reconciliation,
    get_project_cost_reconciliation,
    set_project_cost_coverage,
)
from tests.retirement_fixtures import explicit_fixture_roles


class CEP040ReconciliationTests(TestCase):
    _draft = budget_helpers.BudgetPreparationTests._draft
    _classify_and_submit = budget_helpers.BudgetPreparationTests._classify_and_submit
    _contract = cost_helpers.ProjectCostHardeningTests._contract
    _fact = cost_helpers.ProjectCostHardeningTests._fact

    def setUp(self) -> None:
        native_create = budget_helpers.create_project

        def create_with_explicit_fixture_authority(**kwargs):
            explicit_fixture_roles(self.organization)
            explicit_fixture_roles(self.other_organization)
            return native_create(**kwargs)

        with patch.object(
            budget_helpers,
            "create_project",
            side_effect=create_with_explicit_fixture_authority,
        ):
            cost_helpers.ProjectCostHardeningTests.setUp(self)

    def _coverage(self, contract, *, project=None, watermark=""):
        return set_project_cost_coverage(
            organization=self.organization,
            project=project or self.project,
            actor=self.preparer,
            contract=contract,
            status=ProjectCostCoverageStatus.NOT_STARTED,
            watermark=watermark,
        )

    def _snapshot(self, *, project=None):
        return get_project_cost_reconciliation(
            organization=self.organization,
            project=project or self.project,
            actor=self.preparer,
        )

    def test_expected_source_without_facts_is_explicit_unknown_not_zero(self):
        contract = self._contract(ProjectCostMeasure.ACTUAL, "missing")
        coverage = self._coverage(contract)
        with CaptureQueriesContext(connection) as queries:
            snapshot = self._snapshot()
        self.assertEqual(len(snapshot.sources), 1)
        source = snapshot.sources[0]
        self.assertEqual(source.contract_id, str(contract.pk))
        self.assertTrue(source.missing_facts)
        self.assertEqual(source.fact_count, 0)
        self.assertIsNone(source.net_amount)
        self.assertIsNone(source.cutoff_at)
        self.assertIsNone(snapshot.inert_project_cost_actual_total)
        self.assertFalse(snapshot.coverage_complete)
        self.assertFalse(snapshot.source_equivalence_established)
        self.assertFalse(contract.facts.exists())
        coverage.refresh_from_db()
        self.assertIsNone(coverage.cutoff_at)
        writes = [
            query["sql"]
            for query in queries
            if query["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
        ]
        self.assertTrue(writes)
        self.assertTrue(all('"audit_auditevent"' in sql for sql in writes))

    def test_source_cutoff_and_missing_state_survive_export(self):
        contract = self._contract(ProjectCostMeasure.ACTUAL, "cutoff")
        coverage = self._coverage(contract, watermark="SOURCE-CUTOFF-V1")
        snapshot = self._snapshot()
        self.assertEqual(len(snapshot.sources), 1)
        source = snapshot.sources[0]
        self.assertEqual(source.cutoff_at, coverage.cutoff_at)
        self.assertEqual(source.watermark, coverage.watermark)
        self.assertTrue(source.missing_facts)
        payload = export_project_cost_reconciliation(
            organization=self.organization,
            project=self.project,
            actor=self.preparer,
        ).decode("utf-8-sig")
        self.assertIn(f"cutoff_at={coverage.cutoff_at.isoformat()}", payload)
        self.assertIn("facts=missing", payload)
        self.assertIn("watermark=SOURCE-CUTOFF-V1", payload)

    def test_present_source_retry_keeps_amount_count_and_exact_cutoff(self):
        contract = self._contract(ProjectCostMeasure.ACTUAL, "retry")
        kwargs = {
            "kind": "actual_recognized",
            "amount": "9.00",
            "occurrence": "CEP040-RETRY",
        }
        first = self._fact(contract, **kwargs)
        retried = self._fact(contract, **kwargs)
        coverage = self._coverage(contract, watermark="SOURCE-RETRY-V1")
        self.assertEqual(first.pk, retried.pk)
        snapshot = self._snapshot()
        self.assertEqual(len(snapshot.sources), 1)
        source = snapshot.sources[0]
        self.assertFalse(source.missing_facts)
        self.assertEqual(source.fact_count, 1)
        self.assertEqual(source.net_amount, Decimal("9.00"))
        self.assertEqual(source.cutoff_at, coverage.cutoff_at)
        self.assertEqual(snapshot.inert_project_cost_actual_total, first.amount)
        self.assertEqual(first.recognition_date, date(2026, 10, 1))

    def test_expectations_are_project_scoped_and_not_inferred_tenant_wide(self):
        other_project = create_project(
            organization=self.organization,
            actor=self.preparer,
            code="CEP040-OTHER",
            name="Other reconciliation project",
        )
        actual = self._contract(ProjectCostMeasure.ACTUAL, "other-project")
        self._coverage(actual, project=other_project, watermark="OTHER-PROJECT")
        commitment = self._contract(ProjectCostMeasure.COMMITMENT, "not-actual")
        self._coverage(commitment)
        self.assertEqual(self._snapshot().sources, ())
        self.assertIsNone(self._snapshot(project=other_project))
        with self.assertRaises(PermissionDenied):
            get_project_cost_reconciliation(
                organization=self.other_organization,
                project=self.project,
                actor=self.outsider,
            )

    def test_project_scoped_actor_cannot_read_another_project(self):
        from django.utils import timezone

        from apps.accounts.models import User
        from apps.organizations.models import (
            AuthorizationScopeType,
            MembershipRole,
            MembershipRoleAssignment,
            MembershipScopeGrant,
            MembershipStatus,
            OrganizationMembership,
            OrganizationRole,
        )

        user = User.objects.create_user(username="cep040-project-scoped")
        role = OrganizationRole.objects.get(
            organization__isnull=True, code=MembershipRole.COMPANY_OWNER
        )
        membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=user,
            role_definition=role,
            status=MembershipStatus.ACTIVE,
            authorization_migrated_at=timezone.now(),
        )
        MembershipRoleAssignment.objects.create(
            organization=self.organization,
            membership=membership,
            role=role,
            reason="Explicit bounded reconciliation test role",
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type=AuthorizationScopeType.PROJECT,
            project=self.project,
            reason="Only the authorized reconciliation project",
        )
        self.assertIsNotNone(
            get_project_cost_reconciliation(
                organization=self.organization, project=self.project, actor=user
            )
        )
        other_project = create_project(
            organization=self.organization,
            actor=self.preparer,
            code="CEP040-RESTRICTED",
            name="Outside actor scope",
        )
        with self.assertRaises(PermissionDenied):
            get_project_cost_reconciliation(
                organization=self.organization, project=other_project, actor=user
            )

    def test_observed_sources_without_coverage_remain_visible_and_unknown_cutoff(self):
        contract = self._contract(ProjectCostMeasure.ACTUAL, "observed")
        self._fact(
            contract,
            kind="actual_recognized",
            amount="7.00",
            occurrence="CEP040-OBSERVED",
        )
        missing = self._contract(ProjectCostMeasure.ACTUAL, "expected")
        self._coverage(missing)
        snapshot = self._snapshot()
        sources = {source.contract_id: source for source in snapshot.sources}
        self.assertEqual(set(sources), {str(contract.pk), str(missing.pk)})
        self.assertIsNone(sources[str(contract.pk)].cutoff_at)
        self.assertFalse(sources[str(contract.pk)].missing_facts)
        self.assertEqual(sources[str(contract.pk)].net_amount, Decimal("7.00"))
        self.assertIsNone(sources[str(missing.pk)].net_amount)
        self.assertEqual(snapshot.inert_project_cost_actual_total, Decimal("7.00"))
