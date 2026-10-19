"""INT-B08 native proposal/target transactions with synthetic approved bindings."""

import json
from datetime import date
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase, TransactionTestCase
from django.utils import timezone

from apps.accounting import test_cep042_regression as retained
from apps.accounting.models import JournalEntry
from apps.accounting.test_cep042_regression import explicit_fixture_authority
from apps.audit.models import AuditEvent
from apps.organizations.catalog_bootstrap import synchronize_authorization_catalog
from apps.organizations.models import (
    BusinessPermission,
    OrganizationMembership,
    OrganizationRole,
)
from apps.payroll import test_p7_s29_s32_financial_handoffs as payroll_fixtures
from apps.payroll.financial_handoff_services import (
    prepare_financial_handoff,
    review_financial_handoff,
)
from apps.payroll.models import PayrollPeriod, PayrollRun, PayrollRunEmployee
from apps.payroll.services import _monetary_policy_snapshot, reverse_run
from apps.projects import actual_integration as integration
from apps.projects import test_cep047_actual as actual_fixtures
from apps.projects.actual_sources import (
    ActualRejected,
    NativeActualSource,
    native_lineage,
)
from apps.projects.models import ProjectCostFact
from apps.projects.services import (
    approve_project_cost_source_contract,
    create_project_cost_source_contract,
)
from apps.subledgers.models import Obligation
from apps.timekeeping.models import Timesheet, TimesheetEntry
from apps.treasury.models import TreasuryMovement
from apps.workflows.catalog_bootstrap import synchronize_workflow_catalog
from apps.workforce.models import Employee

KEY = "pcp-payr-actual"


class PayrollLineageUnitTests(SimpleTestCase):
    def test_audit_lineage_retains_source_line_ids_without_employee_or_payee_detail(
        self,
    ):
        source = NativeActualSource(
            KEY,
            "payroll.financialhandoffproposal",
            "proposal",
            "version",
            {
                "payroll": {
                    "run_id": "run",
                    "allocation_line_ids": ["line"],
                    "employee_number": "private",
                    "employee_name": "private",
                }
            },
            Decimal(100),
            "IRR",
            "",
            True,
            "recognize",
        )
        self.assertEqual(
            native_lineage(source),
            {"payroll": {"run_id": "run", "allocation_line_ids": ["line"]}},
        )


