from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections
from django.test import TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounting.models import JournalEntry
from apps.accounting.policy_calculations import (
    accounting_rounding_policy_from_version,
    money_precision_policy_from_version,
)
from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.organizations.models import (
    BusinessPermission,
    BusinessPermissionCode,
    MembershipStatus,
    OrganizationMembership,
    OrganizationRole,
    PlatformPolicy,
    PlatformPolicyVersion,
    PolicySourceBasis,
    PolicyVersionStatus,
    TenantPolicySelection,
    TenantPolicySelectionStatus,
)
from apps.organizations.policy_specs import (
    ACCOUNTING_MONEY_PRECISION_POLICY_CODE,
    ACCOUNTING_ROUNDING_POLICY_CODE,
    get_platform_policy_spec,
    initial_accounting_policy_parameters,
)
from apps.organizations.services import create_organization_with_owner
from apps.projects.models import Project, ProjectCostFact
from apps.subledgers.models import Obligation
from apps.timekeeping.models import Timesheet, TimesheetEntry, TimesheetState
from apps.treasury.models import TreasuryMovement
from apps.workforce.models import Employee

from .financial_handoff_services import (
    prepare_financial_handoff,
    reconcile_financial_handoff,
    review_financial_handoff,
)
from .models import (
    ComponentKind,
    FinancialHandoffFamily,
    FinancialHandoffProposal,
    NetEffect,
    PayrollComponent,
    PayrollPeriod,
    PayrollPeriodStatus,
    PayrollResultLine,
    PayrollRun,
    PayrollRunEmployee,
    PayrollRunKind,
    PayrollRunStatus,
    ResultStatus,
)
from .services import _monetary_policy_snapshot

HANDOFF_PERMISSIONS = [
    BusinessPermissionCode.PAYROLL_RESULTS_VIEW,
    BusinessPermissionCode.PAYROLL_LIABILITY_HANDOFF_PREPARE,
    BusinessPermissionCode.PAYROLL_LIABILITY_HANDOFF_REVIEW,
    BusinessPermissionCode.PAYROLL_ACCOUNTING_HANDOFF_PREPARE,
    BusinessPermissionCode.PAYROLL_ACCOUNTING_HANDOFF_REVIEW,
    BusinessPermissionCode.PAYROLL_PAYMENT_HANDOFF_PREPARE,
    BusinessPermissionCode.PAYROLL_PAYMENT_HANDOFF_REVIEW,
    BusinessPermissionCode.PAYROLL_PROJECT_COST_HANDOFF_PREPARE,
    BusinessPermissionCode.PAYROLL_PROJECT_COST_HANDOFF_REVIEW,
    BusinessPermissionCode.PAYROLL_HANDOFF_RECONCILIATION_PREPARE,
    BusinessPermissionCode.PAYROLL_HANDOFF_RECONCILIATION_REVIEW,
]


