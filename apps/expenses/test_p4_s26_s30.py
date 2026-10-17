from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.test import TestCase
from django.urls import reverse

from apps.accounting.models import JournalEntry
from apps.accounts.models import User
from apps.estimates.services import add_estimate_item, approve_estimate, create_estimate
from apps.expenses.models import (
    ExpenseBudgetAssessment,
    ExpenseStatus,
    PlatformExpenseGroup,
)
from apps.expenses.services import (
    add_expense_allocation,
    approve_expense,
    create_expense_draft,
    create_recurring_expense_template,
    propose_recurring_expense,
    return_expense,
    submit_expense,
    void_expense,
)
from apps.organizations.access_services import bootstrap_membership_authorization
from apps.organizations.models import (
    BusinessPermission,
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationSettings,
)
from apps.projects.models import ProjectBudgetControl
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
    lock_cost_structure_version,
    submit_budget_version,
)
from apps.subledgers.models import Obligation
from apps.treasury.models import PaymentRequest, TreasuryMovement
from apps.treasury.services import create_payment_request
from apps.workforce.models import Employee


class ExpenseControlTests(TestCase):
    def setUp(self) -> None:
        self.maker = User.objects.create_user(username="expense-control-maker")
        self.approver = User.objects.create_user(username="expense-control-approver")
        self.outsider = User.objects.create_user(username="expense-control-outsider")
        self.organization = Organization.objects.create(name="Expense Control", slug="expense-control")
        OrganizationSettings.objects.create(organization=self.organization, currency="IRR")
        PlatformExpenseGroup.objects.get_or_create(
            code="other", defaults={"name": "Other"},
        )
        for user in (self.maker, self.approver):
            membership = self.organization.memberships.create(
                user=user, role=MembershipRole.COMPANY_OWNER, status=MembershipStatus.ACTIVE
            )
            bootstrap_membership_authorization(
                membership=membership, actor=user, source="test-fixture",
            )
        self.project = create_project(
            organization=self.organization,
            actor=self.maker,
            code="EXP-CONTROL",
            name="Expense control project",
        )
        self.wbs = create_wbs_node(
            organization=self.organization,
            project=self.project,
            actor=self.maker,
            code="W1",
            title="Work",
        )
        estimate = create_estimate(
            organization=self.organization,
            project=self.project,
            actor=self.maker,
            estimate_number="EXP-BUDGET",
            title="Expense budget source",
        )
        add_estimate_item(
            estimate=estimate,
            actor=self.maker,
            description="Budget line",
            quantity=Decimal(1),
            unit_price=Decimal("100.00"),
        )
        approve_estimate(estimate=estimate, actor=self.maker)
        estimate.refresh_from_db()
        structure = create_cost_structure_version(
            organization=self.organization,
            actor=self.maker,
            code="EXP-CBS",
            version=1,
            name="Expense structure",
            governance_reference="P4-G07-EXPLICIT",
        )
        self.cbs = add_cbs_node(
            structure=structure, actor=self.maker, code="C1", name="Direct"
        )
        self.cost_center = add_cost_center(
            structure=structure, actor=self.maker, code="CC1", name="Responsibility"
        )
        lock_cost_structure_version(structure=structure, actor=self.maker)
        budget = create_budget_draft_from_estimate(
            organization=self.organization,
            project=self.project,
            actor=self.maker,
            estimate_revision=estimate.current_revision,
            structure=structure,
            handoff_id="EXPENSE-CONTROL",
            submission_version=1,
            governance_reference="P4-G06-EXPLICIT",
            rounding_policy_reference="IRR-DECIMAL-2",
            cost_center_required=True,
            reason="Expense control accepted budget",
        )
        line = budget.source_manifest.lines.get()
        classify_budget_manifest_line(
            line=line,
            actor=self.maker,
            allocations=(
                BudgetAllocationInput(
                    amount=Decimal("100.00"),
                    cbs_node=self.cbs,
                    wbs_node=self.wbs,
                    cost_center=self.cost_center,
                    allocation_basis_reference="approved mapping",
                ),
            ),
        )
        budget = submit_budget_version(budget=budget, actor=self.maker)
        self.budget = accept_budget_version(
            budget=budget,
            actor=self.approver,
            approval_reason="Independent acceptance",
        )

    def _draft(self, *, key="expense-1", source="INV-1", amount=Decimal("60.00")):
        return create_expense_draft(
            organization=self.organization,
            project=self.project,
            actor=self.maker,
            description="Reviewed source expense",
            amount=amount,
            incurred_on=date(2026, 10, 1),
            source_reference=source,
            idempotency_key=key,
        )

    def _allocate(self, expense, amount=None):
        return add_expense_allocation(
            expense=expense,
            actor=self.maker,
            project=self.project,
            wbs_node=self.wbs,
            cbs_node=self.cbs,
            cost_center=self.cost_center,
            amount=amount or expense.amount,
            allocation_basis_reference="reviewed invoice split",
        )

    def test_full_lifecycle_conserves_allocation_and_keeps_finance_boundaries(self) -> None:
        before = (JournalEntry.objects.count(), TreasuryMovement.objects.count(), Obligation.objects.count())
        expense = self._draft()
        self._allocate(expense)
        submit_expense(expense=expense, actor=self.maker)
        expense.refresh_from_db()
        self.assertEqual(expense.status, ExpenseStatus.SUBMITTED)
        with self.assertRaises(PermissionDenied):
            approve_expense(expense=expense, actor=self.maker)
        approve_expense(expense=expense, actor=self.approver)
        expense.refresh_from_db()
        self.assertEqual(expense.status, ExpenseStatus.APPROVED)
        self.assertEqual(
            before,
            (JournalEntry.objects.count(), TreasuryMovement.objects.count(), Obligation.objects.count()),
        )

    def test_reimbursement_source_request_and_replacement_preserve_authority(self) -> None:
        employee = Employee.objects.create(
            organization=self.organization,
            employee_number="EXP-R1",
            first_name="Test",
            last_name="Worker",
        )
        other = Organization.objects.create(name="Other reimbursement", slug="other-reimbursement")
        other_employee = Employee.objects.create(
            organization=other,
            employee_number="EXP-R1",
            first_name="Other",
            last_name="Worker",
        )
        with self.assertRaises(PermissionDenied):
            create_expense_draft(
                organization=self.organization, project=self.project, actor=self.maker,
                description="Reimbursement", amount=Decimal("60.00"),
                incurred_on=date(2026, 10, 1), source_reference="REIMB-INVALID",
                idempotency_key="reimb-invalid", reimbursement_employee=other_employee,
            )
        expense = create_expense_draft(
            organization=self.organization, project=self.project, actor=self.maker,
            description="Reimbursement", amount=Decimal("60.00"),
            incurred_on=date(2026, 10, 1), source_reference="REIMB-1",
            idempotency_key="reimb-1", reimbursement_employee=employee,
        )
        self._allocate(expense)
        submit_expense(expense=expense, actor=self.maker)
        approve_expense(expense=expense, actor=self.approver)
        expense.refresh_from_db()
        before = (JournalEntry.objects.count(), TreasuryMovement.objects.count(), Obligation.objects.count())
        request = create_payment_request(
            organization=self.organization, actor=self.maker,
            kind="employee_reimbursement", amount=expense.amount,
            purpose="Reviewed employee reimbursement", idempotency_key="reimb-request-1",
            employee=employee, project=self.project, source_expense=expense,
        )
        self.assertEqual(request.source_expense_version, 1)
        self.assertEqual(request.source_expense_id, expense.pk)
        self.assertEqual(PaymentRequest.objects.filter(source_expense=expense).count(), 1)
        self.assertEqual(before, (JournalEntry.objects.count(), TreasuryMovement.objects.count(), Obligation.objects.count()))
        with self.assertRaises(ValidationError):
            create_payment_request(
                organization=self.organization, actor=self.maker,
                kind="employee_reimbursement", amount=expense.amount,
                purpose="Duplicate", idempotency_key="reimb-request-2",
                employee=employee, project=self.project, source_expense=expense,
            )
        with self.assertRaises(ValueError):
            void_expense(expense=expense, actor=self.approver, reason="Correction")

    def test_voided_reimbursement_replacement_keeps_source_version(self) -> None:
        employee = Employee.objects.create(
            organization=self.organization, employee_number="EXP-R2",
            first_name="Test", last_name="Worker",
        )
        original = create_expense_draft(
            organization=self.organization, project=self.project, actor=self.maker,
            description="Employee expense", amount=Decimal("60.00"),
            incurred_on=date(2026, 10, 1), source_reference="REIMB-2",
            idempotency_key="reimb-2", reimbursement_employee=employee,
        )
        void_expense(expense=original, actor=self.approver, reason="Source correction")
        replacement = create_expense_draft(
            organization=self.organization, project=self.project, actor=self.maker,
            description="Employee expense corrected", amount=Decimal("60.00"),
            incurred_on=date(2026, 10, 1), source_reference="REIMB-2",
            idempotency_key="reimb-2-v2", reimbursement_employee=employee,
            replaces=original,
        )
        self.assertEqual(replacement.replaces_id, original.pk)
        self.assertEqual(replacement.source_version, 2)
        original.refresh_from_db()
        self.assertEqual(original.status, ExpenseStatus.VOID)

    def test_return_and_resubmit_preserve_evidence_and_append_assessment(self) -> None:
        expense = self._draft()
        self._allocate(expense)
        submit_expense(expense=expense, actor=self.maker)
        return_expense(expense=expense, actor=self.approver, reason="Clarify source")
        expense.refresh_from_db()
        self.assertEqual(expense.status, ExpenseStatus.RETURNED)
        submit_expense(expense=expense, actor=self.maker)
        self.assertEqual(ExpenseBudgetAssessment.objects.filter(expense=expense).count(), 2)

    def test_nonconserved_and_uncoded_budget_submission_fail_closed(self) -> None:
        expense = self._draft()
        self._allocate(expense, Decimal("59.00"))
        with self.assertRaisesMessage(ValueError, "exactly conserve"):
            submit_expense(expense=expense, actor=self.maker)

    def test_duplicate_source_and_idempotent_retry_are_controlled(self) -> None:
        first = self._draft()
        retry = self._draft()
        self.assertEqual(first.pk, retry.pk)
        with self.assertRaisesMessage(ValueError, "Duplicate active expense"):
            self._draft(key="different", source="INV-1")

    def test_recurrence_creates_one_reviewable_draft_only(self) -> None:
        template = create_recurring_expense_template(
            organization=self.organization,
            project=self.project,
            actor=self.maker,
            description="Monthly site rent",
            amount=Decimal("25.00"),
            classification="indirect",
            frequency="monthly",
            starts_on=date(2026, 10, 1),
            source_reference_prefix="RENT",
        )
        first = propose_recurring_expense(
            template=template, occurrence_on=date(2026, 11, 1), actor=self.maker
        )
        retry = propose_recurring_expense(
            template=template, occurrence_on=date(2026, 11, 1), actor=self.maker
        )
        self.assertEqual(first.pk, retry.pk)
        self.assertEqual(first.status, ExpenseStatus.DRAFT)
        self.assertIsNone(first.approved_at)

    def test_cross_tenant_and_permission_scope_fail_closed(self) -> None:
        expense = self._draft()
        with self.assertRaises(PermissionDenied):
            add_expense_allocation(
                expense=expense,
                actor=self.outsider,
                project=self.project,
                wbs_node=self.wbs,
                cbs_node=self.cbs,
                cost_center=self.cost_center,
                amount=expense.amount,
                allocation_basis_reference="denied",
            )

    def test_overrun_is_advisory_and_submitted_source_is_database_immutable(self) -> None:
        expense = self._draft(key="overrun", source="INV-OVERRUN", amount=Decimal("120.00"))
        self._allocate(expense)
        submit_expense(expense=expense, actor=self.maker)
        assessment = ExpenseBudgetAssessment.objects.get(expense=expense)
        self.assertTrue(assessment.is_overrun)
        self.assertEqual(assessment.control_mode, "advisory_only")
        with self.assertRaises(DatabaseError), transaction.atomic():
            type(expense).objects.filter(pk=expense.pk).update(amount=Decimal("1.00"))

    def test_expense_permission_catalog_contains_separated_actions(self) -> None:
        self.assertEqual(
            set(
                BusinessPermission.objects.filter(
                    code__in={
                        "expenses.submit",
                        "expenses.approve",
                        "expenses.return",
                        "expenses.allocate",
                        "expenses.recurrences_manage",
                    }
                ).values_list("code", flat=True)
            ),
            {
                "expenses.submit",
                "expenses.approve",
                "expenses.return",
                "expenses.allocate",
                "expenses.recurrences_manage",
            },
        )

    def test_approval_rejects_stale_governing_budget_pointer(self) -> None:
        expense = self._draft(key="budget-race", source="INV-RACE")
        self._allocate(expense)
        submit_expense(expense=expense, actor=self.maker)
        ProjectBudgetControl.objects.filter(project=self.project).update(
            governing_budget=None
        )
        with self.assertRaisesMessage(ValueError, "changed after submission"):
            approve_expense(expense=expense, actor=self.approver)

    def test_expense_control_ui_is_tenant_scoped_and_available(self) -> None:
        expense = self._draft(key="ui", source="INV-UI")
        self.client.force_login(self.maker)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()
        self.assertEqual(self.client.get(reverse("expenses:draft_create")).status_code, 200)
        self.assertEqual(
            self.client.get(reverse("expenses:detail", args=[expense.pk])).status_code,
            200,
        )
        self.assertEqual(self.client.get(reverse("expenses:recurrences")).status_code, 200)
