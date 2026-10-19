from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.test import TestCase

from apps.accounting.models import JournalEntry
from apps.accounts.models import User
from apps.contracts.models import Contract
from apps.estimates.services import (
    add_estimate_item,
    approve_estimate,
    create_estimate,
)
from apps.expenses.models import Expense
from apps.organizations.models import (
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationSettings,
)
from apps.projects.models import BudgetVersionStatus
from apps.projects.services import (
    BudgetAllocationInput,
    accept_budget_version,
    add_cbs_node,
    add_cost_center,
    classify_budget_manifest_line,
    create_budget_draft_from_estimate,
    create_cost_structure_version,
    create_project,
    create_wbs_node,
    get_budget_plan_evidence,
    lock_cost_structure_version,
    submit_budget_version,
)
from apps.subledgers.models import Obligation, SettlementAllocation
from apps.treasury.models import TreasuryMovement


class BudgetPreparationTests(TestCase):
    def setUp(self) -> None:
        self.preparer = User.objects.create_user(username="budget-preparer")
        self.approver = User.objects.create_user(username="budget-approver")
        self.outsider = User.objects.create_user(username="budget-outsider")
        self.organization = Organization.objects.create(
            name="Budget Org", slug="budget-org"
        )
        self.other_organization = Organization.objects.create(
            name="Other Org", slug="other-org"
        )
        OrganizationSettings.objects.create(
            organization=self.organization, currency="IRR"
        )
        OrganizationSettings.objects.create(
            organization=self.other_organization, currency="IRR"
        )
        for user in (self.preparer, self.approver):
            self.organization.memberships.create(
                user=user,
                role=MembershipRole.COMPANY_OWNER,
                status=MembershipStatus.ACTIVE,
            )
        self.other_organization.memberships.create(
            user=self.outsider,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.project = create_project(
            organization=self.organization,
            actor=self.preparer,
            code="BUDGET",
            name="Budget Project",
            estimated_budget=Decimal("999.00"),
            actual_budget=Decimal("111.00"),
        )
        self.wbs = create_wbs_node(
            organization=self.organization,
            project=self.project,
            actor=self.preparer,
            code="W1",
            title="Work",
        )
        self.estimate = create_estimate(
            organization=self.organization,
            project=self.project,
            actor=self.preparer,
            estimate_number="EST-BUDGET",
            title="Accepted estimate source",
        )
        add_estimate_item(
            estimate=self.estimate,
            actor=self.preparer,
            description="Included line",
            quantity=Decimal(2),
            unit_price=Decimal("50.00"),
        )
        add_estimate_item(
            estimate=self.estimate,
            actor=self.preparer,
            description="Excluded line",
            quantity=Decimal(1),
            unit_price=Decimal("25.00"),
        )
        approve_estimate(estimate=self.estimate, actor=self.preparer)
        self.estimate.refresh_from_db()
        self.revision = self.estimate.current_revision
        self.structure = create_cost_structure_version(
            organization=self.organization,
            actor=self.preparer,
            code="CBS",
            version=1,
            name="Approved planning structure",
            governance_reference="PO-G07-EXPLICIT",
        )
        self.cbs = add_cbs_node(
            structure=self.structure,
            actor=self.preparer,
            code="C1",
            name="Direct cost",
        )
        self.cost_center = add_cost_center(
            structure=self.structure,
            actor=self.preparer,
            code="CC1",
            name="Project responsibility",
        )
        lock_cost_structure_version(structure=self.structure, actor=self.preparer)
        self.structure.refresh_from_db()

    def _draft(self, handoff_id: str = "HANDOFF-1"):
        return create_budget_draft_from_estimate(
            organization=self.organization,
            project=self.project,
            actor=self.preparer,
            estimate_revision=self.revision,
            structure=self.structure,
            handoff_id=handoff_id,
            submission_version=1,
            governance_reference="PO-G06-EXPLICIT",
            rounding_policy_reference="IRR-STORAGE-DECIMAL-2",
            cost_center_required=True,
            reason="Initial accepted estimate handoff",
        )

    def _classify_and_submit(self, budget):
        lines = list(budget.source_manifest.lines.order_by("source_amount"))
        classify_budget_manifest_line(
            line=lines[0],
            actor=self.preparer,
            exclusion_reason="Explicitly outside this internal cost scope",
        )
        classify_budget_manifest_line(
            line=lines[1],
            actor=self.preparer,
            allocations=(
                BudgetAllocationInput(
                    amount=Decimal("60.00"),
                    cbs_node=self.cbs,
                    wbs_node=self.wbs,
                    cost_center=self.cost_center,
                    allocation_basis_reference="reviewed split A",
                ),
                BudgetAllocationInput(
                    amount=Decimal("40.00"),
                    cbs_node=self.cbs,
                    wbs_node=self.wbs,
                    cost_center=self.cost_center,
                    allocation_basis_reference="reviewed split B",
                ),
            ),
        )
        return submit_budget_version(budget=budget, actor=self.preparer)

    def test_complete_manifest_conserves_source_and_exposes_planning_evidence(
        self,
    ) -> None:
        budget = self._classify_and_submit(self._draft())
        evidence = get_budget_plan_evidence(budget=budget, actor=self.preparer)
        self.assertEqual(evidence.source_total, Decimal("100.00"))
        self.assertEqual(evidence.accepted_total, Decimal("100.00"))
        self.assertEqual(evidence.pending_lines, 0)
        self.assertEqual(evidence.excluded_lines, 1)
        self.assertEqual(evidence.currency, "IRR")
        self.assertEqual(evidence.source_revision_id, str(self.revision.pk))

    def test_missing_mapping_and_non_conserving_split_fail_closed(self) -> None:
        budget = self._draft()
        line = budget.source_manifest.lines.order_by("-source_amount").first()
        with self.assertRaisesMessage(ValueError, "conserve"):
            classify_budget_manifest_line(
                line=line,
                actor=self.preparer,
                allocations=(
                    BudgetAllocationInput(
                        amount=Decimal("99.99"),
                        cbs_node=self.cbs,
                        wbs_node=self.wbs,
                        cost_center=self.cost_center,
                        allocation_basis_reference="incomplete",
                    ),
                ),
            )
        with self.assertRaisesMessage(ValueError, "explicit disposition"):
            submit_budget_version(budget=budget, actor=self.preparer)

    def test_missing_authoritative_currency_fails_at_product_owner_gate(self) -> None:
        self.organization.settings.delete()
        with self.assertRaisesMessage(ValueError, "P4-G08"):
            self._draft()

    def test_tenant_object_permission_and_sod_fail_closed(self) -> None:
        with self.assertRaises(PermissionDenied):
            create_budget_draft_from_estimate(
                organization=self.organization,
                project=self.project,
                actor=self.outsider,
                estimate_revision=self.revision,
                structure=self.structure,
                handoff_id="DENIED",
                submission_version=1,
                governance_reference="x",
                rounding_policy_reference="x",
                cost_center_required=True,
                reason="x",
            )
        budget = self._classify_and_submit(self._draft())
        with self.assertRaisesMessage(PermissionDenied, "self-approval"):
            accept_budget_version(
                budget=budget,
                actor=self.preparer,
                approval_reason="not independent",
            )

    def test_idempotent_handoff_and_stale_predecessor_conflict(self) -> None:
        first = self._draft("IDEMPOTENT")
        retry = self._draft("IDEMPOTENT")
        self.assertEqual(first.pk, retry.pk)
        first = self._classify_and_submit(first)
        accepted = accept_budget_version(
            budget=first,
            actor=self.approver,
            approval_reason="Independent review complete",
        )
        self.assertEqual(
            accept_budget_version(
                budget=accepted,
                actor=self.approver,
                approval_reason="retry",
            ).pk,
            accepted.pk,
        )

        stale = self._draft("STALE")
        stale = self._classify_and_submit(stale)
        with self.assertRaisesMessage(ValueError, "predecessor is stale"):
            accept_budget_version(
                budget=stale,
                actor=self.approver,
                approval_reason="would race governing pointer",
            )

    def test_accepted_baseline_and_payload_are_database_immutable(self) -> None:
        budget = accept_budget_version(
            budget=self._classify_and_submit(self._draft()),
            actor=self.approver,
            approval_reason="Independent review complete",
        )
        budget.reason = "rewrite"
        with self.assertRaises(ValidationError):
            budget.save()
        line = budget.source_manifest.lines.filter(disposition="included").first()
        with self.assertRaises(DatabaseError), transaction.atomic():
            type(line).objects.filter(pk=line.pk).update(source_amount=Decimal("1.00"))

    def test_acceptance_does_not_mutate_financial_or_legacy_authorities(self) -> None:
        models = (
            JournalEntry,
            TreasuryMovement,
            Obligation,
            SettlementAllocation,
            Expense,
            TreasuryMovement,
            Contract,
        )
        before = {model: model.objects.count() for model in models}
        estimate_total = self.revision.total_amount
        legacy_totals = (self.project.estimated_budget, self.project.actual_budget)
        accept_budget_version(
            budget=self._classify_and_submit(self._draft()),
            actor=self.approver,
            approval_reason="Independent review complete",
        )
        self.project.refresh_from_db()
        self.revision.refresh_from_db()
        self.assertEqual({model: model.objects.count() for model in models}, before)
        self.assertEqual(self.revision.total_amount, estimate_total)
        self.assertEqual(
            (self.project.estimated_budget, self.project.actual_budget), legacy_totals
        )
        self.assertEqual(
            self.project.budget_control.governing_budget.status,
            BudgetVersionStatus.ACCEPTED,
        )