class PayrollFinancialHandoffTests(TransactionTestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="handoff-owner")
        self.organization = create_organization_with_owner(
            owner=self.owner, name="Handoff Tenant", slug="handoff-tenant"
        )
        self.owner_membership = OrganizationMembership.objects.get(
            organization=self.organization, user=self.owner
        )
        self.actor = self._member("handoff-actor", HANDOFF_PERMISSIONS)
        self.reviewer = self._member("handoff-reviewer", HANDOFF_PERMISSIONS)
        self.denied = self._member("handoff-denied", [])
        precision_version, rounding_version = self._monetary_versions()
        precision = money_precision_policy_from_version(
            precision_version, consumer="payroll.run.lock"
        )
        rounding = accounting_rounding_policy_from_version(
            rounding_version, consumer="payroll.run.lock"
        )
        self.employee = Employee.objects.create(
            organization=self.organization,
            employee_number="PAY-001",
            first_name="کارمند",
            last_name="تحویل",
            phone_number="09120000000",
        )
        self.period = PayrollPeriod.objects.create(
            organization=self.organization,
            code="1405-07",
            name="مهر ۱۴۰۵",
            starts_on=date(2026, 9, 23),
            ends_on=date(2026, 10, 22),
            cutoff_at=timezone.now(),
            status=PayrollPeriodStatus.FINALIZED,
            locked_at=timezone.now(),
            finalized_at=timezone.now(),
            created_by=self.owner,
        )
        self.run = PayrollRun.objects.create(
            organization=self.organization,
            period=self.period,
            code="RUN-FINAL",
            status=PayrollRunStatus.FINALIZED,
            idempotency_key="run-final",
            input_digest="input",
            calculation_digest="calculation-v1",
            precision_policy_version=precision_version,
            rounding_policy_version=rounding_version,
            monetary_policy_snapshot=_monetary_policy_snapshot(
                currency=self.organization.settings.currency,
                precision=precision,
                rounding=rounding,
            ),
            currency=self.organization.settings.currency,
            created_by=self.owner,
            finalized_by=self.owner,
            finalized_at=timezone.now(),
        )
        self.result = PayrollRunEmployee.objects.create(
            organization=self.organization,
            run=self.run,
            employee=self.employee,
            status=ResultStatus.FINALIZED,
            gross_amount=Decimal("1000.00"),
            deduction_amount=Decimal("100.00"),
            employer_amount=Decimal("200.00"),
            net_amount=Decimal("900.00"),
        )
        self.component = PayrollComponent.objects.create(
            organization=self.organization,
            code="BASE",
            name="حقوق پایه",
            kind=ComponentKind.EARNING,
            net_effect=NetEffect.ADD,
            created_by=self.owner,
        )
        self.result_line = PayrollResultLine.objects.create(
            organization=self.organization,
            run=self.run,
            run_employee=self.result,
            component=self.component,
            sequence=10,
            component_kind=ComponentKind.EARNING,
            unrounded_amount=Decimal("1000.00"),
            amount=Decimal("1000.00"),
            explanation={"source": "fixture"},
        )

    def _member(self, username, permissions):
        user = User.objects.create_user(username=username)
        role = OrganizationRole.objects.create(
            organization=self.organization,
            code=username,
            name=username,
            created_by=self.owner,
        )
        role.permissions.add(*BusinessPermission.objects.filter(code__in=permissions))
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=user,
            role_definition=role,
            status=MembershipStatus.ACTIVE,
            joined_at=timezone.now(),
            assigned_by=self.owner,
        )
        return user

    def _monetary_versions(self):
        versions = []
        now = timezone.now()
        for code in (
            ACCOUNTING_MONEY_PRECISION_POLICY_CODE,
            ACCOUNTING_ROUNDING_POLICY_CODE,
        ):
            spec = get_platform_policy_spec(code)
            policy = PlatformPolicy.objects.create(
                code=code,
                name=spec.name,
                category=spec.category,
                sensitivity=spec.sensitivity,
                tenant_selectable=spec.tenant_selectable,
                requires_source_provenance=False,
                created_by=self.owner,
                updated_by=self.owner,
            )
            version = PlatformPolicyVersion.objects.create(
                policy=policy,
                version=1,
                parameters=initial_accounting_policy_parameters(code),
                effective_from=timezone.localdate(),
                status=PolicyVersionStatus.PUBLISHED,
                source_basis=PolicySourceBasis.PRODUCT_DEFINED,
                created_by=self.owner,
                published_by=self.owner,
                published_at=now,
                reason="handoff fixture",
            )
            TenantPolicySelection.objects.create(
                organization=self.organization,
                policy=policy,
                policy_version=version,
                status=TenantPolicySelectionStatus.ACTIVE,
                approved_by=self.owner_membership,
                approved_at=now,
                applied_by=self.owner_membership,
                applied_at=now,
                reason="handoff fixture",
            )
            versions.append(version)
        return versions

    def _prepare(self, family, key=None, **kwargs):
        return prepare_financial_handoff(
            organization=self.organization,
            actor=self.actor,
            run=self.run,
            family=family,
            idempotency_key=key or f"{family}-v1",
            reason="آزمون تحویل کنترل‌شده",
            **kwargs,
        )

    def test_finalized_only_idempotent_pinned_and_non_posting(self) -> None:
        PayrollRun.objects.filter(pk=self.run.pk).update(
            status=PayrollRunStatus.APPROVED
        )
        with self.assertRaises(ValidationError):
            self._prepare(FinancialHandoffFamily.LIABILITY)
        PayrollRun.objects.filter(pk=self.run.pk).update(
            status=PayrollRunStatus.FINALIZED
        )
        self.run.refresh_from_db()
        before = (
            Obligation.objects.count(),
            JournalEntry.objects.count(),
            TreasuryMovement.objects.count(),
            ProjectCostFact.objects.count(),
        )
        liability = self._prepare(FinancialHandoffFamily.LIABILITY)
        self.assertEqual(
            self._prepare(FinancialHandoffFamily.LIABILITY).pk, liability.pk
        )
        self.assertEqual(liability.total_amount, Decimal("900.00"))
        self.assertEqual(liability.currency, self.run.currency)
        self.assertEqual(
            liability.monetary_policy_snapshot, self.run.monetary_policy_snapshot
        )
        self.assertEqual(
            before,
            (
                Obligation.objects.count(),
                JournalEntry.objects.count(),
                TreasuryMovement.objects.count(),
                ProjectCostFact.objects.count(),
            ),
        )

    def test_accounting_mapping_held_and_payment_is_only_a_treasury_proposal(
        self,
    ) -> None:
        accounting = self._prepare(FinancialHandoffFamily.ACCOUNTING)
        payment = self._prepare(FinancialHandoffFamily.PAYMENT)
        self.assertIn("ACCOUNT_MAPPING_NOT_CONFIGURED", accounting.exception_codes)
        self.assertFalse(payment.has_exceptions)
        with self.assertRaises(ValidationError):
            review_financial_handoff(
                organization=self.organization,
                actor=self.reviewer,
                proposal=accounting,
                disposition="accepted",
                reason="نباید پذیرفته شود",
            )
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(TreasuryMovement.objects.count(), 0)

    def test_project_cost_conservation_allocation_lineage_and_no_actual(self) -> None:
        project = Project.objects.create(
            organization=self.organization,
            code="P-1",
            name="پروژه",
            created_by=self.owner,
        )
        timesheet = Timesheet.objects.create(
            organization=self.organization,
            employee=self.employee,
            period_start=self.period.starts_on,
            period_end=self.period.ends_on,
            revision=1,
            declared_minutes=600,
            prepared_by=self.actor,
        )
        TimesheetEntry.objects.create(
            organization=self.organization,
            timesheet=timesheet,
            work_date=date(2026, 10, 1),
            project=project,
            minutes=400,
        )
        TimesheetEntry.objects.create(
            organization=self.organization,
            timesheet=timesheet,
            work_date=date(2026, 10, 2),
            project=project,
            minutes=200,
        )
        Timesheet.objects.filter(pk=timesheet.pk).update(state=TimesheetState.APPROVED)
        proposal = self._prepare(FinancialHandoffFamily.PROJECT_COST)
        self.assertEqual(proposal.total_amount, Decimal("1200.00"))
        self.assertEqual(proposal.allocated_amount, proposal.total_amount)
        self.assertEqual(proposal.unallocated_amount, Decimal(0))
        self.assertEqual(
            sum(proposal.lines.values_list("amount", flat=True), Decimal(0)),
            proposal.total_amount,
        )
        self.assertTrue(all(line.timesheet_entry_id for line in proposal.lines.all()))
        self.assertEqual(ProjectCostFact.objects.count(), 0)

    def test_unallocated_reconciliation_permissions_tenant_and_audit_rollback(
        self,
    ) -> None:
        with self.assertRaises(PermissionDenied):
            prepare_financial_handoff(
                organization=self.organization,
                actor=self.denied,
                run=self.run,
                family=FinancialHandoffFamily.LIABILITY,
                idempotency_key="denied",
                reason="denied",
            )
        proposal = self._prepare(FinancialHandoffFamily.PROJECT_COST)
        self.assertEqual(proposal.unallocated_amount, Decimal("1200.00"))
        PayrollRun.objects.filter(pk=self.run.pk).update(
            calculation_digest="stale-calculation"
        )
        reconciliation = reconcile_financial_handoff(
            organization=self.organization, actor=self.actor, proposal=proposal
        )
        self.assertIn("MISSING_DOWNSTREAM_ACKNOWLEDGEMENT", reconciliation.issue_codes)
        self.assertIn("STALE_SOURCE", reconciliation.issue_codes)
        with (
            patch(
                "apps.payroll.financial_handoff_services.record_audit_event",
                side_effect=RuntimeError("audit unavailable"),
            ),
            self.assertRaises(RuntimeError),
        ):
            prepare_financial_handoff(
                organization=self.organization,
                actor=self.actor,
                run=self.run,
                family=FinancialHandoffFamily.PAYMENT,
                idempotency_key="rollback",
                reason="rollback",
            )
        self.assertFalse(
            FinancialHandoffProposal.objects.filter(idempotency_key="rollback").exists()
        )

        other_owner = User.objects.create_user(username="handoff-other-owner")
        other = create_organization_with_owner(
            owner=other_owner, name="Other Tenant", slug="handoff-other"
        )
        other_role = OrganizationRole.objects.create(
            organization=other,
            code="other-handoff",
            name="other-handoff",
            created_by=other_owner,
        )
        other_role.permissions.add(
            *BusinessPermission.objects.filter(
                code=BusinessPermissionCode.PAYROLL_LIABILITY_HANDOFF_PREPARE
            )
        )
        other_actor = User.objects.create_user(username="handoff-other-actor")
        OrganizationMembership.objects.create(
            organization=other,
            user=other_actor,
            role_definition=other_role,
            status=MembershipStatus.ACTIVE,
            joined_at=timezone.now(),
            assigned_by=other_owner,
        )
        with self.assertRaises(PermissionDenied):
            prepare_financial_handoff(
                organization=other,
                actor=other_actor,
                run=self.run,
                family=FinancialHandoffFamily.LIABILITY,
                idempotency_key="cross-tenant",
                reason="cross tenant",
            )

    def test_replacement_requires_and_preserves_explicit_predecessor_lineage(
        self,
    ) -> None:
        original = self._prepare(FinancialHandoffFamily.LIABILITY)
        replacement = PayrollRun.objects.create(
            organization=self.organization,
            period=self.period,
            code="RUN-REPLACEMENT",
            kind=PayrollRunKind.REPLACEMENT,
            status=PayrollRunStatus.FINALIZED,
            idempotency_key="run-replacement",
            replaces=self.run,
            input_digest="replacement-input",
            calculation_digest="replacement-calculation",
            precision_policy_version=self.run.precision_policy_version,
            rounding_policy_version=self.run.rounding_policy_version,
            monetary_policy_snapshot=self.run.monetary_policy_snapshot,
            currency=self.run.currency,
            created_by=self.owner,
            finalized_by=self.owner,
            finalized_at=timezone.now(),
        )
        replacement_result = PayrollRunEmployee.objects.create(
            organization=self.organization,
            run=replacement,
            employee=self.employee,
            predecessor_result=self.result,
            status=ResultStatus.FINALIZED,
            gross_amount=Decimal("1100.00"),
            employer_amount=Decimal("220.00"),
            net_amount=Decimal("990.00"),
        )
        PayrollResultLine.objects.create(
            organization=self.organization,
            run=replacement,
            run_employee=replacement_result,
            component=self.component,
            sequence=10,
            component_kind=ComponentKind.EARNING,
            unrounded_amount=Decimal("1100.00"),
            amount=Decimal("1100.00"),
            explanation={"replacement": True},
        )
        successor = prepare_financial_handoff(
            organization=self.organization,
            actor=self.actor,
            run=replacement,
            family=FinancialHandoffFamily.LIABILITY,
            idempotency_key="replacement-liability",
            reason="اصلاح صریح",
        )
        self.assertEqual(successor.predecessor, original)
        self.assertEqual(successor.record_kind, "replacement")

    def test_persian_rtl_ui_and_minimum_sensitive_detail(self) -> None:
        proposal = self._prepare(FinancialHandoffFamily.LIABILITY)
        self.client.force_login(self.actor)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()
        response = self.client.get(
            reverse("payroll:financial_handoff_detail", args=[proposal.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<html lang="fa" dir="rtl">', html=False)
        self.assertContains(response, "هیچ اثر مالی خودکار ندارد")
        self.assertNotContains(response, self.employee.phone_number)
        self.assertTrue(
            self.organization.audit_events.filter(
                action=AuditAction.PAYROLL_FINANCIAL_HANDOFF_PREPARED
            ).exists()
        )

    def test_handoff_views_expose_only_explicitly_authorized_family(self) -> None:
        liability = self._prepare(FinancialHandoffFamily.LIABILITY)
        payment = self._prepare(FinancialHandoffFamily.PAYMENT)
        limited = self._member(
            "liability-only",
            [BusinessPermissionCode.PAYROLL_LIABILITY_HANDOFF_PREPARE],
        )
        self.client.force_login(limited)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()

        response = self.client.get(reverse("payroll:financial_handoff_workbench"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("payroll:financial_handoff_detail", args=[liability.pk]))
        self.assertNotContains(response, reverse("payroll:financial_handoff_detail", args=[payment.pk]))
        self.assertEqual(
            self.client.get(
                reverse("payroll:financial_handoff_detail", args=[payment.pk])
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                reverse("payroll:financial_handoff_review", args=[liability.pk])
            ).status_code,
            403,
        )

    def test_concurrent_idempotent_preparation_creates_one_proposal(self) -> None:
        organization_id = self.organization.pk
        actor_id = self.actor.pk
        run_id = self.run.pk

        def prepare():
            close_old_connections()
            try:
                return prepare_financial_handoff(
                    organization=self.organization.__class__.objects.get(
                        pk=organization_id
                    ),
                    actor=User.objects.get(pk=actor_id),
                    run=PayrollRun.objects.get(pk=run_id),
                    family=FinancialHandoffFamily.LIABILITY,
                    idempotency_key="concurrent-liability",
                    reason="آزمون همزمانی",
                ).pk
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            ids = list(executor.map(lambda _: prepare(), range(2)))
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(
            FinancialHandoffProposal.objects.filter(
                organization=self.organization,
                family=FinancialHandoffFamily.LIABILITY,
            ).count(),
            1,
        )
