"""Synthetic finalized Payroll sources, real AP services and PostgreSQL races."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from apps.accounting.models import Account, ControlAccountMappingVersion, JournalEntry
from apps.accounting.test_cep042_regression import explicit_fixture_authority
from apps.audit.models import AuditAction, AuditEvent
from apps.organizations.models import BusinessPermission, OrganizationMembership
from apps.organizations.models import BusinessPermissionCode as P
from apps.organizations.role_defaults import DEFAULT_ROLE_PERMISSIONS
from apps.organizations.services import create_organization_with_owner
from apps.parties.models import BusinessParty
from apps.payroll import test_p7_s29_s32_financial_handoffs as source_scenarios
from apps.payroll.financial_handoff_services import (
    prepare_financial_handoff,
    review_financial_handoff,
)
from apps.payroll.models import PayrollResultLine, PayrollRun, PayrollRunEmployee
from apps.payroll.services import reverse_run
from apps.projects.models import ProjectCostFact
from apps.treasury.models import TreasuryMovement

from . import payroll_handoffs as api
from .models import Obligation
from .payroll_models import (
    PayrollAPDraft,
    PayrollAPEnrollment,
    PayrollAPOperation,
    PayrollAPReversal,
)
from .services import (
    _require_unreversed_source,
    _source_reversed_amount_as_of,
)


class PayrollAPFixture:
    _member = source_scenarios.PayrollFinancialHandoffTests._member
    _monetary_versions = (
        source_scenarios.PayrollFinancialHandoffTests._monetary_versions
    )
    _prepare = source_scenarios.PayrollFinancialHandoffTests._prepare

    def setUp(self):
        source_scenarios.PayrollFinancialHandoffTests.setUp(self)
        self.day = date(2026, 10, 18)
        self.ap_permissions = [
            P.SUBLEDGERS_PAYROLL_ENROLLMENTS_MANAGE,
            P.SUBLEDGERS_PAYROLL_ENROLLMENTS_APPROVE,
            P.SUBLEDGERS_PAYROLL_PREPARE,
            P.SUBLEDGERS_PAYROLL_VIEW,
            P.SUBLEDGERS_OBLIGATIONS_RECOGNIZE,
            P.SUBLEDGERS_SOURCES_REVERSE,
            P.PAYROLL_ADJUST,
        ]
        membership = OrganizationMembership.objects.get(
            organization=self.organization, user=self.actor
        )
        membership.role_definition.permissions.add(
            *BusinessPermission.objects.filter(code__in=self.ap_permissions)
        )
        explicit_fixture_authority(membership, membership.role_definition)
        for actor in (self.reviewer, self.denied):
            m = OrganizationMembership.objects.get(
                organization=self.organization, user=actor
            )
            explicit_fixture_authority(m, m.role_definition)
        self.ap_membership = membership
        self.party = BusinessParty.objects.create(
            organization=self.organization,
            party_kind="individual",
            display_name="Synthetic explicitly mapped payee",
            created_by=self.owner,
            updated_by=self.owner,
        )
        self.account = Account.objects.create(
            organization=self.organization,
            code="AP043",
            name="Explicit synthetic AP control",
            account_type="liability",
            is_posting=True,
            created_by=self.owner,
        )
        ControlAccountMappingVersion.objects.create(
            organization=self.organization,
            source_kind=api.SOURCE_KIND,
            direction="payable",
            version=1,
            control_account=self.account,
            effective_from=date(2026, 1, 1),
            reason="Explicit synthetic AP mapping",
            created_by=self.ap_membership,
        )
        self.proposal = self.source(self.run, "original")

    def source(self, run, key):
        result = prepare_financial_handoff(
            organization=self.organization,
            actor=self.actor,
            run=run,
            family="liability",
            idempotency_key=key,
            reason="Synthetic finalized source",
        )
        review_financial_handoff(
            organization=self.organization,
            actor=self.reviewer,
            proposal=result,
            disposition="accepted",
            reason="Source review only",
        )
        return result

    def enrollment(self, proposal=None, *, activate=True):
        proposal = proposal or self.proposal
        lines = list(proposal.lines.all())
        line = lines[0]
        value = api.prepare_enrollment(
            organization=self.organization,
            actor=self.actor,
            category=line.line_kind,
            assignments={
                str(item.pk): {
                    "party_id": str(self.party.pk),
                    "recognized_on": self.day.isoformat(),
                    "due_date": (self.day + timedelta(days=10)).isoformat(),
                    "grouping_reference": "explicit-occurrence",
                }
                for item in lines
            },
            evidence_reference="Approved synthetic EXT0013 contract; no seeded production policy",
        )
        if activate:
            now = max(timezone.now(), getattr(self, "clock", timezone.now()))
            api.change_enrollment(
                organization=self.organization,
                actor=self.actor,
                enrollment=value,
                kind="activate",
                effective_at=now + timedelta(seconds=1),
                reason="Explicit AP activation",
            )
            self.clock = now + timedelta(seconds=2)
        return value

    def prepare(self, proposal=None, key="request", **kwargs):
        with patch.object(api.timezone, "now", return_value=self.clock):
            return api.prepare_payroll_ap(
                organization=self.organization,
                actor=self.actor,
                proposal=proposal or self.proposal,
                idempotency_key=key,
                reason="Explicit AP request",
                **kwargs,
            )

    def accept(self, draft):
        with patch.object(api.timezone, "now", return_value=self.clock):
            return api.accept_payroll_ap_draft(
                organization=self.organization,
                actor=self.actor,
                draft=draft,
                idempotency_key=f"recognize:{draft.pk}",
            )

    def correction_sources(self, *, replace=True):
        chain = reverse_run(
            organization=self.organization,
            actor=self.actor,
            original_run=self.run,
            reason="Explicit Payroll correction",
            idempotency_key="native-reversal",
            create_replacement=replace,
        )
        reversal = self.source(chain.reversal_run, "reversal")
        if not replace:
            return reversal, None
        run = chain.replacement_run
        # Explicit finalized source fixture, not a claim to exercise Payroll calculation.
        PayrollRun.objects.filter(pk=run.pk).update(
            status="finalized",
            calculation_digest="replacement-v1",
            precision_policy_version=self.run.precision_policy_version,
            rounding_policy_version=self.run.rounding_policy_version,
            monetary_policy_snapshot=self.run.monetary_policy_snapshot,
            finalized_at=timezone.now(),
            finalized_by=self.actor,
        )
        for result in run.employee_results.all():
            PayrollRunEmployee.objects.filter(pk=result.pk).update(
                status="finalized",
                gross_amount=Decimal(1100),
                deduction_amount=Decimal(100),
                employer_amount=Decimal(200),
                net_amount=Decimal(1000),
            )
            PayrollResultLine.objects.create(
                organization=self.organization,
                run=run,
                run_employee=result,
                component=self.component,
                sequence=10,
                component_kind="earning",
                unrounded_amount=1100,
                amount=1100,
                explanation={"source": "Synthetic replacement finalized source"},
            )
        run.refresh_from_db()
        return reversal, self.source(run, "replacement")

    def trace(self, proposal=None):
        result = api.reconcile_payroll_ap(
            organization=self.organization,
            actor=self.actor,
            proposal=proposal or self.proposal,
        )
        if os.getenv("BONIRA_CEP043_TRACE"):
            p = Path(os.environ["BONIRA_CEP043_TRACE"])
            rows = json.loads(p.read_text()) if p.exists() else []
            rows.append({**result, "synthetic_data_only": True})
            p.write_text(json.dumps(rows, indent=2) + "\n")
        return result


class PayrollAPHandoffTests(PayrollAPFixture, TestCase):
    def test_unenrolled_and_unactivated_fail_closed_without_downstream_effect(self):
        self.clock = timezone.now()
        with self.assertRaises(ValidationError):
            self.prepare()
        self.enrollment(activate=False)
        with self.assertRaises(ValidationError):
            self.prepare()
        self.assertEqual(PayrollAPDraft.objects.count(), 0)
        self.assertEqual(Obligation.objects.count(), 0)
        self.assertEqual(
            AuditEvent.objects.filter(action=AuditAction.PAYROLL_AP_FAILED).count(), 2
        )

    def test_explicit_draft_is_not_recognition_and_ap_acceptance_is_idempotent(self):
        self.enrollment()
        operation = self.prepare()
        draft = PayrollAPDraft.objects.get(pk=operation.result["drafts"][0])
        self.assertFalse(Obligation.objects.exists())
        self.assertEqual(draft.amount, Decimal(900))
        self.assertEqual(draft.source_version, self.proposal.source_digest)
        target = self.accept(draft)
        self.assertEqual(self.accept(draft).pk, target.pk)
        self.assertEqual(target.source_uuid, draft.pk)
        self.assertEqual(target.source_snapshot["enrollment"], str(draft.enrollment_id))
        self.assertEqual(self.trace()["rows"][0]["obligation"], str(target.pk))
        self.assertFalse(JournalEntry.objects.exists())
        self.assertFalse(TreasuryMovement.objects.exists())
        self.assertFalse(ProjectCostFact.objects.exists())

    def test_exact_occurrence_replay_and_conflicting_payload(self):
        self.enrollment()
        result = self.prepare()
        self.assertEqual(self.prepare(key="another-request").pk, result.pk)
        with self.assertRaises(ValidationError):
            api.prepare_payroll_ap(
                organization=self.organization,
                actor=self.actor,
                proposal=self.proposal,
                idempotency_key="request",
                reason="Conflicting reason",
            )
        self.assertEqual(PayrollAPOperation.objects.count(), 1)
        self.assertEqual(PayrollAPDraft.objects.count(), 1)

    def test_source_review_does_not_grant_ap_enrollment_or_recognition(self):
        self.enrollment()
        draft = PayrollAPDraft.objects.get(pk=self.prepare().result["drafts"][0])
        with self.assertRaises(PermissionDenied):
            api.accept_payroll_ap_draft(
                organization=self.organization,
                actor=self.reviewer,
                draft=draft,
                idempotency_key="denied",
            )
        with self.assertRaises(PermissionDenied):
            api.prepare_enrollment(
                organization=self.organization,
                actor=self.reviewer,
                category="employee_payable",
                assignments={},
                evidence_reference="Not AP authority",
            )
        codes = set(self.ap_permissions[:4])
        self.assertTrue(
            all(
                not codes.intersection(values)
                for role in ("tenant_owner", "tenant_admin")
                for values in (DEFAULT_ROLE_PERMISSIONS[role],)
            )
        )

    def test_withdrawal_prevents_new_consumption_preserves_existing_target_and_pin(
        self,
    ):
        enrollment = self.enrollment()
        draft = PayrollAPDraft.objects.get(pk=self.prepare().result["drafts"][0])
        target = self.accept(draft)
        api.change_enrollment(
            organization=self.organization,
            actor=self.actor,
            enrollment=enrollment,
            kind="withdraw",
            effective_at=self.clock + timedelta(seconds=1),
            reason="Prospective withdrawal",
        )
        self.clock += timedelta(seconds=2)
        self.assertEqual(self.accept(draft).pk, target.pk)
        self.assertEqual(self.prepare().result["drafts"], [str(draft.pk)])
        self.assertEqual(self.trace()["rows"][0]["enrollment"], str(enrollment.pk))
        self.assertEqual(
            Obligation.objects.get(pk=target.pk).original_amount, Decimal(900)
        )

    def test_withdrawal_preserves_already_consumed_draft_for_ap_acceptance(self):
        enrollment = self.enrollment()
        draft = PayrollAPDraft.objects.get(pk=self.prepare().result["drafts"][0])
        api.change_enrollment(
            organization=self.organization,
            actor=self.actor,
            enrollment=enrollment,
            kind="withdraw",
            effective_at=self.clock + timedelta(seconds=1),
            reason="Stop new AP consumption",
        )
        self.clock += timedelta(seconds=2)
        target = self.accept(draft)
        self.assertEqual(target.source_uuid, draft.pk)
        self.assertEqual(draft.enrollment_id, enrollment.pk)
        self.assertEqual(Obligation.objects.count(), 1)

    def test_withdrawal_blocks_first_consumption_without_prior_draft(self):
        enrollment = self.enrollment()
        api.change_enrollment(
            organization=self.organization,
            actor=self.actor,
            enrollment=enrollment,
            kind="withdraw",
            effective_at=self.clock + timedelta(seconds=1),
            reason="Stop prospective source consumption",
        )
        self.clock += timedelta(seconds=2)
        with self.assertRaises(ValidationError):
            self.prepare()
        self.assertFalse(PayrollAPDraft.objects.exists())
        self.assertFalse(Obligation.objects.exists())

    def test_enrollment_version_is_prospective_and_immutable(self):
        first = self.enrollment()
        draft = PayrollAPDraft.objects.get(pk=self.prepare().result["drafts"][0])
        target = self.accept(draft)
        second = self.enrollment(activate=False)
        with self.assertRaises(ValidationError):
            api.change_enrollment(
                organization=self.organization,
                actor=self.actor,
                enrollment=second,
                kind="activate",
                effective_at=timezone.now() - timedelta(seconds=1),
                reason="Retroactive",
            )
        api.change_enrollment(
            organization=self.organization,
            actor=self.actor,
            enrollment=second,
            kind="activate",
            effective_at=self.clock + timedelta(seconds=1),
            reason="Future version",
        )
        self.clock += timedelta(seconds=2)
        self.assertEqual(self.accept(draft).pk, target.pk)
        self.assertEqual(
            PayrollAPDraft.objects.get(pk=draft.pk).enrollment_id, first.pk
        )
        with self.assertRaises(ValidationError):
            first.save()
        with self.assertRaises(ValidationError):
            PayrollAPEnrollment.objects.filter(pk=first.pk).update(version=88)

    def test_mapping_rejects_cross_tenant_payee_unknown_category_and_missing_terms(
        self,
    ):
        other = create_organization_with_owner(
            owner=self.owner, name="Other synthetic tenant", slug="other043"
        )
        party = BusinessParty.objects.create(
            organization=other,
            party_kind="individual",
            display_name="Other",
            created_by=self.owner,
            updated_by=self.owner,
        )
        terms = {
            str(self.proposal.lines.get().pk): {
                "party_id": str(party.pk),
                "recognized_on": self.day.isoformat(),
                "due_date": self.day.isoformat(),
                "grouping_reference": "explicit",
            }
        }
        for category in ("employee_payable", "every_payroll_component"):
            with self.assertRaises(ValidationError):
                api.prepare_enrollment(
                    organization=self.organization,
                    actor=self.actor,
                    category=category,
                    assignments=terms,
                    evidence_reference="Synthetic",
                )
        with self.assertRaises(ValidationError):
            api.prepare_enrollment(
                organization=self.organization,
                actor=self.actor,
                category="employee_payable",
                assignments={str(self.proposal.lines.get().pk): {}},
                evidence_reference="Missing terms",
            )

    def test_target_failure_rolls_back_drafts_and_preserves_source_and_retry_audit(
        self,
    ):
        self.enrollment()
        native = self.run.calculation_digest
        with (
            patch.object(
                api,
                "_audit",
                side_effect=lambda org, actor, action, identity, metadata: (
                    (_ for _ in ()).throw(DatabaseError("Synthetic target failure"))
                    if action == AuditAction.PAYROLL_AP_OPERATION
                    else None
                ),
            ),
            self.assertRaises(DatabaseError),
        ):
            self.prepare()
        self.assertFalse(PayrollAPDraft.objects.exists())
        self.assertFalse(PayrollAPOperation.objects.exists())
        self.run.refresh_from_db()
        self.assertEqual(self.run.calculation_digest, native)
        self.assertEqual(self.run.status, "finalized")
        self.assertEqual(len(self.prepare().result["drafts"]), 1)

    def test_atomic_correction_retains_original_reversal_replacement_and_draft_boundary(
        self,
    ):
        self.enrollment()
        original = PayrollAPDraft.objects.get(pk=self.prepare().result["drafts"][0])
        target = self.accept(original)
        reverse, replacement = self.correction_sources()
        self.enrollment(replacement)
        operation = self.prepare(
            replacement, key="correct", reversal=reverse, effective_date=self.day
        )
        self.assertEqual(
            self.prepare(
                replacement, key="correct", reversal=reverse, effective_date=self.day
            ).pk,
            operation.pk,
        )
        fresh = PayrollAPDraft.objects.get(pk=operation.result["drafts"][0])
        self.assertEqual(fresh.predecessor_id, original.pk)
        self.assertEqual(fresh.amount, Decimal(1000))
        self.assertEqual(Obligation.objects.count(), 1)
        self.assertEqual(
            Obligation.objects.get(pk=target.pk).outstanding_amount, Decimal(0)
        )
        self.assertEqual(
            _source_reversed_amount_as_of(target, self.day - timedelta(days=1)),
            Decimal(0),
        )
        self.assertEqual(_source_reversed_amount_as_of(target, self.day), Decimal(900))
        with self.assertRaises(ValidationError):
            _require_unreversed_source(target)
        with self.assertRaises(ValidationError):
            self.accept(original)
        self.accept(fresh)
        self.assertEqual(Obligation.objects.count(), 2)
        self.assertEqual(self.trace()["rows"][0]["replacements"], [str(fresh.pk)])
        self.trace(replacement)
        self.assertFalse(JournalEntry.objects.exists())

    def test_no_longer_enrolled_replacement_does_not_create_payable(self):
        enrollment = self.enrollment()
        self.accept(PayrollAPDraft.objects.get(pk=self.prepare().result["drafts"][0]))
        reverse, replacement = self.correction_sources()
        api.change_enrollment(
            organization=self.organization,
            actor=self.actor,
            enrollment=enrollment,
            kind="withdraw",
            effective_at=self.clock + timedelta(seconds=1),
            reason="Withdraw category",
        )
        self.clock += timedelta(seconds=2)
        result = self.prepare(
            replacement, key="no-replacement", reversal=reverse, effective_date=self.day
        )
        self.assertEqual(result.result["drafts"], [])
        self.assertEqual(len(result.result["reversals"]), 1)
        self.assertEqual(Obligation.objects.count(), 1)

    def test_failure_after_reversal_rolls_back_entire_correction_then_retry(self):
        self.enrollment()
        self.accept(PayrollAPDraft.objects.get(pk=self.prepare().result["drafts"][0]))
        reverse, replacement = self.correction_sources()
        self.enrollment(replacement)
        with (
            patch.object(
                api,
                "_drafts",
                side_effect=DatabaseError("Synthetic replacement failure"),
            ),
            self.assertRaises(DatabaseError),
        ):
            self.prepare(
                replacement,
                key="rollback",
                reversal=reverse,
                effective_date=self.day,
            )
        self.assertFalse(PayrollAPReversal.objects.exists())
        self.assertEqual(Obligation.objects.get().outstanding_amount, Decimal(900))
        self.assertEqual(
            len(
                self.prepare(
                    replacement,
                    key="rollback",
                    reversal=reverse,
                    effective_date=self.day,
                ).result["drafts"]
            ),
            1,
        )

    def test_consumed_target_fails_closed_without_any_partial_reversal(self):
        self.enrollment()
        self.accept(PayrollAPDraft.objects.get(pk=self.prepare().result["drafts"][0]))
        reverse, replacement = self.correction_sources()
        self.enrollment(replacement)
        with patch.object(api, "_active_settlement_amount", return_value=Decimal(1)):  # noqa: SIM117
            with self.assertRaises(ValidationError):
                self.prepare(
                    replacement, key="held", reversal=reverse, effective_date=self.day
                )
        self.assertFalse(PayrollAPReversal.objects.exists())
        self.assertEqual(Obligation.objects.count(), 1)
        self.assertEqual(
            len(
                self.prepare(
                    replacement, key="held", reversal=reverse, effective_date=self.day
                ).result["drafts"]
            ),
            1,
        )

    def test_reconciliation_and_retry_detect_source_and_target_drift(self):
        self.enrollment()
        draft = PayrollAPDraft.objects.get(pk=self.prepare().result["drafts"][0])
        target = self.accept(draft)
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE subledgers_obligation SET original_amount=1 WHERE id=%s",
                [target.pk],
            )
        with self.assertRaises(ValidationError):
            self.trace()
        with self.assertRaises(ValidationError):
            self.prepare()
        self.assertEqual(Obligation.objects.count(), 1)

    def test_reversal_only_creates_no_negative_or_replacement_payable(self):
        self.enrollment()
        self.accept(PayrollAPDraft.objects.get(pk=self.prepare().result["drafts"][0]))
        reverse, _ = self.correction_sources(replace=False)
        result = self.prepare(
            reverse, key="reverse-only", reversal=reverse, effective_date=self.day
        )
        self.assertEqual(result.result["drafts"], [])
        self.assertEqual(
            self.prepare(
                reverse, key="reverse-only", reversal=reverse, effective_date=self.day
            ).pk,
            result.pk,
        )
        self.assertEqual(Obligation.objects.get().outstanding_amount, Decimal(0))
        self.assertEqual(PayrollAPReversal.objects.count(), 1)
        self.trace()

    def test_real_recognition_link_and_allocation_facts_hold_target_until_unwound(self):
        from apps.accounting.models import FiscalPeriod, FiscalYear

        from .models import SettlementAllocation, SettlementReversal

        self.enrollment()
        target = self.accept(
            PayrollAPDraft.objects.get(pk=self.prepare().result["drafts"][0])
        )
        reverse, replacement = self.correction_sources()
        self.enrollment(replacement)
        year = FiscalYear.objects.create(
            organization=self.organization,
            code="CONSUME",
            name="Synthetic",
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 12, 31),
            created_by=self.owner,
        )
        period = FiscalPeriod.objects.create(
            organization=self.organization,
            fiscal_year=year,
            number=1,
            name="Synthetic",
            starts_on=year.starts_on,
            ends_on=year.ends_on,
        )
        journal = JournalEntry.objects.create(
            organization=self.organization,
            period=period,
            kind="manual",
            document_date=self.day,
            accounting_date=self.day,
            description="Synthetic independent recognition link",
            source_key="independent043",
            prepared_by=self.ap_membership,
        )
        Obligation.objects.filter(pk=target.pk).update(recognition_journal=journal)
        with self.assertRaises(ValidationError):
            self.prepare(
                replacement, key="real-held", reversal=reverse, effective_date=self.day
            )
        self.assertFalse(PayrollAPReversal.objects.exists())
        # Synthetic owning-domain fact setup/unwind only, no posting engine claim.
        Obligation.objects.filter(pk=target.pk).update(recognition_journal=None)
        movement = TreasuryMovement.objects.create(
            organization=self.organization,
            kind="disbursement",
            movement_date=self.day,
            amount=10,
            description="Synthetic retained allocation fixture",
            idempotency_key="allocation-fixture",
            payload_hash="synthetic",
            created_by=self.ap_membership,
        )
        allocation = SettlementAllocation.objects.create(
            organization=self.organization,
            obligation=target,
            treasury_movement=movement,
            amount=1,
            effective_date=self.day,
            reason="Synthetic owning-domain allocation fact",
            idempotency_key="allocation043",
            payload_hash="synthetic",
            created_by=self.ap_membership,
        )
        with self.assertRaises(ValidationError):
            self.prepare(
                replacement, key="real-held", reversal=reverse, effective_date=self.day
            )
        SettlementReversal.objects.create(
            organization=self.organization,
            allocation=allocation,
            effective_date=self.day + timedelta(days=1),
            reason="Synthetic independent allocation unwind",
            idempotency_key="unwind043",
            payload_hash="synthetic",
            reversed_by=self.ap_membership,
        )
        with self.assertRaises(ValidationError):
            self.prepare(
                replacement, key="real-held", reversal=reverse, effective_date=self.day
            )
        # Dates must align; a replacement cannot precede the independent unwind.
        self.assertEqual(PayrollAPReversal.objects.count(), 0)
        self.assertEqual(Obligation.objects.count(), 1)

    def test_multi_occurrence_correction_rolls_back_all_reversals_and_replacements(
        self,
    ):
        from apps.workforce.models import Employee

        employee = Employee.objects.create(
            organization=self.organization,
            employee_number="PAY-BATCH",
            first_name="Synthetic",
            last_name="Second",
        )
        run = PayrollRun.objects.create(
            organization=self.organization,
            period=self.period,
            code="BATCH",
            kind="off_cycle",
            status="finalized",
            idempotency_key="batch",
            calculation_digest="batch-v1",
            precision_policy_version=self.run.precision_policy_version,
            rounding_policy_version=self.run.rounding_policy_version,
            monetary_policy_snapshot=self.run.monetary_policy_snapshot,
            currency=self.run.currency,
            created_by=self.owner,
            finalized_by=self.owner,
            finalized_at=timezone.now(),
        )
        for person in (self.employee, employee):
            result = PayrollRunEmployee.objects.create(
                organization=self.organization,
                run=run,
                employee=person,
                status="finalized",
                gross_amount=1000,
                deduction_amount=100,
                employer_amount=200,
                net_amount=900,
            )
            PayrollResultLine.objects.create(
                organization=self.organization,
                run=run,
                run_employee=result,
                component=self.component,
                sequence=10,
                component_kind="earning",
                unrounded_amount=1000,
                amount=1000,
                explanation={"source": "Synthetic batch"},
            )
        self.run = run
        self.proposal = self.source(run, "batch-source")
        self.enrollment()
        for pk in self.prepare().result["drafts"]:
            self.accept(PayrollAPDraft.objects.get(pk=pk))
        reverse, replacement = self.correction_sources()
        self.enrollment(replacement)
        create = api._create
        counter = []

        def fail_second(model, **values):
            if model is PayrollAPDraft:
                counter.append(1)
                if len(counter) == 2:
                    raise DatabaseError("Synthetic second replacement failure")
            return create(model, **values)

        with (
            patch.object(api, "_create", side_effect=fail_second),
            self.assertRaises(DatabaseError),
        ):
            self.prepare(
                replacement,
                key="batch-correction",
                reversal=reverse,
                effective_date=self.day,
            )
        self.assertEqual(PayrollAPReversal.objects.count(), 0)
        self.assertEqual(PayrollAPDraft.objects.count(), 2)
        result = self.prepare(
            replacement,
            key="batch-correction",
            reversal=reverse,
            effective_date=self.day,
        )
        self.assertEqual(len(result.result["reversals"]), 2)
        self.assertEqual(len(result.result["drafts"]), 2)
        self.assertEqual(Obligation.objects.count(), 2)
        self.trace()
        self.trace(replacement)


class PayrollAPConcurrencyTests(PayrollAPFixture, TransactionTestCase):
    def test_concurrent_corrections_commit_one_reversal_and_replacement_set(self):
        self.enrollment()
        original = PayrollAPDraft.objects.get(pk=self.prepare().result["drafts"][0])
        self.accept(original)
        reversal, replacement = self.correction_sources()
        self.enrollment(replacement)
        barrier = Barrier(2)

        def correct():
            close_old_connections()
            try:
                barrier.wait(timeout=20)
                operation = api.prepare_payroll_ap(
                    organization=self.organization,
                    actor=self.actor,
                    proposal=replacement,
                    reversal=reversal,
                    effective_date=self.day,
                    idempotency_key="concurrent-correction",
                    reason="Concurrent correction",
                )
                return str(operation.pk), operation.result
            finally:
                close_old_connections()

        with patch.object(api.timezone, "now", return_value=self.clock):  # noqa: SIM117
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = [
                    future.result(timeout=45)
                    for future in [pool.submit(correct), pool.submit(correct)]
                ]
        self.assertEqual(results[0], results[1])
        self.assertEqual(PayrollAPReversal.objects.count(), 1)
        self.assertEqual(PayrollAPDraft.objects.count(), 2)
        self.assertEqual(Obligation.objects.count(), 1)

    def test_concurrent_source_replay_creates_one_draft_and_one_ap_target(self):
        self.enrollment()
        barrier = Barrier(2)

        def consume():
            close_old_connections()
            try:
                barrier.wait(timeout=20)
                result = api.prepare_payroll_ap(
                    organization=self.organization,
                    actor=self.actor,
                    proposal=self.proposal,
                    idempotency_key="concurrent",
                    reason="Concurrent synthetic request",
                )
                draft = PayrollAPDraft.objects.get(pk=result.result["drafts"][0])
                return str(
                    api.accept_payroll_ap_draft(
                        organization=self.organization,
                        actor=self.actor,
                        draft=draft,
                        idempotency_key="concurrent-accept",
                    ).pk
                )
            finally:
                close_old_connections()

        # Freeze clock once around the threads; per-thread patch contexts would race.
        with patch.object(api.timezone, "now", return_value=self.clock):  # noqa: SIM117
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = [
                    x.result(timeout=45)
                    for x in [pool.submit(consume), pool.submit(consume)]
                ]
        self.assertEqual(results[0], results[1])
        self.assertEqual(PayrollAPDraft.objects.count(), 1)
        self.assertEqual(Obligation.objects.count(), 1)