class PayrollActualTests(TransactionTestCase):
    _draft = actual_fixtures.ActualTargetTests._draft
    _classify_and_submit = actual_fixtures.ActualTargetTests._classify_and_submit
    read_source = actual_fixtures.ActualTargetTests.read_source
    consume = actual_fixtures.ActualTargetTests.consume
    _monetary_versions = (
        payroll_fixtures.PayrollFinancialHandoffTests._monetary_versions
    )

    def setUp(self):
        synchronize_workflow_catalog(using="default")
        actual_fixtures.ActualTargetTests.setUp(self)
        self.native_patch.stop()
        self.owner = self.preparer
        self.owner_membership = OrganizationMembership.objects.get(
            organization=self.organization, user=self.owner
        )
        role = OrganizationRole.objects.create(
            organization=self.organization,
            code="cep048-synthetic-source-authority",
            name="Explicit synthetic Payroll source authority",
            created_by=self.owner,
        )
        role.permissions.add(
            *BusinessPermission.objects.exclude(
                code__startswith="accounting_recognition."
            )
        )
        for actor in (self.preparer, self.approver):
            explicit_fixture_authority(
                OrganizationMembership.objects.get(
                    organization=self.organization, user=actor
                ),
                role,
            )
        precision_version, rounding_version = self._monetary_versions()
        from apps.accounting.policy_calculations import (
            accounting_rounding_policy_from_version,
            money_precision_policy_from_version,
        )

        self.money = {
            "precision_policy_version": precision_version,
            "rounding_policy_version": rounding_version,
            "monetary_policy_snapshot": _monetary_policy_snapshot(
                currency="IRR",
                precision=money_precision_policy_from_version(
                    precision_version, consumer="payroll.run.lock"
                ),
                rounding=accounting_rounding_policy_from_version(
                    rounding_version, consumer="payroll.run.lock"
                ),
            ),
        }
        self.employee = Employee.objects.create(
            organization=self.organization,
            employee_number="CEP048-EMP",
            first_name="Synthetic",
            last_name="Payroll",
            phone_number="09120000000",
        )
        self.period = PayrollPeriod.objects.create(
            organization=self.organization,
            code="CEP048-PERIOD",
            name="Synthetic period",
            starts_on=date(2026, 9, 23),
            ends_on=date(2026, 10, 22),
            cutoff_at=timezone.now(),
            status="finalized",
            locked_at=timezone.now(),
            finalized_at=timezone.now(),
            created_by=self.owner,
        )
        sheet = Timesheet.objects.create(
            organization=self.organization,
            employee=self.employee,
            period_start=self.period.starts_on,
            period_end=self.period.ends_on,
            revision=1,
            declared_minutes=600,
            prepared_by=self.owner,
        )
        for day, minutes in [(1, 400), (2, 200)]:
            TimesheetEntry.objects.create(
                organization=self.organization,
                timesheet=sheet,
                work_date=date(2026, 10, day),
                project=self.project,
                minutes=minutes,
            )
        Timesheet.objects.filter(pk=sheet.pk).update(state="approved")
        self.run = self.make_run("ORIGINAL")
        self.proposal = self.propose(self.run)
        contract = create_project_cost_source_contract(
            organization=self.organization,
            actor=self.owner,
            producer_key=KEY,
            version=1,
            measure="actual",
            source_model="payroll.financialhandoffproposal",
            event_schema=f"{KEY}.v1",
            classification_policy_reference="TEST-CLASSIFICATION-1",
            recognition_policy_reference="TEST-EXPLICIT-DATE-1",
            reconciliation_policy_reference="TEST-RECONCILIATION-1",
            requires_financial_evidence=True,
        )
        self.contracts[KEY] = approve_project_cost_source_contract(
            contract=contract, actor=self.approver
        )
        self.policies[
            KEY,
            "TEST-CLASSIFICATION-1",
            "TEST-EXPLICIT-DATE-1",
            "TEST-RECONCILIATION-1",
        ] = integration.ActualPolicyBinding(self.map_source)

    def make_run(
        self, code, *, kind="regular", gross="1000.00", employer="200.00", **kwargs
    ):
        run = PayrollRun.objects.create(
            organization=self.organization,
            period=self.period,
            code=f"CEP048-{code}",
            kind=kind,
            status="finalized",
            idempotency_key=f"CEP048-{code}",
            input_digest=f"test-input-{code}",
            calculation_digest=f"test-version-{code}",
            currency="IRR",
            created_by=self.owner,
            finalized_by=self.approver,
            finalized_at=timezone.now(),
            **self.money,
            **kwargs,
        )
        PayrollRunEmployee.objects.create(
            organization=self.organization,
            run=run,
            employee=self.employee,
            status="finalized",
            gross_amount=Decimal(gross),
            employer_amount=Decimal(employer),
            net_amount=Decimal(gross),
        )
        return run

    def propose(self, run, *, family="project_cost", review=True):
        proposal = prepare_financial_handoff(
            organization=self.organization,
            actor=self.owner,
            run=run,
            family=family,
            idempotency_key=f"CEP048-{family}-{run.pk}",
            reason="Synthetic source evidence",
        )
        if review:
            review_financial_handoff(
                organization=self.organization,
                actor=self.approver,
                proposal=proposal,
                disposition="accepted",
                reason="Synthetic independent source review",
            )
        return proposal

    def map_source(self, *, source, **kwargs):
        effects = tuple(
            integration.ActualEffect(
                ("replacement:" if source.operation == "replace_reversed" else "")
                + row["timesheet_entry_id"],
                self.project,
                self.cbs,
                self.wbs,
                self.cost_center,
                Decimal(row["amount"]),
                source.currency,
                date(2026, 10, 14),
                "TEST-PAYROLL-PINNED-VALUE",
                "TEST-PAYROLL-FINANCIAL-EVIDENCE",
            )
            for row in source.evidence["allocations"]
        )
        return integration.ActualMapping(
            effects,
            "TEST-CUTOFF-1",
            "TEST-EXPLICIT-DATE-1",
            "TEST-PAYROLL-NATIVE-POLICY-VERSION",
            "TEST-PROJECT-LABOR-MAPPING-V1",
        )

    def candidate(self, proposal=None, **kwargs):
        return integration.prepare_actual_candidate(
            organization=self.organization,
            actor=kwargs.get("actor", self.owner),
            contract_id=self.contracts[KEY].pk,
            source_id=(proposal or self.proposal).pk,
        )

    def reconcile(self, proposal=None):
        return integration.reconcile_actual_candidate(
            organization=self.organization,
            actor=self.owner,
            contract_id=self.contracts[KEY].pk,
            source_id=(proposal or self.proposal).pk,
        )

    def test_native_l2_allocation_source_line_version_idempotency_and_authority(self):
        other_authorities = (
            JournalEntry.objects.count(),
            Obligation.objects.count(),
            TreasuryMovement.objects.count(),
        )
        candidate = self.candidate()
        self.assertFalse(ProjectCostFact.objects.exists())
        result = self.consume(candidate)
        self.assertEqual(self.consume(candidate).fact_ids, result.fact_ids)
        self.assertEqual(len(result.fact_ids), 2)
        self.assertEqual(
            sum(ProjectCostFact.objects.values_list("amount", flat=True)),
            Decimal("1200.00"),
        )
        self.assertEqual(
            set(ProjectCostFact.objects.values_list("source_version", flat=True)),
            {candidate.source_version},
        )
        self.assertEqual(
            other_authorities,
            (
                JournalEntry.objects.count(),
                Obligation.objects.count(),
                TreasuryMovement.objects.count(),
            ),
        )
        report = self.reconcile()
        self.assertTrue(report["target_payload_matches"])
        self.assertEqual(Decimal(report["mapped_target_difference"]), 0)
        print("CEP048 RECON " + json.dumps(report, sort_keys=True))
        event = AuditEvent.objects.get(
            entity_type=integration.ENTITY, metadata__stage="succeeded"
        )
        self.assertEqual(
            len(event.metadata["native_lineage"]["payroll"]["allocation_line_ids"]), 2
        )
        print("CEP048 TRACE " + json.dumps(event.metadata, sort_keys=True))

    def test_missing_contract_mapping_unreviewed_and_cash_sources_fail_closed(self):
        with self.assertRaisesMessage(
            ActualRejected, "approved_actual_contract_required"
        ):
            integration.prepare_actual_candidate(
                organization=self.organization,
                actor=self.owner,
                contract_id=uuid4(),
                source_id=self.proposal.pk,
            )
        with (
            patch.object(integration, "POLICIES", {}),
            self.assertRaisesMessage(
                ActualRejected, "approved_mapping_cutoff_classification_required"
            ),
        ):
            self.candidate()
        unreviewed = self.propose(
            self.make_run("UNREVIEWED", kind="off_cycle"), review=False
        )
        with self.assertRaises(ActualRejected):
            self.candidate(unreviewed)
        payment = self.propose(self.run, family="payment", review=False)
        with self.assertRaises(ActualRejected):
            self.candidate(payment)
        adjustment = self.propose(
            self.make_run("ADJUSTMENT", kind="adjustment", predecessor=self.run)
        )
        with self.assertRaisesMessage(
            ActualRejected, "approved_payroll_adjustment_mapping_required"
        ):
            self.candidate(adjustment)
        self.assertFalse(ProjectCostFact.objects.exists())

    def test_target_rollback_durable_failure_retry_and_revalidation(self):
        candidate = self.candidate()
        original = integration.record_project_cost_fact

        def fail_after_insert(**kwargs):
            original(**kwargs)
            raise RuntimeError("synthetic target failure")

        with (
            patch.object(
                integration, "record_project_cost_fact", side_effect=fail_after_insert
            ),
            self.assertRaises(RuntimeError),
        ):
            self.consume(candidate)
        self.assertFalse(ProjectCostFact.objects.exists())
        failure = AuditEvent.objects.get(
            entity_type=integration.ENTITY, metadata__stage="failed"
        )
        self.assertEqual(failure.metadata["error_code"], "target_failure")
        with (
            patch.object(integration, "POLICIES", {}),
            self.assertRaises(ActualRejected),
        ):
            self.consume(candidate, retry_of=failure.entity_id)
        result = self.consume(candidate, retry_of=failure.entity_id)
        self.assertEqual(self.consume(candidate).outcome, "replayed")
        self.assertEqual(len(result.fact_ids), 2)
        print(
            "CEP048 TRANSACTION rollback0 -> durable failure -> denied unmapped retry -> revalidated2 -> replay2"
        )

    def test_current_source_version_and_tenant_authority_are_rechecked(self):
        with self.assertRaises(PermissionDenied):
            self.candidate(actor=self.outsider)
        candidate = self.candidate()
        PayrollRun.objects.filter(pk=self.run.pk).update(
            calculation_digest="changed-source"
        )
        with self.assertRaisesMessage(
            ActualRejected, "payroll_source_version_or_policy_mismatch"
        ):
            self.consume(candidate)
        self.assertFalse(ProjectCostFact.objects.exists())

    def test_explicit_native_inverse_then_replacement_does_not_reverse_twice(self):
        candidate = self.candidate()
        original = self.consume(candidate)
        reversal = reverse_run(
            organization=self.organization,
            actor=self.approver,
            original_run=self.run,
            reason="Synthetic governed correction",
            idempotency_key="CEP048-REVERSE",
            create_replacement=False,
        )
        inverse_proposal = self.propose(reversal.reversal_run)
        replacement = self.make_run(
            "REPLACEMENT",
            kind="replacement",
            gross="1100.00",
            employer="220.00",
            replaces=self.run,
            predecessor=reversal.reversal_run,
        )
        replacement_proposal = self.propose(replacement)
        fresh = self.candidate(replacement_proposal)
        with self.assertRaisesMessage(
            ActualRejected, "recognized_native_reversal_required"
        ):
            self.consume(fresh)
        self.assertEqual(ProjectCostFact.objects.count(), 2)
        inverse = self.consume(self.candidate(inverse_proposal))
        self.assertEqual(len(inverse.fact_ids), 2)
        successor = self.consume(fresh)
        self.assertEqual(len(successor.fact_ids), 2)
        self.assertEqual(self.consume(fresh).fact_ids, successor.fact_ids)
        self.assertEqual(self.consume(candidate).fact_ids, original.fact_ids)
        self.assertEqual(ProjectCostFact.objects.count(), 6)
        self.assertEqual(
            ProjectCostFact.objects.filter(kind="actual_reversal").count(), 2
        )
        self.assertEqual(
            sum(ProjectCostFact.objects.values_list("amount", flat=True)),
            Decimal("1320.00"),
        )
        report = self.reconcile()
        self.assertFalse(report["source_active"])
        self.assertEqual(Decimal(report["lineage_net_amount"]), Decimal("1320.00"))
        self.assertEqual(set(report["target_reversals"]), set(inverse.fact_ids))
        print("CEP048 CORRECTION_RECON " + json.dumps(report, sort_keys=True))
        for event in AuditEvent.objects.filter(
            entity_type=integration.ENTITY, metadata__stage="succeeded"
        ).order_by("created_at"):
            print(
                "CEP048 CORRECTION_TRACE " + json.dumps(event.metadata, sort_keys=True)
            )


class RetainedPayrollHandoffRegression(retained.PayrollAffectedRegression):
    def setUp(self):
        synchronize_authorization_catalog(using="default")
        synchronize_workflow_catalog(using="default")
        super().setUp()
