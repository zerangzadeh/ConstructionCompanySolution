from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.apps import apps as django_apps
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounting.models import JournalEntry
from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.audit.services import get_organization_audit_events, record_audit_event
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermission,
    BusinessPermissionCode,
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    PlatformPolicy,
    PlatformPolicyVersion,
    PolicySourceBasis,
    PolicyVersionStatus,
    TenantPolicySelection,
    TenantPolicySelectionStatus,
)
from apps.organizations.permission_registry import (
    registered_model_labels,
    registered_permission_codes,
)
from apps.organizations.policy_specs import (
    ACCOUNTING_MONEY_PRECISION_POLICY_CODE,
    ACCOUNTING_ROUNDING_POLICY_CODE,
    get_platform_policy_spec,
    initial_accounting_policy_parameters,
)
from apps.organizations.role_defaults import DEFAULT_ROLE_PERMISSIONS
from apps.organizations.services import create_organization_with_owner
from apps.projects.models import ProjectCostFact
from apps.subledgers.models import Obligation
from apps.treasury.models import TreasuryMovement
from apps.workforce.models import Employee

from .models import (
    CalculationMethod,
    ComponentKind,
    ConfigurationStatus,
    NetEffect,
    PayrollComponent,
    PayrollException,
    PayrollInputSnapshot,
    PayrollPeriodStatus,
    PayrollResultLine,
    PayrollRun,
    PayrollRunEmployee,
    PayrollRunKind,
    PayrollRunStatus,
    Payslip,
    RateSource,
    ResultStatus,
)
from .services import (
    activate_employment_configuration,
    activate_rule,
    approve_run,
    calculate_run,
    create_component,
    create_employment_configuration,
    create_period,
    create_rule,
    create_run,
    export_payslip,
    finalize_run,
    lock_run_inputs,
    negative_net_carry_forward_candidate,
    record_adjustment,
    record_input,
    retire_employment_configuration,
    retire_rule,
    reverse_run,
    review_negative_net_exception,
    submit_run_for_review,
    view_payslip,
)

PAYROLL_PERMISSION_CODES = [
    BusinessPermissionCode.PAYROLL_CONFIGURATION_VIEW,
    BusinessPermissionCode.PAYROLL_CONFIGURATION_MANAGE,
    BusinessPermissionCode.PAYROLL_PREPARE,
    BusinessPermissionCode.PAYROLL_REVIEW,
    BusinessPermissionCode.PAYROLL_FINALIZE,
    BusinessPermissionCode.PAYROLL_ADJUST,
    BusinessPermissionCode.PAYROLL_RESULTS_VIEW,
    BusinessPermissionCode.PAYSLIPS_VIEW,
    BusinessPermissionCode.PAYSLIPS_EXPORT,
    BusinessPermissionCode.PAYROLL_AUDIT_VIEW,
]


class CorePayrollTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="payroll-owner")
        self.organization = create_organization_with_owner(
            owner=self.owner, name="Payroll Tenant", slug="payroll-tenant"
        )
        self.organization.settings.timezone = "Asia/Tehran"
        self.organization.settings.save(update_fields=["timezone", "updated_at"])
        self.owner_membership = OrganizationMembership.objects.get(
            organization=self.organization, user=self.owner
        )
        self._activate_monetary_policies()
        self.actor = self._member("payroll-operator", PAYROLL_PERMISSION_CODES)
        self.denied = self._member("workforce-only", [])
        self.employee = Employee.objects.create(
            organization=self.organization,
            employee_number="PAY-001",
            first_name="کارمند",
            last_name="نمونه",
        )
        self.configuration = create_employment_configuration(
            organization=self.organization,
            actor=self.actor,
            employee=self.employee,
            pay_model="salaried",
            base_rate=Decimal("50.12500000"),
            rate_unit="hour",
            effective_from=date(2026, 1, 1),
            source_reference="employment-offer-v1",
            evidence={"approved_reference": "HR-001"},
        )
        activate_employment_configuration(
            organization=self.organization,
            actor=self.actor,
            configuration=self.configuration,
        )
        self.period = create_period(
            organization=self.organization,
            actor=self.actor,
            code="1405-07",
            name="دوره مهر ۱۴۰۵",
            starts_on=date(2026, 9, 23),
            ends_on=date(2026, 10, 22),
            cutoff_at=datetime(2026, 10, 23, 12, tzinfo=ZoneInfo("Asia/Tehran")),
        )

    def _member(
        self, username: str, permission_codes: list[BusinessPermissionCode]
    ) -> User:
        user = User.objects.create_user(username=username)
        role = OrganizationRole.objects.create(
            organization=self.organization,
            code=username,
            name=username,
            created_by=self.owner,
        )
        role.permissions.add(
            *BusinessPermission.objects.filter(code__in=permission_codes)
        )
        membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=user,
            role_definition=role,
            status=MembershipStatus.ACTIVE,
            joined_at=timezone.now(),
            assigned_by=self.owner,
        )
        membership.role_assignments.create(
            organization=self.organization,
            role=role,
            reason="Explicit Payroll test authority",
        )
        membership.scope_grants.create(
            organization=self.organization,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="Explicit Payroll test scope",
        )
        return user

    def _activate_monetary_policies(self) -> None:
        now = timezone.now()
        self.monetary_policies: dict[str, PlatformPolicy] = {}
        self.monetary_policy_versions: dict[str, PlatformPolicyVersion] = {}
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
                reason="Payroll monetary-policy test fixture",
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
                reason="Payroll monetary-policy test activation",
            )
            self.monetary_policies[code] = policy
            self.monetary_policy_versions[code] = version

    def _replace_money_precision_policy(self, money_scale: int) -> PlatformPolicyVersion:
        policy = self.monetary_policies[ACCOUNTING_MONEY_PRECISION_POLICY_CODE]
        previous = self.monetary_policy_versions[
            ACCOUNTING_MONEY_PRECISION_POLICY_CODE
        ]
        previous_selection = TenantPolicySelection.objects.get(
            organization=self.organization,
            policy=policy,
            status=TenantPolicySelectionStatus.ACTIVE,
        )
        previous_selection.status = TenantPolicySelectionStatus.SUPERSEDED
        previous_selection.save(update_fields=["status", "updated_at"])
        parameters = initial_accounting_policy_parameters(
            ACCOUNTING_MONEY_PRECISION_POLICY_CODE
        )
        parameters["money_scale"] = money_scale
        now = timezone.now()
        version = PlatformPolicyVersion.objects.create(
            policy=policy,
            version=previous.version + 1,
            parameters=parameters,
            effective_from=timezone.localdate(),
            status=PolicyVersionStatus.PUBLISHED,
            source_basis=PolicySourceBasis.PRODUCT_DEFINED,
            supersedes=previous,
            created_by=self.owner,
            published_by=self.owner,
            published_at=now,
            reason="Payroll monetary-policy test replacement",
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
            supersedes=previous_selection,
            reason="Payroll monetary-policy test replacement activation",
        )
        self.monetary_policy_versions[ACCOUNTING_MONEY_PRECISION_POLICY_CODE] = version
        return version

    def _component(
        self, code: str, kind: str, effect: str, *, statutory: bool = False
    ) -> PayrollComponent:
        return create_component(
            organization=self.organization,
            actor=self.actor,
            code=code,
            name=code,
            kind=kind,
            net_effect=effect,
            is_statutory_reserved=statutory,
        )

    def _fixed_rule(
        self,
        component: PayrollComponent,
        amount: str,
        *,
        sequence: int,
        code: str | None = None,
    ):
        rule = create_rule(
            organization=self.organization,
            actor=self.actor,
            component=component,
            code=code or f"RULE-{component.code}",
            name=f"Rule {component.code}",
            sequence=sequence,
            method=CalculationMethod.FIXED_AMOUNT,
            fixed_amount=Decimal(amount),
            effective_from=date(2026, 1, 1),
            source_reference=f"policy-{component.code}-v1",
        )
        return activate_rule(
            organization=self.organization, actor=self.actor, rule=rule
        )

    def _run(self, code: str = "RUN-01", *, kind: str = PayrollRunKind.REGULAR):
        return create_run(
            organization=self.organization,
            actor=self.actor,
            period=self.period,
            code=code,
            kind=kind,
            idempotency_key=f"idempotency-{code}",
            employees=[self.employee],
        )

    def _finalized_run(self):
        earning = self._component(
            "BASE", ComponentKind.EARNING, NetEffect.ADD
        )
        allowance = self._component(
            "ALLOW", ComponentKind.ALLOWANCE, NetEffect.ADD
        )
        deduction = self._component(
            "DEDUCT", ComponentKind.DEDUCTION, NetEffect.SUBTRACT
        )
        self._fixed_rule(earning, "1000.005", sequence=10)
        percentage_rule = create_rule(
            organization=self.organization,
            actor=self.actor,
            component=allowance,
            code="ALLOW-PERCENT",
            name="Configured allowance",
            sequence=20,
            method=CalculationMethod.PERCENT_OF_COMPONENT,
            percentage=Decimal(10),
            basis_component=earning,
            effective_from=date(2026, 1, 1),
            source_reference="allowance-policy-v1",
        )
        activate_rule(
            organization=self.organization,
            actor=self.actor,
            rule=percentage_rule,
        )
        self._fixed_rule(deduction, "100.004", sequence=30)
        run = self._run()
        lock_run_inputs(organization=self.organization, actor=self.actor, run=run)
        calculate_run(organization=self.organization, actor=self.actor, run=run)
        submit_run_for_review(
            organization=self.organization, actor=self.actor, run=run
        )
        approve_run(organization=self.organization, actor=self.actor, run=run)
        finalize_run(organization=self.organization, actor=self.actor, run=run)
        return PayrollRun.objects.get(pk=run.pk)

    def test_effective_pay_versions_are_non_overlapping_and_snapshots_pin_version(
        self,
    ) -> None:
        replacement = create_employment_configuration(
            organization=self.organization,
            actor=self.actor,
            employee=self.employee,
            pay_model="hourly",
            base_rate=Decimal(75),
            rate_unit="hour",
            effective_from=date(2026, 11, 1),
            source_reference="employment-offer-v2",
        )
        with self.assertRaises(ValidationError):
            activate_employment_configuration(
                organization=self.organization,
                actor=self.actor,
                configuration=replacement,
            )
        retire_employment_configuration(
            organization=self.organization,
            actor=self.actor,
            configuration=self.configuration,
            effective_to=date(2026, 10, 31),
        )
        activate_employment_configuration(
            organization=self.organization,
            actor=self.actor,
            configuration=replacement,
        )
        self.configuration.refresh_from_db()
        replacement.refresh_from_db()
        self.assertEqual(self.configuration.status, ConfigurationStatus.RETIRED)
        self.assertEqual(replacement.status, ConfigurationStatus.ACTIVE)
        self.assertEqual(replacement.version, 2)

        component = self._component(
            "VERSIONED-EARNING", ComponentKind.EARNING, NetEffect.ADD
        )
        first_rule = self._fixed_rule(component, "100", sequence=10)
        second_rule = create_rule(
            organization=self.organization,
            actor=self.actor,
            component=component,
            code=first_rule.code,
            name="Rule VERSIONED-EARNING v2",
            sequence=10,
            method=CalculationMethod.FIXED_AMOUNT,
            fixed_amount=Decimal(125),
            effective_from=date(2026, 11, 1),
            source_reference="policy-versioned-earning-v2",
        )
        with self.assertRaises(ValidationError):
            activate_rule(
                organization=self.organization,
                actor=self.actor,
                rule=second_rule,
            )
        retire_rule(
            organization=self.organization,
            actor=self.actor,
            rule=first_rule,
            effective_to=date(2026, 10, 31),
        )
        activate_rule(
            organization=self.organization,
            actor=self.actor,
            rule=second_rule,
        )
        run = self._run()
        lock_run_inputs(organization=self.organization, actor=self.actor, run=run)
        snapshot = PayrollInputSnapshot.objects.get(run=run)
        self.assertEqual(snapshot.employment_version, 1)
        self.assertEqual(snapshot.rule_version, 1)
        self.assertEqual(snapshot.rule_id, first_rule.pk)

    def test_decimal_calculation_lineage_same_user_finalization_and_immutability(
        self,
    ) -> None:
        before = (
            JournalEntry.objects.count(),
            Obligation.objects.count(),
            TreasuryMovement.objects.count(),
            ProjectCostFact.objects.count(),
        )
        run = self._finalized_run()
        result = run.employee_results.get()
        self.assertEqual(result.gross_amount, Decimal(1100))
        self.assertEqual(result.deduction_amount, Decimal(100))
        self.assertEqual(result.net_amount, Decimal(1000))
        self.assertEqual(run.finalized_by, self.actor)
        self.assertEqual(run.reviewed_by, self.actor)
        self.assertEqual(run.created_by, self.actor)
        self.assertTrue(run.input_digest)
        self.assertTrue(run.calculation_digest)
        lines = PayrollResultLine.objects.filter(run=run)
        self.assertEqual(lines.count(), 3)
        self.assertTrue(
            all(line.explanation.get("input_digest") for line in lines)
        )
        self.assertEqual(PayrollInputSnapshot.objects.filter(run=run).count(), 3)
        payslip = Payslip.objects.get(run_employee=result)
        self.assertEqual(payslip.presentation_snapshot["net_amount"], "1000.00")
        self.assertEqual(
            view_payslip(
                organization=self.organization, actor=self.actor, payslip=payslip
            ).pk,
            payslip.pk,
        )
        self.assertEqual(
            export_payslip(
                organization=self.organization, actor=self.actor, payslip=payslip
            )["net_amount"],
            "1000.00",
        )
        with self.assertRaises(PermissionDenied):
            view_payslip(
                organization=self.organization, actor=self.denied, payslip=payslip
            )
        run.code = "MUTATED"
        with self.assertRaises(ValidationError):
            run.save()
        result.gross_amount = Decimal(1)
        with self.assertRaises(ValidationError):
            result.save()
        self.assertEqual(
            before,
            (
                JournalEntry.objects.count(),
                Obligation.objects.count(),
                TreasuryMovement.objects.count(),
                ProjectCostFact.objects.count(),
            ),
        )

    def test_currency_precision_policy_rounds_and_pins_historical_runs(self) -> None:
        zero_component = self._component(
            "ZERO-DECIMAL", ComponentKind.EARNING, NetEffect.ADD
        )
        zero_rule = self._fixed_rule(zero_component, "10.5", sequence=10)
        zero_run = self._run("ROUND-0")
        lock_run_inputs(
            organization=self.organization, actor=self.actor, run=zero_run
        )
        calculate_run(organization=self.organization, actor=self.actor, run=zero_run)
        zero_run.refresh_from_db()
        self.assertEqual(zero_run.monetary_policy_snapshot["money_scale"], 0)
        self.assertEqual(
            zero_run.employee_results.get().lines.get(component=zero_component).amount,
            Decimal(11),
        )
        retire_rule(
            organization=self.organization,
            actor=self.actor,
            rule=zero_rule,
            effective_to=date(2026, 10, 22),
        )

        two_decimal_precision = self._replace_money_precision_policy(2)
        two_component = self._component(
            "TWO-DECIMAL", ComponentKind.EARNING, NetEffect.ADD
        )
        self._fixed_rule(two_component, "10.005", sequence=10)
        two_period = create_period(
            organization=self.organization,
            actor=self.actor,
            code="1405-08",
            name="دوره آبان ۱۴۰۵",
            starts_on=date(2026, 10, 23),
            ends_on=date(2026, 11, 21),
            cutoff_at=datetime(2026, 11, 22, 12, tzinfo=ZoneInfo("Asia/Tehran")),
        )
        two_run = create_run(
            organization=self.organization,
            actor=self.actor,
            period=two_period,
            code="ROUND-2",
            idempotency_key="round-2",
            employees=[self.employee],
        )
        lock_run_inputs(
            organization=self.organization, actor=self.actor, run=two_run
        )
        two_run.refresh_from_db()
        self.assertEqual(two_run.precision_policy_version_id, two_decimal_precision.pk)
        self.assertEqual(two_run.monetary_policy_snapshot["money_scale"], 2)
        self.assertEqual(two_run.monetary_policy_snapshot["final_quantum"], "0.01")

        self._replace_money_precision_policy(0)
        calculate_run(organization=self.organization, actor=self.actor, run=two_run)
        two_result = two_run.employee_results.get()
        two_line = two_result.lines.get(component=two_component)
        self.assertEqual(two_line.amount, Decimal("10.01"))
        self.assertEqual(two_line.explanation["rounding"], "ROUND_HALF_UP:0.01")
        self.assertEqual(
            two_line.explanation["precision_policy_version"],
            two_decimal_precision.version,
        )

    def test_missing_variable_input_fails_closed_then_locks_exact_snapshot(self) -> None:
        earning = self._component("HOURS", ComponentKind.EARNING, NetEffect.ADD)
        rule = create_rule(
            organization=self.organization,
            actor=self.actor,
            component=earning,
            code="HOURS-RULE",
            name="Explicit hours",
            sequence=10,
            method=CalculationMethod.QUANTITY_TIMES_RATE,
            rate_source=RateSource.EMPLOYMENT,
            effective_from=date(2026, 1, 1),
            source_reference="configured-hour-rule",
        )
        rule = activate_rule(
            organization=self.organization, actor=self.actor, rule=rule
        )
        run = self._run()
        with self.assertRaises(ValidationError):
            lock_run_inputs(
                organization=self.organization, actor=self.actor, run=run
            )
        self.assertTrue(
            PayrollException.objects.filter(
                run=run, code="MISSING_INPUT_HOURS-RULE", is_resolved=False
            ).exists()
        )
        item = record_input(
            organization=self.organization,
            actor=self.actor,
            run=run,
            employee=self.employee,
            rule=rule,
            quantity=Decimal("160.25000000"),
            source_type="approved_timesheet",
            source_reference="timesheet:approved:001",
            source_version="3",
            source_status="approved",
            source_payload={"minutes": 9615, "approval": "TS-001"},
        )
        lock_run_inputs(organization=self.organization, actor=self.actor, run=run)
        item.source_payload = {"minutes": 1}
        with self.assertRaises(ValidationError):
            item.save()
        snapshot = PayrollInputSnapshot.objects.get(run=run)
        self.assertEqual(snapshot.quantity, Decimal("160.25000000"))
        self.assertEqual(snapshot.rate, Decimal("50.12500000"))
        self.assertEqual(snapshot.source_payload["minutes"], 9615)

    def test_locked_snapshot_is_authoritative_after_component_catalogue_change(
        self,
    ) -> None:
        earning = self._component(
            "SNAPSHOT-EARNING", ComponentKind.EARNING, NetEffect.ADD
        )
        self._fixed_rule(earning, "10.005", sequence=10)
        run = self._run()
        lock_run_inputs(organization=self.organization, actor=self.actor, run=run)

        earning.name = "Later catalogue name"
        earning.kind = ComponentKind.DEDUCTION
        earning.net_effect = NetEffect.SUBTRACT
        earning.save()

        calculate_run(organization=self.organization, actor=self.actor, run=run)
        submit_run_for_review(
            organization=self.organization, actor=self.actor, run=run
        )
        approve_run(organization=self.organization, actor=self.actor, run=run)
        finalize_run(organization=self.organization, actor=self.actor, run=run)

        result = PayrollRunEmployee.objects.get(run=run)
        self.assertEqual(result.gross_amount, Decimal(10))
        self.assertEqual(result.deduction_amount, Decimal(0))
        self.assertEqual(result.net_amount, Decimal(10))
        line = result.lines.get()
        self.assertEqual(line.component_kind, ComponentKind.EARNING)
        payslip_line = result.payslip.presentation_snapshot["lines"][0]
        self.assertEqual(payslip_line["component_name"], "SNAPSHOT-EARNING")
        self.assertEqual(payslip_line["component_kind"], ComponentKind.EARNING)

    def test_negative_net_is_explicit_exception_and_cannot_finalize(self) -> None:
        earning = self._component("SMALL", ComponentKind.EARNING, NetEffect.ADD)
        deduction = self._component(
            "LARGE-DEDUCTION", ComponentKind.DEDUCTION, NetEffect.SUBTRACT
        )
        self._fixed_rule(earning, "100", sequence=10)
        self._fixed_rule(deduction, "200", sequence=20)
        run = self._run()
        lock_run_inputs(organization=self.organization, actor=self.actor, run=run)
        run = calculate_run(
            organization=self.organization, actor=self.actor, run=run
        )
        self.assertEqual(run.status, PayrollRunStatus.EXCEPTION)
        result = run.employee_results.get()
        self.assertEqual(result.net_amount, Decimal(0))
        self.assertEqual(result.status, ResultStatus.EXCEPTION)
        exception = run.exceptions.get(code="NEGATIVE_NET_PAY", is_resolved=False)
        self.assertEqual(Decimal(exception.details["calculated_net_amount"]), Decimal(-100))
        self.assertEqual(Decimal(exception.details["unallocated_negative_amount"]), Decimal(100))
        self.assertEqual(exception.details["carry_forward_route"], None)
        self.assertEqual(
            negative_net_carry_forward_candidate(
                organization=self.organization, actor=self.actor, exception=exception
            ),
            {
                "source_run_id": str(run.pk),
                "source_result_id": str(result.pk),
                "source_input_digest": run.input_digest,
                "source_calculation_digest": run.calculation_digest,
                "amount": exception.details["unallocated_negative_amount"],
                "recognition_route": None,
                "postable": False,
            },
        )
        with self.assertRaises(ValidationError):
            review_negative_net_exception(
                organization=self.organization,
                actor=self.actor,
                exception=exception,
                reason=" ",
            )
        with self.assertRaises(PermissionDenied):
            review_negative_net_exception(
                organization=self.organization,
                actor=self.denied,
                exception=exception,
                reason="Review",
            )
        with patch(
            "apps.payroll.services.record_audit_event",
            side_effect=RuntimeError("audit unavailable"),
        ), self.assertRaises(RuntimeError):
            review_negative_net_exception(
                organization=self.organization,
                actor=self.actor,
                exception=exception,
                reason="Review must be auditable",
            )
        self.assertFalse(
            AuditEvent.objects.filter(
                organization=self.organization,
                action=AuditAction.PAYROLL_NEGATIVE_NET_REVIEWED,
                entity_id=str(exception.pk),
            ).exists()
        )
        review_negative_net_exception(
            organization=self.organization,
            actor=self.actor,
            exception=exception,
            reason="Remain held pending an approved recognition route",
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                organization=self.organization,
                action=AuditAction.PAYROLL_NEGATIVE_NET_REVIEWED,
                entity_id=str(exception.pk),
            ).exists()
        )
        exception.refresh_from_db()
        self.assertFalse(exception.is_resolved)
        self.assertEqual(JournalEntry.objects.filter(organization=self.organization).count(), 0)
        self.assertEqual(Obligation.objects.filter(organization=self.organization).count(), 0)
        self.assertEqual(TreasuryMovement.objects.filter(organization=self.organization).count(), 0)
        self.assertEqual(ProjectCostFact.objects.filter(organization=self.organization).count(), 0)
        with self.assertRaises(ValidationError):
            submit_run_for_review(
                organization=self.organization, actor=self.actor, run=run
            )
        with self.assertRaises(ValidationError):
            finalize_run(organization=self.organization, actor=self.actor, run=run)
        replacement = create_run(
            organization=self.organization,
            actor=self.actor,
            period=self.period,
            code="RUN-NEG-RPL",
            idempotency_key="negative-replacement",
            employees=[self.employee],
            kind=PayrollRunKind.REPLACEMENT,
            predecessor=run,
            replaces=run,
        )
        self.assertEqual(replacement.employee_results.get().predecessor_result_id, result.pk)
        self.assertEqual(run.employee_results.get().net_amount, Decimal(0))

    def test_off_cycle_adjustment_and_reversal_replacement_keep_lineage_and_idempotency(
        self,
    ) -> None:
        run = self._finalized_run()
        reversal = reverse_run(
            organization=self.organization,
            actor=self.actor,
            original_run=run,
            reason="اصلاح کنترل‌شده مبلغ",
            idempotency_key="reverse-run-01",
            create_replacement=True,
            replacement_code="RUN-01-RPL",
        )
        same = reverse_run(
            organization=self.organization,
            actor=self.actor,
            original_run=PayrollRun.objects.get(pk=run.pk),
            reason="اصلاح کنترل‌شده مبلغ",
            idempotency_key="reverse-run-01",
            create_replacement=True,
            replacement_code="RUN-01-RPL",
        )
        self.assertEqual(same.pk, reversal.pk)
        run.refresh_from_db()
        self.assertEqual(run.status, PayrollRunStatus.REVERSED)
        self.assertEqual(reversal.reversal_run.status, PayrollRunStatus.FINALIZED)
        self.assertEqual(reversal.replacement_run.status, PayrollRunStatus.DRAFT)
        self.assertEqual(reversal.replacement_run.replaces_id, run.pk)
        original_net = run.employee_results.get().net_amount
        reversal_net = reversal.reversal_run.employee_results.get().net_amount
        self.assertEqual(reversal_net, -original_net)
        self.assertTrue(
            reversal.reversal_run.result_lines.filter(is_reversal=True).exists()
        )

        # A separate off-cycle run records arrears without rewriting the old run.
        off_cycle = self._run(code="OFF-01", kind=PayrollRunKind.OFF_CYCLE)
        earning = PayrollComponent.objects.get(code="BASE")
        record_adjustment(
            organization=self.organization,
            actor=self.actor,
            run=off_cycle,
            employee=self.employee,
            component=earning,
            kind="arrears",
            amount=Decimal("25.125"),
            effective_on=date(2026, 10, 1),
            source_reference="arrears-case-1",
            reason="معوقه صریح دوره قبل",
            original_result=run.employee_results.get(),
        )
        lock_run_inputs(
            organization=self.organization, actor=self.actor, run=off_cycle
        )
        calculate_run(
            organization=self.organization, actor=self.actor, run=off_cycle
        )
        self.assertEqual(
            off_cycle.employee_results.get().net_amount, Decimal(25)
        )

    def test_statutory_rules_are_fail_closed_without_blocking_core_components(self) -> None:
        reserved = self._component(
            "TAX-RESERVED",
            ComponentKind.DEDUCTION,
            NetEffect.SUBTRACT,
            statutory=True,
        )
        rule = create_rule(
            organization=self.organization,
            actor=self.actor,
            component=reserved,
            code="TAX-RULE",
            name="Reserved only",
            sequence=10,
            method=CalculationMethod.FIXED_AMOUNT,
            fixed_amount=Decimal(1),
            effective_from=date(2026, 1, 1),
            source_reference="unresolved-statutory-authority",
            requires_statutory_authority=True,
        )
        with self.assertRaisesRegex(ValidationError, "P7-S23"):
            activate_rule(
                organization=self.organization, actor=self.actor, rule=rule
            )
        ordinary = self._component("ORDINARY", ComponentKind.EARNING, NetEffect.ADD)
        self.assertIsNotNone(self._fixed_rule(ordinary, "10", sequence=20))

    def test_permissions_tenant_isolation_and_audit_rollback(self) -> None:
        with self.assertRaises(PermissionDenied):
            create_component(
                organization=self.organization,
                actor=self.denied,
                code="DENIED",
                name="Denied",
                kind=ComponentKind.EARNING,
                net_effect=NetEffect.ADD,
            )
        other_owner = User.objects.create_user(username="other-payroll-owner")
        other = create_organization_with_owner(
            owner=other_owner, name="Other Payroll", slug="other-payroll"
        )
        other_role = OrganizationRole.objects.create(
            organization=other,
            code="other-payroll-role",
            name="Other payroll role",
            created_by=other_owner,
        )
        other_role.permissions.add(
            *BusinessPermission.objects.filter(code__in=PAYROLL_PERMISSION_CODES)
        )
        other_actor = User.objects.create_user(username="other-payroll-actor")
        other_membership = OrganizationMembership.objects.create(
            organization=other,
            user=other_actor,
            role_definition=other_role,
            status=MembershipStatus.ACTIVE,
            joined_at=timezone.now(),
            assigned_by=other_owner,
        )
        other_membership.role_assignments.create(
            organization=other,
            role=other_role,
            reason="Explicit cross-tenant Payroll test authority",
        )
        other_membership.scope_grants.create(
            organization=other,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="Explicit cross-tenant Payroll test scope",
        )
        with self.assertRaises(ValidationError):
            create_employment_configuration(
                organization=other,
                actor=other_actor,
                employee=self.employee,
                pay_model="salaried",
                base_rate=Decimal(1),
                rate_unit="month",
                effective_from=date(2026, 1, 1),
                source_reference="cross-tenant",
            )
        with patch(
            "apps.payroll.services.record_audit_event",
            side_effect=RuntimeError("audit unavailable"),
        ), self.assertRaises(RuntimeError):
            create_component(
                organization=self.organization,
                actor=self.actor,
                code="ROLLBACK",
                name="Rollback",
                kind=ComponentKind.EARNING,
                net_effect=NetEffect.ADD,
            )
        self.assertFalse(
            PayrollComponent.objects.filter(
                organization=self.organization, code="ROLLBACK"
            ).exists()
        )

        audit_only = self._member(
            "audit-only", [BusinessPermissionCode.AUDIT_VIEW]
        )
        self.assertTrue(
            self.organization.audit_events.filter(
                action__startswith="payroll."
            ).exists()
        )
        self.assertFalse(
            get_organization_audit_events(
                user=audit_only, organization=self.organization
            )
            .filter(action__startswith="payroll.")
            .exists()
        )

    def test_payroll_registry_is_complete_and_default_roles_are_denied(self) -> None:
        model_labels = {
            model._meta.label
            for model in django_apps.get_app_config("payroll").get_models()
        }
        self.assertLessEqual(model_labels, registered_model_labels())
        permission_codes = {code.value for code in PAYROLL_PERMISSION_CODES}
        self.assertLessEqual(permission_codes, registered_permission_codes())
        for default_permissions in DEFAULT_ROLE_PERMISSIONS.values():
            self.assertTrue(permission_codes.isdisjoint(default_permissions))

    def test_core_and_statutory_audit_permissions_do_not_imply_each_other(self) -> None:
        record_audit_event(
            action=AuditAction.PAYROLL_STATUTORY_CALCULATED,
            entity_type="payroll.StatutoryCalculation",
            entity_id="statutory-sensitive",
            organization=self.organization,
            actor=self.actor,
        )
        core_auditor = self._member(
            "core-payroll-auditor",
            [
                BusinessPermissionCode.AUDIT_VIEW,
                BusinessPermissionCode.PAYROLL_AUDIT_VIEW,
            ],
        )
        core_events = get_organization_audit_events(
            user=core_auditor, organization=self.organization
        )
        self.assertTrue(
            core_events.filter(
                action=AuditAction.PAYROLL_CONFIGURATION_RECORDED
            ).exists()
        )
        self.assertFalse(
            core_events.filter(action=AuditAction.PAYROLL_STATUTORY_CALCULATED).exists()
        )

        statutory_auditor = self._member(
            "statutory-payroll-auditor",
            [
                BusinessPermissionCode.AUDIT_VIEW,
                BusinessPermissionCode.PAYROLL_STATUTORY_AUDIT_VIEW,
            ],
        )
        statutory_events = get_organization_audit_events(
            user=statutory_auditor, organization=self.organization
        )
        self.assertTrue(
            statutory_events.filter(
                action=AuditAction.PAYROLL_STATUTORY_CALCULATED
            ).exists()
        )
        self.assertFalse(
            statutory_events.filter(
                action=AuditAction.PAYROLL_CONFIGURATION_RECORDED
            ).exists()
        )

    def test_run_creation_is_idempotent_and_conflicting_reuse_is_rejected(self) -> None:
        run = self._run()
        same = create_run(
            organization=self.organization,
            actor=self.actor,
            period=self.period,
            code="RUN-01",
            kind=PayrollRunKind.REGULAR,
            idempotency_key="idempotency-RUN-01",
            employees=[self.employee],
        )
        self.assertEqual(run.pk, same.pk)
        self.assertEqual(PayrollRun.objects.filter(period=self.period).count(), 1)
        with self.assertRaises(ValidationError):
            create_run(
                organization=self.organization,
                actor=self.actor,
                period=self.period,
                code="OTHER",
                kind=PayrollRunKind.REGULAR,
                idempotency_key="idempotency-RUN-01",
                employees=[self.employee],
            )

    def test_persian_rtl_ui_is_permission_gated(self) -> None:
        self.client.force_login(self.actor)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()
        response = self.client.get(reverse("payroll:workbench"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<html lang="fa" dir="rtl">', html=False)
        self.assertContains(response, "کارگاه حقوق و دستمزد")
        self.assertEqual(
            self.client.get(reverse("payroll:configuration")).status_code, 200
        )
        run = self._finalized_run()
        payslip = run.payslips.get()
        self.assertEqual(
            self.client.get(
                reverse("payroll:payslip_detail", args=[payslip.pk])
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                reverse("payroll:payslip_export", args=[payslip.pk])
            ).status_code,
            405,
        )
        export_response = self.client.post(
            reverse("payroll:payslip_export", args=[payslip.pk])
        )
        self.assertEqual(export_response.status_code, 200)
        self.assertEqual(
            export_response.headers["Content-Type"],
            "application/json; charset=utf-8",
        )
        self.assertEqual(
            self.client.get(reverse("payroll:audit_history")).status_code, 200
        )
        self.client.force_login(self.denied)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()
        self.assertEqual(
            self.client.get(reverse("payroll:workbench")).status_code, 403
        )
        self.assertEqual(
            self.client.get(
                reverse("payroll:payslip_detail", args=[payslip.pk])
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(reverse("payroll:audit_history")).status_code, 403
        )

    def test_period_overlap_is_rejected_and_finalization_locks_period(self) -> None:
        with self.assertRaises(ValidationError):
            create_period(
                organization=self.organization,
                actor=self.actor,
                code="OVERLAP",
                name="Overlap",
                starts_on=date(2026, 10, 1),
                ends_on=date(2026, 10, 31),
                cutoff_at=datetime(
                    2026, 11, 1, 12, tzinfo=ZoneInfo("Asia/Tehran")
                ),
            )
        run = self._finalized_run()
        self.period.refresh_from_db()
        self.assertEqual(self.period.status, PayrollPeriodStatus.FINALIZED)
        self.assertEqual(run.status, PayrollRunStatus.FINALIZED)


class PayrollConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def test_concurrent_same_key_run_creation_has_one_effect(self) -> None:
        owner = User.objects.create_user(username="payroll-race-owner")
        organization = create_organization_with_owner(
            owner=owner, name="Payroll Race", slug="payroll-race"
        )
        actor = User.objects.create_user(username="payroll-race-actor")
        role = OrganizationRole.objects.create(
            organization=organization,
            code="payroll-race-role",
            name="Payroll race role",
            created_by=owner,
        )
        role.permissions.add(
            *BusinessPermission.objects.filter(
                code=BusinessPermissionCode.PAYROLL_PREPARE
            )
        )
        membership = OrganizationMembership.objects.create(
            organization=organization,
            user=actor,
            role_definition=role,
            status=MembershipStatus.ACTIVE,
            joined_at=timezone.now(),
            assigned_by=owner,
        )
        membership.role_assignments.create(
            organization=organization,
            role=role,
            reason="Explicit Payroll concurrency test authority",
        )
        membership.scope_grants.create(
            organization=organization,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="Explicit Payroll concurrency test scope",
        )
        employee = Employee.objects.create(
            organization=organization,
            employee_number="RACE-001",
            first_name="Race",
            last_name="Employee",
        )
        period = create_period(
            organization=organization,
            actor=actor,
            code="RACE-PERIOD",
            name="Race period",
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 1, 31),
            cutoff_at=datetime(2026, 2, 1, tzinfo=ZoneInfo("Asia/Tehran")),
        )

        def create_once(_: int) -> str:
            close_old_connections()
            try:
                run = create_run(
                    organization=Organization.objects.get(pk=organization.pk),
                    actor=User.objects.get(pk=actor.pk),
                    period=period.__class__.objects.get(pk=period.pk),
                    code="RACE-RUN",
                    idempotency_key="race-run-key",
                    employees=[Employee.objects.get(pk=employee.pk)],
                )
                return str(run.pk)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            identifiers = list(executor.map(create_once, range(2)))
        self.assertEqual(len(set(identifiers)), 1)
        self.assertEqual(
            PayrollRun.objects.filter(
                organization=organization, idempotency_key="race-run-key"
            ).count(),
            1,
        )
