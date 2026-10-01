from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from queue import Queue
from threading import Barrier

from django.core.exceptions import PermissionDenied
from django.db import close_old_connections, connection
from django.db.models import Sum
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.expenses.models import Expense
from apps.expenses.services import (
    add_expense_allocation,
    approve_expense,
    create_expense_draft,
    submit_expense,
)
from apps.organizations.authorization import permission_supports_object_scope
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermission,
    BusinessPermissionCode,
    MembershipRole,
    MembershipScopeGrant,
    MembershipStatus,
    Organization,
)
from apps.organizations.services import ACTIVE_ORGANIZATION_SESSION_KEY
from apps.projects import test_p4_budget_preparation as budget_helpers
from apps.projects.models import (
    Project,
    ProjectCostFact,
    ProjectCostFactKind,
    ProjectCostMeasure,
    ProjectCostSourceContract,
)
from apps.projects.services import (
    accept_budget_version,
    approve_project_cost_source_contract,
    create_project,
    create_project_cost_source_contract,
    export_project_cost_reconciliation,
    get_project_cost_reconciliation,
    record_project_cost_fact,
)


class ProjectCostHardeningTests(TestCase):
    _draft = budget_helpers.BudgetPreparationTests._draft
    _classify_and_submit = budget_helpers.BudgetPreparationTests._classify_and_submit

    def setUp(self) -> None:
        budget_helpers.BudgetPreparationTests.setUp(self)
        self.budget = accept_budget_version(
            budget=self._classify_and_submit(self._draft()),
            actor=self.approver,
            approval_reason="Independent acceptance for P4-S35–S37",
        )

    def _contract(self, measure: str, suffix: str):
        contract = create_project_cost_source_contract(
            organization=self.organization,
            actor=self.preparer,
            producer_key=f"p4.s35.{measure}.{suffix}",
            version=1,
            measure=measure,
            source_model=(
                "expenses.expense"
                if measure == ProjectCostMeasure.ACTUAL
                else "procurement.purchase_order"
            ),
            event_schema=f"{measure}.v1",
            classification_policy_reference="CLASSIFICATION-V1",
            recognition_policy_reference="RECOGNITION-V1",
            reconciliation_policy_reference="RECONCILIATION-V1",
            requires_financial_evidence=(measure == ProjectCostMeasure.ACTUAL),
        )
        return approve_project_cost_source_contract(
            contract=contract, actor=self.approver
        )

    def _fact(
        self,
        contract,
        *,
        kind: str,
        amount: str,
        occurrence: str,
        economic_event: str = "EVENT-1",
        **extra,
    ):
        return record_project_cost_fact(
            organization=self.organization,
            project=self.project,
            actor=self.preparer,
            contract=contract,
            kind=kind,
            source_id=extra.pop("source_id", "SOURCE-PRIVATE-1"),
            source_version="1",
            source_line_id=extra.pop("source_line_id", occurrence),
            economic_event_id=economic_event,
            occurrence_id=occurrence,
            recognition_date=date(2026, 10, 1),
            currency="IRR",
            amount=Decimal(amount),
            cbs_node=extra.pop("cbs_node", self.cbs),
            wbs_node=extra.pop("wbs_node", self.wbs),
            cost_center=extra.pop("cost_center", self.cost_center),
            classification_version="CLASSIFICATION-V1",
            valuation_reference="VALUATION-V1",
            financial_evidence_reference=(
                "FINANCIAL-EVIDENCE-1" if contract.requires_financial_evidence else ""
            ),
            **extra,
        )

    def _approved_expense(self, *, amount: str, suffix: str) -> Expense:
        expense = create_expense_draft(
            organization=self.organization,
            project=self.project,
            actor=self.preparer,
            description="Immutable approved expense evidence",
            amount=Decimal(amount),
            incurred_on=date(2026, 10, 1),
            source_reference=f"EXP-S35-{suffix}",
            idempotency_key=f"expense-s35-{suffix}",
        )
        add_expense_allocation(
            expense=expense,
            actor=self.preparer,
            project=self.project,
            wbs_node=self.wbs,
            cbs_node=self.cbs,
            cost_center=self.cost_center,
            amount=Decimal(amount),
            allocation_basis_reference="P4-S35 conserved coding",
        )
        submit_expense(expense=expense, actor=self.preparer)
        return approve_expense(expense=expense, actor=self.approver)

    def test_s35_conserves_idempotent_expense_and_coded_cost_reversal(self) -> None:
        expense = create_expense_draft(
            organization=self.organization,
            project=self.project,
            actor=self.preparer,
            description="Idempotent evidence",
            amount=Decimal("10.00"),
            incurred_on=date(2026, 10, 1),
            source_reference="EXP-IDEMPOTENT",
            idempotency_key="expense-idempotent",
        )
        retry = create_expense_draft(
            organization=self.organization,
            project=self.project,
            actor=self.preparer,
            description="Idempotent evidence",
            amount=Decimal("10.00"),
            incurred_on=date(2026, 10, 1),
            source_reference="EXP-IDEMPOTENT",
            idempotency_key="expense-idempotent",
        )
        self.assertEqual(expense.pk, retry.pk)
        with self.assertRaisesMessage(ValueError, "different payload"):
            create_expense_draft(
                organization=self.organization,
                project=self.project,
                actor=self.preparer,
                description="Conflicting retry",
                amount=Decimal("11.00"),
                incurred_on=date(2026, 10, 1),
                source_reference="EXP-IDEMPOTENT-OTHER",
                idempotency_key="expense-idempotent",
            )

        actual = self._contract(ProjectCostMeasure.ACTUAL, "reversal")
        original = self._fact(
            actual,
            kind=ProjectCostFactKind.ACTUAL_RECOGNIZED,
            amount="25.00",
            occurrence="ACTUAL-ORIGINAL",
        )
        other_wbs = budget_helpers.create_wbs_node(
            organization=self.organization,
            project=self.project,
            actor=self.preparer,
            code="W2",
            title="Other coded dimension",
        )
        with self.assertRaisesMessage(ValueError, "coded dimension"):
            self._fact(
                actual,
                kind=ProjectCostFactKind.ACTUAL_REVERSAL,
                amount="-25.00",
                occurrence="ACTUAL-BAD-REVERSAL",
                reverses=original,
                wbs_node=other_wbs,
            )
        reversal = self._fact(
            actual,
            kind=ProjectCostFactKind.ACTUAL_REVERSAL,
            amount="-25.00",
            occurrence="ACTUAL-REVERSAL",
            reverses=original,
        )
        self.assertEqual(reversal.reverses_id, original.pk)

    def test_s37_reconciliation_labels_incomplete_provenance_and_differences(
        self,
    ) -> None:
        self._approved_expense(amount="60.00", suffix="reconciliation")
        actual = self._contract(ProjectCostMeasure.ACTUAL, "reconciliation")
        commitment = self._contract(ProjectCostMeasure.COMMITMENT, "reconciliation")
        self._fact(
            actual,
            kind=ProjectCostFactKind.ACTUAL_RECOGNIZED,
            amount="50.00",
            occurrence="ACTUAL-RECONCILIATION",
        )
        self._fact(
            commitment,
            kind=ProjectCostFactKind.COMMITMENT_AUTHORIZED,
            amount="80.00",
            occurrence="COMMITMENT-EXCLUDED",
        )

        snapshot = get_project_cost_reconciliation(
            organization=self.organization,
            project=self.project,
            actor=self.preparer,
        )
        assert snapshot is not None
        self.assertFalse(snapshot.coverage_complete)
        self.assertFalse(snapshot.source_equivalence_established)
        self.assertEqual(snapshot.accepted_budget_total, Decimal("100.00"))
        self.assertEqual(snapshot.approved_or_recorded_expense_total, Decimal("60.00"))
        self.assertEqual(snapshot.inert_project_cost_actual_total, Decimal("50.00"))
        self.assertEqual(snapshot.unresolved_total_difference, Decimal("10.00"))
        self.assertEqual(len(snapshot.lines), 1)
        self.assertEqual(snapshot.lines[0].unresolved_difference, Decimal("10.00"))
        self.assertEqual(snapshot.sources[0].source_model, "expenses.expense")
        exclusions = {item.code: item for item in snapshot.exclusions}
        self.assertEqual(exclusions["non_actual_project_cost_fact"].count, 1)
        self.assertEqual(exclusions["actual_fact_without_budget_lineage"].count, 1)
        self.assertEqual(
            exclusions["actual_fact_without_budget_lineage"].disposition,
            "uncomparable",
        )

        payload = export_project_cost_reconciliation(
            organization=self.organization,
            project=self.project,
            actor=self.preparer,
        )
        self.assertIn(b"coverage,incomplete", payload)
        self.assertIn(b"source_equivalence,not_established", payload)
        self.assertNotIn(b"SOURCE-PRIVATE-1", payload)
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.PROJECT_COST_RECONCILIATION_VIEWED,
                organization=self.organization,
            ).exists()
        )
        export_audit = AuditEvent.objects.get(
            action=AuditAction.PROJECT_COST_RECONCILIATION_EXPORTED
        )
        self.assertEqual(export_audit.metadata["coverage"], "incomplete")

    def test_s37_missing_source_is_unknown_not_zero(self) -> None:
        actual = self._contract(ProjectCostMeasure.ACTUAL, "unknown")
        self._fact(
            actual,
            kind=ProjectCostFactKind.ACTUAL_RECOGNIZED,
            amount="15.00",
            occurrence="ACTUAL-WITHOUT-EXPENSE",
        )
        snapshot = get_project_cost_reconciliation(
            organization=self.organization,
            project=self.project,
            actor=self.preparer,
        )
        assert snapshot is not None
        self.assertIsNone(snapshot.approved_or_recorded_expense_total)
        self.assertIsNone(snapshot.unresolved_total_difference)
        self.assertIsNone(snapshot.lines[0].approved_or_recorded_expense_amount)
        self.assertIsNone(snapshot.lines[0].unresolved_difference)

    def test_permissions_tenant_and_object_scope_are_fail_closed(self) -> None:
        viewer = User.objects.create_user(username="p4-s37-viewer")
        self.organization.memberships.create(
            user=viewer,
            role=MembershipRole.VIEWER,
            status=MembershipStatus.ACTIVE,
        )
        with self.assertRaises(PermissionDenied):
            get_project_cost_reconciliation(
                organization=self.organization,
                project=self.project,
                actor=viewer,
            )
        with self.assertRaises(PermissionDenied):
            get_project_cost_reconciliation(
                organization=self.other_organization,
                project=self.project,
                actor=self.outsider,
            )

        scoped_user = User.objects.create_user(username="p4-s37-scoped")
        membership = self.organization.memberships.create(
            user=scoped_user,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type=AuthorizationScopeType.PROJECT,
            project=self.project,
            reason="P4-S37 reconciliation scope",
        )
        self.assertIsNotNone(
            get_project_cost_reconciliation(
                organization=self.organization,
                project=self.project,
                actor=scoped_user,
            )
        )
        other_project = create_project(
            organization=self.organization,
            actor=self.preparer,
            code="P4-S37-OTHER",
            name="Other project",
        )
        with self.assertRaises(PermissionDenied):
            get_project_cost_reconciliation(
                organization=self.organization,
                project=other_project,
                actor=scoped_user,
            )

    def test_reconciliation_query_count_is_bounded_and_does_not_mutate_sources(
        self,
    ) -> None:
        self._approved_expense(amount="10.00", suffix="query-1")
        actual = self._contract(ProjectCostMeasure.ACTUAL, "query")
        self._fact(
            actual,
            kind=ProjectCostFactKind.ACTUAL_RECOGNIZED,
            amount="9.00",
            occurrence="ACTUAL-QUERY-1",
        )
        with CaptureQueriesContext(connection) as initial_queries:
            get_project_cost_reconciliation(
                organization=self.organization,
                project=self.project,
                actor=self.preparer,
            )
        source_counts = (
            Expense.objects.count(),
            ProjectCostFact.objects.count(),
        )
        for index in range(2, 7):
            self._approved_expense(amount="10.00", suffix=f"query-{index}")
            self._fact(
                actual,
                kind=ProjectCostFactKind.ACTUAL_RECOGNIZED,
                amount="9.00",
                occurrence=f"ACTUAL-QUERY-{index}",
                economic_event=f"EVENT-{index}",
            )
        with CaptureQueriesContext(connection) as expanded_queries:
            get_project_cost_reconciliation(
                organization=self.organization,
                project=self.project,
                actor=self.preparer,
            )
        self.assertEqual(len(initial_queries), len(expanded_queries))
        self.assertLessEqual(len(expanded_queries), 20)
        self.assertEqual(Expense.objects.count(), source_counts[0] + 5)
        self.assertEqual(ProjectCostFact.objects.count(), source_counts[1] + 5)

    def test_runtime_ui_and_permission_catalog_are_available(self) -> None:
        self.assertTrue(
            permission_supports_object_scope(
                BusinessPermissionCode.PROJECT_COST_RECONCILIATIONS_VIEW
            )
        )
        self.assertTrue(
            BusinessPermission.objects.filter(
                code=BusinessPermissionCode.PROJECT_COST_RECONCILIATIONS_VIEW
            ).exists()
        )
        self.assertTrue(
            BusinessPermission.objects.filter(
                code=BusinessPermissionCode.PROJECT_COST_RECONCILIATIONS_EXPORT
            ).exists()
        )
        self.client.force_login(self.preparer)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.organization.pk)
        session.save()
        response = self.client.get(
            reverse("projects:cost_reconciliation", args=[self.project.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "پوشش همواره ناقص است")
        export = self.client.get(
            reverse("projects:cost_reconciliation_export", args=[self.project.pk])
        )
        self.assertEqual(export.status_code, 200)
        self.assertEqual(export["X-Content-Type-Options"], "nosniff")


class ProjectCostConcurrencyTests(TransactionTestCase):
    reset_sequences = False
    setUp = budget_helpers.BudgetPreparationTests.setUp
    _draft = budget_helpers.BudgetPreparationTests._draft
    _classify_and_submit = budget_helpers.BudgetPreparationTests._classify_and_submit

    def _parallel(self, operations):
        barrier = Barrier(len(operations))
        outcomes: Queue[tuple[str, object]] = Queue()

        def runner(operation) -> None:
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    outcomes.put(("ok", operation()))
                except Exception as exc:  # noqa: BLE001 - race outcome is asserted
                    outcomes.put(("error", exc))
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=len(operations)) as pool:
            futures = [pool.submit(runner, operation) for operation in operations]
            for future in futures:
                future.result(timeout=30)
        return [outcomes.get_nowait() for _ in operations]

    def test_s36_concurrent_idempotency_and_commitment_cap_are_serialized(self) -> None:
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL row-lock semantics are required.")
        budget = self._classify_and_submit(self._draft())
        accept_budget_version(
            budget=budget,
            actor=self.approver,
            approval_reason="Concurrent P4-S36 budget",
        )

        def create_same_expense() -> str:
            expense = create_expense_draft(
                organization=Organization.objects.get(pk=self.organization.pk),
                project=Project.objects.get(pk=self.project.pk),
                actor=User.objects.get(pk=self.preparer.pk),
                description="Concurrent idempotent evidence",
                amount=Decimal("10.00"),
                incurred_on=date(2026, 10, 1),
                source_reference="EXP-CONCURRENT",
                idempotency_key="expense-concurrent",
            )
            return str(expense.pk)

        outcomes = self._parallel((create_same_expense, create_same_expense))
        self.assertTrue(all(status == "ok" for status, _ in outcomes), outcomes)
        self.assertEqual(len({value for _, value in outcomes}), 1)
        self.assertEqual(
            Expense.objects.filter(idempotency_key="expense-concurrent").count(), 1
        )

        def create_same_contract() -> str:
            source_contract = create_project_cost_source_contract(
                organization=Organization.objects.get(pk=self.organization.pk),
                actor=User.objects.get(pk=self.preparer.pk),
                producer_key="p4.s36.commitment",
                version=1,
                measure=ProjectCostMeasure.COMMITMENT,
                source_model="procurement.purchase_order",
                event_schema="commitment.v1",
                classification_policy_reference="CLASSIFICATION-V1",
                recognition_policy_reference="RECOGNITION-V1",
                reconciliation_policy_reference="RECONCILIATION-V1",
                requires_financial_evidence=False,
            )
            return str(source_contract.pk)

        contract_outcomes = self._parallel((create_same_contract, create_same_contract))
        self.assertTrue(
            all(status == "ok" for status, _ in contract_outcomes),
            contract_outcomes,
        )
        self.assertEqual(len({value for _, value in contract_outcomes}), 1)
        contract = ProjectCostSourceContract.objects.get(pk=contract_outcomes[0][1])
        contract = approve_project_cost_source_contract(
            contract=contract, actor=self.approver
        )
        record_project_cost_fact(
            organization=self.organization,
            project=self.project,
            actor=self.preparer,
            contract=contract,
            kind=ProjectCostFactKind.COMMITMENT_AUTHORIZED,
            source_id="PO-1",
            source_version="1",
            source_line_id="PO-1-L1",
            economic_event_id="PO-1",
            occurrence_id="PO-1-AUTH",
            recognition_date=date(2026, 10, 1),
            currency="IRR",
            amount=Decimal("100.00"),
            cbs_node=self.cbs,
            wbs_node=self.wbs,
            cost_center=self.cost_center,
            classification_version="CLASSIFICATION-V1",
            valuation_reference="VALUATION-V1",
        )

        def relieve(suffix: str) -> str:
            fact = record_project_cost_fact(
                organization=Organization.objects.get(pk=self.organization.pk),
                project=Project.objects.get(pk=self.project.pk),
                actor=User.objects.get(pk=self.preparer.pk),
                contract=contract.__class__.objects.get(pk=contract.pk),
                kind=ProjectCostFactKind.COMMITMENT_RELIEF,
                source_id="PO-1",
                source_version="1",
                source_line_id=f"RELIEF-{suffix}",
                economic_event_id="PO-1",
                occurrence_id=f"PO-1-RELIEF-{suffix}",
                recognition_date=date(2026, 10, 1),
                currency="IRR",
                amount=Decimal("60.00"),
                cbs_node=self.cbs.__class__.objects.get(pk=self.cbs.pk),
                wbs_node=self.wbs.__class__.objects.get(pk=self.wbs.pk),
                cost_center=self.cost_center.__class__.objects.get(
                    pk=self.cost_center.pk
                ),
                classification_version="CLASSIFICATION-V1",
                valuation_reference="VALUATION-V1",
            )
            return str(fact.pk)

        outcomes = self._parallel((lambda: relieve("A"), lambda: relieve("B")))
        self.assertEqual(sum(status == "ok" for status, _ in outcomes), 1, outcomes)
        self.assertEqual(sum(status == "error" for status, _ in outcomes), 1, outcomes)
        self.assertEqual(
            ProjectCostFact.objects.filter(
                economic_event_id="PO-1",
                kind=ProjectCostFactKind.COMMITMENT_RELIEF,
            ).aggregate(total=Sum("amount"))["total"],
            Decimal("60.00"),
        )
