from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, transaction
from django.test import TestCase
from django.urls import reverse

from apps.organizations.services import ACTIVE_ORGANIZATION_SESSION_KEY
from apps.projects import test_p4_budget_preparation as budget_helpers
from apps.projects.models import (
    ProjectCostCoverageStatus,
    ProjectCostFact,
    ProjectCostFactKind,
    ProjectCostMeasure,
)
from apps.projects.services import (
    accept_budget_version,
    approve_project_cost_source_contract,
    create_project_cost_forecast_draft,
    create_project_cost_source_contract,
    get_project_cost_projection,
    record_project_cost_fact,
    set_project_cost_coverage,
)


class IntegratedProjectCostTests(TestCase):
    _draft = budget_helpers.BudgetPreparationTests._draft
    _classify_and_submit = budget_helpers.BudgetPreparationTests._classify_and_submit

    def setUp(self) -> None:
        budget_helpers.BudgetPreparationTests.setUp(self)
        submitted = self._classify_and_submit(self._draft())
        self.budget = accept_budget_version(
            budget=submitted,
            actor=self.approver,
            approval_reason="Independent acceptance for integrated-cost tests",
        )

    def _contract(self, measure: str, *, maker=None, approver=None, suffix: str = ""):
        maker = maker or self.preparer
        approver = approver or self.approver
        contract = create_project_cost_source_contract(
            organization=self.organization,
            actor=maker,
            producer_key=f"test.{measure}{suffix}",
            version=1,
            measure=measure,
            source_model=f"test.{measure}",
            event_schema=f"{measure}.v1",
            classification_policy_reference="CLASSIFICATION-V1",
            recognition_policy_reference="RECOGNITION-V1",
            reconciliation_policy_reference="RECONCILIATION-V1",
            requires_financial_evidence=(measure != ProjectCostMeasure.COMMITMENT),
        )
        return approve_project_cost_source_contract(contract=contract, actor=approver)

    def _fact(self, contract, kind: str, amount: str, occurrence: str, **extra):
        return record_project_cost_fact(
            organization=self.organization,
            project=self.project,
            actor=self.preparer,
            contract=contract,
            kind=kind,
            source_id="SRC-1",
            source_version="1",
            source_line_id=extra.pop("source_line_id", occurrence),
            economic_event_id=extra.pop("economic_event_id", "EVENT-1"),
            occurrence_id=occurrence,
            recognition_date=date(2026, 10, 1),
            currency="IRR",
            amount=Decimal(amount),
            cbs_node=self.cbs,
            wbs_node=self.wbs,
            cost_center=self.cost_center,
            classification_version="CLASSIFICATION-V1",
            valuation_reference="VALUATION-V1",
            financial_evidence_reference=(
                "JOURNAL-EVIDENCE-1" if contract.requires_financial_evidence else ""
            ),
            **extra,
        )

    def test_contract_precedes_facts_is_idempotent_and_enforces_sod(self) -> None:
        draft = create_project_cost_source_contract(
            organization=self.organization,
            actor=self.preparer,
            producer_key="test.commitment",
            version=1,
            measure=ProjectCostMeasure.COMMITMENT,
            source_model="test.purchase_order",
            event_schema="po.v1",
            classification_policy_reference="CLASSIFICATION-V1",
            recognition_policy_reference="COMMITMENT-V1",
            reconciliation_policy_reference="RECONCILIATION-V1",
            requires_financial_evidence=False,
        )
        with self.assertRaises(PermissionDenied):
            approve_project_cost_source_contract(contract=draft, actor=self.preparer)
        with self.assertRaises(PermissionDenied):
            self._fact(
                draft,
                ProjectCostFactKind.COMMITMENT_AUTHORIZED,
                "600.00",
                "PO-1-AUTH",
            )
        approved = approve_project_cost_source_contract(
            contract=draft, actor=self.approver
        )
        first = self._fact(
            approved,
            ProjectCostFactKind.COMMITMENT_AUTHORIZED,
            "600.00",
            "PO-1-AUTH",
        )
        retry = self._fact(
            approved,
            ProjectCostFactKind.COMMITMENT_AUTHORIZED,
            "600.00",
            "PO-1-AUTH",
        )
        self.assertEqual(first.pk, retry.pk)
        with self.assertRaisesMessage(ValueError, "different payload"):
            self._fact(
                approved,
                ProjectCostFactKind.COMMITMENT_AUTHORIZED,
                "601.00",
                "PO-1-AUTH",
            )

    def test_commitment_actual_accrual_replacement_and_projection(self) -> None:
        commitment = self._contract(ProjectCostMeasure.COMMITMENT)
        accrual = self._contract(ProjectCostMeasure.ACCRUAL)
        actual = self._contract(ProjectCostMeasure.ACTUAL)
        self._fact(
            commitment, ProjectCostFactKind.COMMITMENT_AUTHORIZED, "600.00", "C-AUTH"
        )
        self._fact(
            commitment, ProjectCostFactKind.COMMITMENT_RELIEF, "200.00", "C-RELIEF"
        )
        accrued = self._fact(
            accrual, ProjectCostFactKind.ACCRUAL_RECOGNIZED, "200.00", "A-REC"
        )
        reversed_accrual = self._fact(
            accrual,
            ProjectCostFactKind.ACCRUAL_REVERSAL,
            "-200.00",
            "A-REV",
            reverses=accrued,
        )
        self.assertEqual(reversed_accrual.reverses_id, accrued.pk)
        self._fact(
            actual,
            ProjectCostFactKind.ACTUAL_RECOGNIZED,
            "210.00",
            "X-REC",
            replaces_accrual=accrued,
        )
        projection = get_project_cost_projection(
            organization=self.organization,
            project=self.project,
            actor=self.preparer,
        )
        self.assertEqual(projection.authorized_commitment, Decimal("600.00"))
        self.assertEqual(projection.open_commitment, Decimal("400.00"))
        self.assertEqual(projection.accrual, Decimal("0.00"))
        self.assertEqual(projection.actual_cost, Decimal("210.00"))
        self.assertFalse(projection.coverage_complete)

    def test_coverage_forecast_and_fail_closed_gates(self) -> None:
        commitment = self._contract(ProjectCostMeasure.COMMITMENT)
        self._fact(
            commitment, ProjectCostFactKind.COMMITMENT_AUTHORIZED, "600.00", "C2-AUTH"
        )
        self._fact(
            commitment, ProjectCostFactKind.COMMITMENT_RELIEF, "200.00", "C2-RELIEF"
        )
        with self.assertRaisesMessage(ValueError, "fail-closed"):
            set_project_cost_coverage(
                organization=self.organization,
                project=self.project,
                actor=self.preparer,
                contract=commitment,
                status=ProjectCostCoverageStatus.COMPLETE,
                watermark="PO:2026-10-01:42",
            )
        set_project_cost_coverage(
            organization=self.organization,
            project=self.project,
            actor=self.preparer,
            contract=commitment,
            status=ProjectCostCoverageStatus.PARTIAL,
            watermark="PO:2026-10-01:42",
            exception_note="Other approved producers are not activated.",
        )
        forecast = create_project_cost_forecast_draft(
            organization=self.organization,
            project=self.project,
            actor=self.preparer,
            cutoff_date=date(2026, 10, 1),
            uncommitted_etc=Decimal("300.00"),
            assumptions="Explicit remaining-work assumption",
        )
        self.assertEqual(forecast.remaining_committed_etc, Decimal("400.00"))
        self.assertEqual(forecast.eac, Decimal("700.00"))
        self.assertFalse(forecast.coverage_complete)
        with self.assertRaisesMessage(ValueError, "currency"):
            record_project_cost_fact(
                organization=self.organization,
                project=self.project,
                actor=self.preparer,
                contract=commitment,
                kind=ProjectCostFactKind.COMMITMENT_ADJUSTMENT,
                source_id="SRC",
                source_version="1",
                source_line_id="L2",
                economic_event_id="EVENT-1",
                occurrence_id="BAD-FX",
                recognition_date=date(2026, 10, 1),
                currency="USD",
                amount=Decimal("1.00"),
                cbs_node=self.cbs,
                wbs_node=self.wbs,
                cost_center=self.cost_center,
                classification_version="V1",
                valuation_reference="V1",
            )

    def test_cross_tenant_and_database_immutability(self) -> None:
        contract = self._contract(ProjectCostMeasure.COMMITMENT)
        fact = self._fact(
            contract,
            ProjectCostFactKind.COMMITMENT_AUTHORIZED,
            "10.00",
            "IMMUTABLE",
        )
        with self.assertRaises(PermissionDenied):
            record_project_cost_fact(
                organization=self.other_organization,
                project=self.project,
                actor=self.outsider,
                contract=contract,
                kind=ProjectCostFactKind.COMMITMENT_ADJUSTMENT,
                source_id="SRC",
                source_version="1",
                source_line_id="L",
                economic_event_id="E",
                occurrence_id="CROSS",
                recognition_date=date(2026, 10, 1),
                currency="IRR",
                amount=Decimal("1.00"),
                cbs_node=self.cbs,
                wbs_node=self.wbs,
                cost_center=self.cost_center,
                classification_version="V1",
                valuation_reference="V1",
            )
        with self.assertRaises(DatabaseError), transaction.atomic():
            ProjectCostFact.objects.filter(pk=fact.pk).update(amount=Decimal("11.00"))

    def test_project_detail_exposes_permission_scoped_incomplete_projection(
        self,
    ) -> None:
        self.client.force_login(self.preparer)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.organization.pk)
        session.save()
        response = self.client.get(
            reverse("projects:detail", kwargs={"project_id": self.project.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "هزینه یکپارچه پروژه")
        self.assertContains(response, "پوشش ناقص")
        self.assertNotContains(response, "پوشش کامل ثبت‌شده")
