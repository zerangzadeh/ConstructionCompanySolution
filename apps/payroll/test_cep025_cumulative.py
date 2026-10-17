from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermission,
    BusinessPermissionCode,
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationRole,
    OrganizationSettings,
)
from apps.payroll.cumulative_services import (
    approve_payroll_year,
    create_payroll_year_draft,
    cumulative_balances,
    record_cumulative_for_run,
)
from apps.payroll.models import (
    ComponentKind,
    NetEffect,
    PayrollComponent,
    PayrollCumulativeState,
    PayrollPeriod,
    PayrollResultLine,
    PayrollRun,
    PayrollRunEmployee,
    PayrollRunKind,
    PayrollRunStatus,
    PayrollYearStatus,
    ResultStatus,
)
from apps.payroll.services import finalize_run, reverse_run
from apps.workforce.models import Employee


class OperationalCumulativeTests(TestCase):
    def setUp(self) -> None:
        self.actor = User.objects.create_user(username="cep025-owner")
        self.organization = Organization.objects.create(
            name="CEP-025 tenant", slug="cep025-tenant"
        )
        OrganizationSettings.objects.create(
            organization=self.organization, currency="IRR"
        )
        owner_role = OrganizationRole.objects.get(code=MembershipRole.COMPANY_OWNER)
        owner_role.permissions.add(
            *BusinessPermission.objects.filter(
                code__in=[
                    BusinessPermissionCode.PAYROLL_CONFIGURATION_MANAGE,
                    BusinessPermissionCode.PAYROLL_FINALIZE,
                    BusinessPermissionCode.PAYROLL_ADJUST,
                    BusinessPermissionCode.PAYROLL_RESULTS_VIEW,
                ]
            )
        )
        membership = self.organization.memberships.create(
            user=self.actor,
            role=MembershipRole.COMPANY_OWNER,
            role_definition=owner_role,
            status=MembershipStatus.ACTIVE,
        )
        membership.role_assignments.create(
            organization=self.organization,
            role=owner_role,
            reason="Explicit cumulative test authority",
        )
        membership.scope_grants.create(
            organization=self.organization,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="Explicit cumulative test scope",
        )
        self.employee = Employee.objects.create(
            organization=self.organization,
            employee_number="CEP025",
            first_name="Test",
            last_name="Employee",
        )
        self.period = PayrollPeriod.objects.create(
            organization=self.organization,
            code="CEP025-PERIOD",
            name="October payroll",
            starts_on=date(2026, 10, 1),
            ends_on=date(2026, 10, 31),
            cutoff_at=timezone.now(),
            status="finalized",
            created_by=self.actor,
        )
        self.run = self._run(code="CEP025-RUN", digest="a" * 64)
        self.components = {}
        for kind, effect in (
            (ComponentKind.EARNING, NetEffect.ADD),
            (ComponentKind.ALLOWANCE, NetEffect.ADD),
            (ComponentKind.DEDUCTION, NetEffect.SUBTRACT),
            (ComponentKind.REIMBURSEMENT, NetEffect.ADD),
            (ComponentKind.EMPLOYER, NetEffect.NONE),
            (ComponentKind.INFORMATIONAL, NetEffect.NONE),
        ):
            self.components[kind] = PayrollComponent.objects.create(
                organization=self.organization,
                code=f"C-{kind}",
                name=kind,
                kind=kind,
                net_effect=effect,
                created_by=self.actor,
            )
        self.lines = self._lines(self.run)

    def _run(
        self,
        *,
        code: str,
        digest: str,
        kind: str = PayrollRunKind.REGULAR,
        reversal_of: PayrollRun | None = None,
    ) -> PayrollRun:
        return PayrollRun.objects.create(
            organization=self.organization,
            period=self.period,
            code=code,
            kind=kind,
            status=PayrollRunStatus.FINALIZED,
            idempotency_key=code,
            reversal_of=reversal_of,
            predecessor=reversal_of,
            calculation_digest=digest,
            created_by=self.actor,
        )

    def _lines(
        self, run: PayrollRun, *, reversed_sign: bool = False
    ) -> list[PayrollResultLine]:
        result = PayrollRunEmployee.objects.create(
            organization=self.organization,
            run=run,
            employee=self.employee,
            status=ResultStatus.FINALIZED,
        )
        amounts = {
            ComponentKind.EARNING: "100.00",
            ComponentKind.ALLOWANCE: "20.00",
            ComponentKind.DEDUCTION: "10.00",
            ComponentKind.REIMBURSEMENT: "5.00",
            ComponentKind.EMPLOYER: "15.00",
            ComponentKind.INFORMATIONAL: "99.00",
        }
        return [
            PayrollResultLine.objects.create(
                organization=self.organization,
                run=run,
                run_employee=result,
                component=self.components[kind],
                sequence=index,
                component_kind=kind,
                unrounded_amount=(
                    -Decimal(amount) if reversed_sign else Decimal(amount)
                ),
                amount=-Decimal(amount) if reversed_sign else Decimal(amount),
                explanation={"source_version": run.calculation_digest},
                is_reversal=reversed_sign,
            )
            for index, (kind, amount) in enumerate(amounts.items(), start=1)
        ]

    def _year(self, code: str = "OPERATIONAL-2026"):
        return approve_payroll_year(
            organization=self.organization,
            actor=self.actor,
            year=create_payroll_year_draft(
                organization=self.organization,
                actor=self.actor,
                code=code,
                starts_on=date(2026, 7, 1),
                ends_on=date(2027, 6, 30),
                reason="Explicit operational reset interval",
            ),
        )

    def test_finalized_signed_buckets_are_idempotent_and_reversal_preserves_history(
        self,
    ) -> None:
        with self.assertRaises(ValidationError):
            record_cumulative_for_run(
                organization=self.organization, actor=self.actor, run=self.run
            )
        year = self._year()
        self.assertEqual(
            record_cumulative_for_run(
                organization=self.organization, actor=self.actor, run=self.run
            ),
            5,
        )
        self.assertEqual(
            record_cumulative_for_run(
                organization=self.organization, actor=self.actor, run=self.run
            ),
            0,
        )
        balances = cumulative_balances(
            organization=self.organization,
            actor=self.actor,
            year=year,
            employee=self.employee,
        )
        self.assertEqual(len(balances), 5)
        self.assertEqual(
            {state.component_kind: state.balance for state in balances}[
                ComponentKind.DEDUCTION
            ],
            Decimal("10.00"),
        )
        self.assertEqual({state.source_version for state in balances}, {"a" * 64})
        PayrollRun.objects.filter(pk=self.run.pk).update(
            status=PayrollRunStatus.REVERSED
        )
        reversal = self._run(
            code="CEP025-REV",
            digest="b" * 64,
            kind=PayrollRunKind.REVERSAL,
            reversal_of=self.run,
        )
        self._lines(reversal, reversed_sign=True)
        self.assertEqual(
            record_cumulative_for_run(
                organization=self.organization, actor=self.actor, run=reversal
            ),
            5,
        )
        self.assertEqual(PayrollCumulativeState.objects.filter(year=year).count(), 10)
        self.assertTrue(
            all(
                state.balance == Decimal("0.00") and state.state_version == 2
                for state in cumulative_balances(
                    organization=self.organization,
                    actor=self.actor,
                    year=year,
                    employee=self.employee,
                )
            )
        )
        with self.assertRaises(ValidationError):
            PayrollCumulativeState.objects.filter(year=year).first().save()

    def test_year_reapproval_preserves_old_version_and_rebuilds_from_source(
        self,
    ) -> None:
        old_year = self._year()
        record_cumulative_for_run(
            organization=self.organization, actor=self.actor, run=self.run
        )
        new_year = self._year()
        old_year.refresh_from_db()
        self.assertEqual(old_year.status, PayrollYearStatus.SUPERSEDED)
        self.assertEqual(new_year.version, 2)
        self.assertEqual(
            PayrollCumulativeState.objects.filter(year=old_year).count(), 5
        )
        self.assertEqual(
            record_cumulative_for_run(
                organization=self.organization, actor=self.actor, run=self.run
            ),
            5,
        )
        self.assertEqual(
            PayrollCumulativeState.objects.filter(year=new_year).count(), 5
        )
        with self.assertRaises(ValidationError):
            self._year("OVERLAPPING-DIFFERENT-YEAR")

    def test_core_finalize_and_reversal_hooks_commit_matching_ytd_history(self) -> None:
        year = self._year()
        PayrollRun.objects.filter(pk=self.run.pk).update(
            status=PayrollRunStatus.APPROVED
        )
        PayrollRunEmployee.objects.filter(run=self.run).update(
            status=ResultStatus.CALCULATED
        )
        finalize_run(organization=self.organization, actor=self.actor, run=self.run)
        self.assertEqual(PayrollCumulativeState.objects.filter(year=year).count(), 5)
        with patch("apps.payroll.services._locked_monetary_policies"):
            reverse_run(
                organization=self.organization,
                actor=self.actor,
                original_run=self.run,
                reason="Correct source version",
                idempotency_key="cep025-hook-reversal",
                create_replacement=False,
            )
        self.assertEqual(PayrollCumulativeState.objects.filter(year=year).count(), 10)
        self.assertTrue(
            all(
                state.balance == Decimal("0.00")
                for state in cumulative_balances(
                    organization=self.organization,
                    actor=self.actor,
                    year=year,
                    employee=self.employee,
                )
            )
        )

    def test_draft_or_cross_tenant_year_cannot_expose_cumulative_state(self) -> None:
        draft = create_payroll_year_draft(
            organization=self.organization,
            actor=self.actor,
            code="DRAFT-YEAR",
            starts_on=date(2026, 7, 1),
            ends_on=date(2027, 6, 30),
            reason="Explicit future boundary",
        )
        self.assertEqual(draft.status, PayrollYearStatus.DRAFT)
        with self.assertRaises(ValidationError):
            cumulative_balances(
                organization=self.organization,
                actor=self.actor,
                year=draft,
                employee=self.employee,
            )
        with self.assertRaises(ValidationError):
            record_cumulative_for_run(
                organization=self.organization, actor=self.actor, run=self.run
            )
        other = Organization.objects.create(name="Other", slug="cep025-other")
        other_employee = Employee.objects.create(
            organization=other,
            employee_number="OTHER",
            first_name="Other",
            last_name="Employee",
        )
        with self.assertRaises(PermissionDenied):
            cumulative_balances(
                organization=self.organization,
                actor=self.actor,
                year=draft,
                employee=other_employee,
            )
