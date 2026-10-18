"""Governed write-offs against real approved supplier/AP source contracts."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connections
from django.test import TestCase, TransactionTestCase

from apps.accounting.models import Account, FiscalPeriod, JournalLine
from apps.accounting.recognition_models import SourceRecognitionDraft
from apps.accounting.recognition_services import (
    approve_recognition_mapping,
    prepare_recognition_mapping,
    prepare_source_recognition,
    reconcile_source_recognition,
)
from apps.accounting.services import create_fiscal_period, create_fiscal_year
from apps.accounting.test_cep042_regression import explicit_fixture_authority
from apps.audit.models import AuditAction, AuditEvent
from apps.organizations.models import (
    BusinessPermission,
    MembershipScopeGrant,
    Organization,
    OrganizationRole,
    TenantPolicySelection,
)
from apps.organizations.models import (
    BusinessPermissionCode as P,
)
from apps.organizations.policy_specs import SUBLEDGER_WRITEOFF_SELF_APPROVAL_POLICY_CODE
from apps.treasury.models import TreasuryMovement

from . import tests as foundation
from .models import WriteOffCorrection, WriteOffDecision, WriteOffReversal
from .services import _amounts_as_of, propose_write_off
from .test_cep033_invoice_handoff import InvoiceAPFixture
from .writeoffs import correct_write_off, decide_write_off, requester_writeoff_status


class CEP044Fixture(InvoiceAPFixture):
    _activate_policy = foundation.SubledgerFoundationTests._activate_policy

    def setUp(self):
        super().setUp()
        for user in (self.owner, self.member, self.approver):
            membership = self.organization.memberships.get(user=user)
            explicit_fixture_authority(membership, membership.role_definition)
        self.target = self.handoff()
        self.day = self.target.recognized_on
        self._activate_policy(
            SUBLEDGER_WRITEOFF_SELF_APPROVAL_POLICY_CODE,
            {"allow_self_approval": getattr(self, "allow_self_approval", False)},
        )
        self.counterpart = Account.objects.create(
            organization=self.organization,
            code="CEP044",
            name="Explicit counterpart",
            account_type="expense",
            is_posting=True,
            created_by=self.owner,
        )
        year = create_fiscal_year(
            organization=self.organization,
            actor=self.owner,
            code="CEP044",
            name="Year",
            starts_on=date(self.day.year, 1, 1),
            ends_on=date(self.day.year, 12, 31),
            calendar_version=1,
        )
        self.period = create_fiscal_period(
            organization=self.organization,
            actor=self.owner,
            fiscal_year=year,
            number=1,
            name="Period",
            starts_on=year.starts_on,
            ends_on=year.ends_on,
        )
        self.recognition_mapping = self.accounting_mapping(
            "Procurement Supplier Invoice Match",
            "payable_recognized",
            self.counterpart,
            self.mapping.control_account,
        )
        self.writeoff_mapping = self.accounting_mapping(
            "AP/AR Write-off",
            "payable_written_off",
            self.mapping.control_account,
            self.counterpart,
        )

    def accounting_mapping(self, family, event, debit, credit):
        mapping = prepare_recognition_mapping(
            organization=self.organization,
            actor=self.owner,
            source_family=family,
            source_event=event,
            effective_from=date(self.day.year, 1, 1),
            account_assignments={
                "amount": {"debit": str(debit.pk), "credit": str(credit.pk)}
            },
            evidence_reference="Explicit synthetic CEP044 mapping; no production value",
        )
        if family != getattr(self, "unapproved_family", None):
            approve_recognition_mapping(
                organization=self.organization,
                actor=self.approver,
                mapping=mapping,
                reason="Independent test mapping approval",
            )
        return mapping

    def proposal(self, key="original", amount="10", day=None, corrects=None):
        return propose_write_off(
            organization=self.organization,
            actor=self.owner,
            obligation=self.target,
            amount=Decimal(amount),
            effective_date=day or self.day,
            reason="Manual request",
            idempotency_key=key,
            corrects=corrects,
        )

    def approve(self, proposal=None, actor=None):
        return decide_write_off(
            organization=self.organization,
            actor=actor or self.approver,
            proposal=proposal or self.proposal(),
            approve=True,
            reason="Explicit approval",
        )

    def correct(self, original, replacement=None, **overrides):
        values = {
            "organization": self.organization,
            "actor": self.approver,
            "original": original,
            "replacement": replacement,
            "effective_date": self.day + timedelta(days=1),
            "reason": "Governed correction",
            "idempotency_key": "correction",
        }
        values.update(overrides)
        return correct_write_off(**values)

    def mark_consumed(self, effect):
        """Synthetic already-posted target; never activates a posting producer."""
        from django.utils import timezone

        from apps.accounting.models import JournalEntry
        from apps.organizations.models import PlatformPolicyVersion
        from apps.organizations.policy_specs import (
            ACCOUNTING_MONEY_PRECISION_POLICY_CODE,
            ACCOUNTING_ROUNDING_POLICY_CODE,
            initial_accounting_policy_parameters,
        )

        versions = []
        for code in (
            ACCOUNTING_MONEY_PRECISION_POLICY_CODE,
            ACCOUNTING_ROUNDING_POLICY_CODE,
        ):
            version = PlatformPolicyVersion.objects.filter(
                policy__code=code, status="published"
            ).first()
            if version is None:
                self._activate_policy(code, initial_accounting_policy_parameters(code))
                version = PlatformPolicyVersion.objects.get(
                    policy__code=code, status="published"
                )
            versions.append(version)
        JournalEntry.objects.filter(pk=effect.journal_id).update(
            status="posted",
            number=44001,
            posted_by=self.owner_membership,
            posted_at=timezone.now(),
            precision_policy_version=versions[0],
            rounding_policy_version=versions[1],
        )


class WriteOffGovernanceTests(CEP044Fixture, TestCase):
    def test_rejection_retains_request_and_has_no_financial_effect(self):
        proposal = self.proposal()
        decision = decide_write_off(
            organization=self.organization,
            actor=self.approver,
            proposal=proposal,
            approve=False,
            reason="Rejected",
        )
        self.assertEqual(decision.decision, "rejected")
        self.assertFalse(SourceRecognitionDraft.objects.exists())
        with self.assertRaises(ValidationError):
            self.approve(proposal)
        self.assertEqual(
            _amounts_as_of(self.target, self.day), (Decimal(0), Decimal(0))
        )

    def test_approval_replay_and_requester_minimum_status(self):
        proposal = self.proposal()
        self.assertEqual(
            requester_writeoff_status(
                organization=self.organization,
                actor=self.owner,
                proposal_id=proposal.pk,
            )["status"],
            "proposed",
        )
        decision = self.approve(proposal)
        self.assertEqual(self.approve(proposal).pk, decision.pk)
        with self.assertRaises(ValidationError):
            decide_write_off(
                organization=self.organization,
                actor=self.approver,
                proposal=proposal,
                approve=False,
                reason="Conflict",
            )
        self.assertEqual(WriteOffDecision.objects.count(), 1)
        self.assertEqual(SourceRecognitionDraft.objects.count(), 1)
        self.assertEqual(
            _amounts_as_of(self.target, self.day), (Decimal(0), Decimal(10))
        )
        status = requester_writeoff_status(
            organization=self.organization,
            actor=self.owner,
            proposal_id=proposal.pk,
        )
        self.assertEqual(
            set(status), {"proposal_id", "status", "amount", "effective_date"}
        )
        self.assertEqual(status["status"], "approved")
        with self.assertRaises(PermissionDenied):
            requester_writeoff_status(
                organization=self.organization,
                actor=self.member,
                proposal_id=proposal.pk,
            )

    def test_atomic_replacement_preserves_cutoffs_and_exact_accounting_inverse(self):
        original = self.approve()
        replacement = self.proposal(
            "replacement", "7", self.day + timedelta(days=1), original
        )
        before_cash = list(TreasuryMovement.objects.values())
        result = self.correct(original, replacement)
        self.assertEqual(self.correct(original, replacement).pk, result.pk)
        self.assertEqual(result.replacement.proposal.amount, Decimal(7))
        self.assertEqual(
            _amounts_as_of(self.target, self.day), (Decimal(0), Decimal(10))
        )
        self.assertEqual(
            _amounts_as_of(self.target, result.effective_date), (Decimal(0), Decimal(7))
        )
        self.assertEqual(before_cash, list(TreasuryMovement.objects.values()))
        self.assertEqual(WriteOffCorrection.objects.count(), 1)
        self.assertEqual(SourceRecognitionDraft.objects.count(), 3)
        effect = SourceRecognitionDraft.objects.get(
            pk=result.accounting_evidence["original"]
        )
        inverse = SourceRecognitionDraft.objects.get(
            pk=result.accounting_evidence["reversal"]
        )
        rows = lambda journal: list(
            JournalLine.objects.filter(journal=journal)
            .order_by("account_id")
            .values_list("account_id", "debit", "credit")
        )
        self.assertEqual(
            [(a, c, d) for a, d, c in rows(effect.journal)], rows(inverse.journal)
        )
        self.assertEqual(inverse.journal.accounting_date, result.effective_date)
        with self.assertRaises(ValidationError):
            self.correct(original, replacement, reason="Conflicting payload")
        with self.assertRaises(ValidationError):
            self.correct(original, idempotency_key="second economic correction")
        for item in (original, original.proposal, result.reversal, result):
            with self.assertRaises(ValidationError):
                item.save()
            with self.assertRaises(ValidationError):
                type(item).objects.filter(pk=item.pk).update(reason="overwrite")
        if os.getenv("BONIRA_CEP044_TRACE"):
            Path(os.environ["BONIRA_CEP044_TRACE"]).write_text(
                json.dumps(
                    {
                        "environment": "Disposable synthetic PostgreSQL test only",
                        "source_obligation": str(self.target.pk),
                        "source_uuid": str(self.target.source_uuid),
                        "source_version": self.target.source_version,
                        "source_hash": self.target.source_hash,
                        "control_account_id": str(self.target.control_account_id),
                        "control_mapping_id": str(
                            self.target.control_account_mapping_id
                        ),
                        "original_decision": str(original.pk),
                        "original_amount": str(original.proposal.amount),
                        "original_date": original.proposal.effective_date.isoformat(),
                        "correction": str(result.pk),
                        "correction_actor": str(result.actor_id),
                        "correction_created_at": result.created_at.isoformat(),
                        "correction_date": result.effective_date.isoformat(),
                        "reversal": str(result.reversal_id),
                        "replacement": str(result.replacement_id),
                        "replacement_amount": str(result.replacement.proposal.amount),
                        "accounting": result.accounting_evidence,
                        "policy": result.policy_evidence,
                        "cutoffs_before_after": ["10.000000", "7.000000"],
                        "exact_inverse_and_replay": "PASS",
                        "immutable_history_and_treasury_preserved": "PASS",
                        "target_level": "L2 draft only",
                        "production": False,
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

    def test_full_cancellation_has_no_replacement(self):
        original = self.approve()
        result = self.correct(original)
        self.assertIsNone(result.replacement_id)
        self.assertEqual(
            _amounts_as_of(self.target, self.day), (Decimal(0), Decimal(10))
        )
        self.assertEqual(
            _amounts_as_of(self.target, result.effective_date), (Decimal(0), Decimal(0))
        )

    def test_policy_missing_and_self_approval_fail_closed(self):
        proposal = self.proposal()
        with self.assertRaises(PermissionDenied):
            self.approve(proposal, actor=self.owner)
        TenantPolicySelection.objects.filter(
            policy__code=SUBLEDGER_WRITEOFF_SELF_APPROVAL_POLICY_CODE
        ).delete()
        with self.assertRaises(ValidationError):
            self.approve(proposal)
        self.assertFalse(WriteOffDecision.objects.exists())
        self.assertFalse(SourceRecognitionDraft.objects.exists())

    def test_late_failure_rolls_back_entire_set_and_success_audit(self):
        original = self.approve()
        replacement = self.proposal(
            "replacement", "7", self.day + timedelta(days=1), original
        )
        original_counts = (
            WriteOffDecision.objects.count(),
            SourceRecognitionDraft.objects.count(),
        )
        with (
            patch(
                "apps.subledgers.writeoffs._capacity",
                side_effect=ValidationError("injected failure"),
            ),
            self.assertRaises(ValidationError),
        ):
            self.correct(original, replacement)
        self.assertFalse(WriteOffReversal.objects.exists())
        self.assertFalse(WriteOffCorrection.objects.exists())
        self.assertEqual(
            original_counts,
            (WriteOffDecision.objects.count(), SourceRecognitionDraft.objects.count()),
        )
        self.assertFalse(
            AuditEvent.objects.filter(
                action=AuditAction.SUBLEDGER_WRITEOFF_CORRECTED
            ).exists()
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.SUBLEDGER_WRITEOFF_FAILED
            ).exists()
        )
        self.correct(original, replacement)

    def test_closed_period_refuses_without_date_substitution(self):
        original = self.approve()
        FiscalPeriod.objects.filter(pk=self.period.pk).update(status="closed")
        with self.assertRaises(ValidationError):
            self.correct(original)
        self.assertFalse(WriteOffReversal.objects.exists())
        self.assertEqual(SourceRecognitionDraft.objects.count(), 1)

    def test_native_ap_control_reconciliation_and_exact_replay(self):
        effect = prepare_source_recognition(
            organization=self.organization,
            actor=self.approver,
            source_kind="ap_invoice",
            source_id=self.match.pk,
        )
        self.assertEqual(
            effect.pk,
            prepare_source_recognition(
                organization=self.organization,
                actor=self.approver,
                source_kind="ap_invoice",
                source_id=self.match.pk,
            ).pk,
        )
        reconciliation = reconcile_source_recognition(
            organization=self.organization,
            actor=self.approver,
            effect=effect,
        )
        self.assertEqual(reconciliation["status"], "matched")

    def test_failed_target_preserves_source_and_retry_revalidates(self):
        from apps.accounting.recognition_services import attempt_source_recognition

        # A source with an unsupported kind cannot be routed through AP generically.
        with self.assertRaises(ValidationError):
            prepare_source_recognition(
                organization=self.organization,
                actor=self.approver,
                source_kind="subledgers",
                source_id=self.target.pk,
            )
        before = self.target.source_hash
        with patch(
            "apps.accounting.recognition_services._mapped_rows",
            side_effect=ValidationError("injected target failure"),
        ):
            self.assertIsNone(
                attempt_source_recognition(
                    organization=self.organization,
                    actor=self.approver,
                    source_kind="ap_invoice",
                    source_id=self.match.pk,
                )
            )
        self.target.refresh_from_db()
        self.assertEqual(before, self.target.source_hash)
        self.assertFalse(SourceRecognitionDraft.objects.exists())
        effect = prepare_source_recognition(
            organization=self.organization,
            actor=self.approver,
            source_kind="ap_invoice",
            source_id=self.match.pk,
        )
        self.assertEqual(effect.source_uuid, self.match.pk)

    def test_denied_permissions_object_scope_and_tenant_state(self):
        proposal = self.proposal()
        membership = self.organization.memberships.get(user=self.approver)
        role = membership.role_definition
        permission = BusinessPermission.objects.get(code=P.SUBLEDGERS_WRITEOFFS_APPROVE)
        role.permissions.remove(permission)
        with self.assertRaises(PermissionDenied):
            self.approve(proposal)
        role.permissions.add(permission)
        scope = MembershipScopeGrant.objects.get(
            membership=membership, revoked_at__isnull=True
        )
        from django.utils import timezone

        MembershipScopeGrant.objects.filter(pk=scope.pk).update(
            revoked_at=timezone.now()
        )
        with self.assertRaises(PermissionDenied):
            self.approve(proposal)
        MembershipScopeGrant.objects.filter(pk=scope.pk).update(revoked_at=None)
        for status in ("suspended", "cancelled"):
            Organization.objects.filter(pk=self.organization.pk).update(status=status)
            with self.assertRaises(PermissionDenied):
                self.approve(proposal)
        Organization.objects.filter(pk=self.organization.pk).update(status="active")
        self.approve(proposal)

    def test_foreign_tenant_sources_are_denied_without_targets(self):
        from apps.accounts.models import User
        from apps.organizations.services import create_organization_with_owner

        outsider = User.objects.create_user(username="cep044-outsider")
        other = create_organization_with_owner(
            owner=outsider, name="Other", slug="other044"
        )
        role = OrganizationRole.objects.create(
            organization=other, code="foreign044", name="Explicit foreign authority"
        )
        role.permissions.set(BusinessPermission.objects.filter(is_active=True))
        explicit_fixture_authority(other.memberships.get(user=outsider), role)
        proposal = self.proposal()
        for operation in (
            lambda: decide_write_off(
                organization=other,
                actor=outsider,
                proposal=proposal,
                approve=True,
                reason="forged",
            ),
            lambda: prepare_source_recognition(
                organization=other,
                actor=outsider,
                source_kind="ap_invoice",
                source_id=self.match.pk,
            ),
            lambda: requester_writeoff_status(
                organization=other, actor=outsider, proposal_id=proposal.pk
            ),
        ):
            with self.assertRaises(PermissionDenied):
                operation()
        self.assertFalse(WriteOffDecision.objects.exists())
        self.assertFalse(SourceRecognitionDraft.objects.exists())

    def test_consumed_target_and_mismatched_date_fail_closed(self):
        original = self.approve()
        replacement = self.proposal("wrong-date", "7", self.day, original)
        with self.assertRaises(ValidationError):
            self.correct(original, replacement)
        effect = SourceRecognitionDraft.objects.get(source_uuid=original.pk)
        self.mark_consumed(effect)
        with self.assertRaises(ValidationError):
            self.correct(original)
        self.assertFalse(WriteOffReversal.objects.exists())
        self.assertFalse(WriteOffCorrection.objects.exists())

    def test_capacity_date_boundaries_and_future_correction(self):
        original = self.approve(self.proposal(amount=str(self.target.original_amount)))
        replacement = self.proposal(
            "replacement", "7", self.day + timedelta(days=1), original
        )
        self.correct(original, replacement)
        from .writeoffs import max_writeoff_exposure

        self.assertEqual(
            max_writeoff_exposure(self.target, on_or_after=self.day),
            self.target.original_amount,
        )
        self.assertEqual(
            max_writeoff_exposure(
                self.target, on_or_after=self.day + timedelta(days=1)
            ),
            Decimal(7),
        )
        with self.assertRaises(ValidationError):
            self.approve(self.proposal("overlapping", "1", self.day))
        with self.assertRaises(ValidationError):
            self.correct(original, effective_date=self.day - timedelta(days=1))

    def test_native_ap_reversal_and_replacement_accounting_chain(self):
        original = prepare_source_recognition(
            organization=self.organization,
            actor=self.approver,
            source_kind="ap_invoice",
            source_id=self.match.pk,
        )
        corrected_match = self.correction_source()
        target = self.handoff(
            match=corrected_match,
            key="corrected-ap",
            corrects=self.target,
            effective_date=self.day,
            reason="Explicit AP correction",
        )
        reversal = prepare_source_recognition(
            organization=self.organization,
            actor=self.approver,
            source_kind="ap_invoice",
            source_id=self.match.pk,
        )
        replacement = prepare_source_recognition(
            organization=self.organization,
            actor=self.approver,
            source_kind="ap_invoice",
            source_id=corrected_match.pk,
        )
        self.assertTrue(reversal.is_reversal)
        self.assertEqual(reversal.predecessor_id, original.pk)
        self.assertEqual(replacement.predecessor_id, original.pk)
        self.assertEqual(target.source_uuid, corrected_match.pk)
        for effect in (original, reversal, replacement):
            self.assertEqual(
                reconcile_source_recognition(
                    organization=self.organization, actor=self.approver, effect=effect
                )["status"],
                "matched",
            )

    def test_consumed_native_ap_target_blocks_source_reversal(self):
        effect = prepare_source_recognition(
            organization=self.organization,
            actor=self.approver,
            source_kind="ap_invoice",
            source_id=self.match.pk,
        )
        self.mark_consumed(effect)
        with self.assertRaises(ValidationError):
            self.reverse(self.target)
        self.assertIsNone(self.target.source_reversal_evidence)

    def test_correction_chain_requires_explicit_reverse_authority_and_pins_each_predecessor(
        self,
    ):
        original = self.approve()
        permission = BusinessPermission.objects.get(code=P.SUBLEDGERS_WRITEOFFS_REVERSE)
        role = self.organization.memberships.get(user=self.approver).role_definition
        role.permissions.remove(permission)
        with self.assertRaises(PermissionDenied):
            self.correct(original)
        self.assertFalse(WriteOffReversal.objects.exists())
        role.permissions.add(permission)
        replacement = self.proposal(
            "replacement", "7", self.day + timedelta(days=1), original
        )
        first = self.correct(original, replacement)
        next_date = self.day + timedelta(days=2)
        next_proposal = self.proposal(
            "next replacement", "4", next_date, first.replacement
        )
        second = self.correct(
            first.replacement,
            next_proposal,
            effective_date=next_date,
            idempotency_key="second correction",
        )
        self.assertEqual(second.original_id, first.replacement_id)
        for cutoff, amount in (
            (self.day, 10),
            (first.effective_date, 7),
            (next_date, 4),
        ):
            self.assertEqual(_amounts_as_of(self.target, cutoff)[1], Decimal(amount))


class WriteOffSelfApprovalTests(CEP044Fixture, TestCase):
    allow_self_approval = True

    def test_explicit_effective_policy_allows_self_approval_without_new_classification(
        self,
    ):
        original = self.approve(actor=self.owner)
        result = self.correct(original, actor=self.owner)
        self.assertTrue(original.authority_evidence["policy"]["self_approval_used"])
        self.assertTrue(result.policy_evidence["reversal"]["self_approval_used"])


class WriteOffConfigurationTests(CEP044Fixture, TestCase):
    unapproved_family = "AP/AR Write-off"

    def test_unapproved_mapping_fails_then_explicit_approval_allows_retry(self):
        proposal = self.proposal()
        with self.assertRaises(ValidationError):
            self.approve(proposal)
        self.assertFalse(WriteOffDecision.objects.exists())
        self.assertFalse(SourceRecognitionDraft.objects.exists())
        approve_recognition_mapping(
            organization=self.organization,
            actor=self.approver,
            mapping=self.writeoff_mapping,
            reason="Explicit mapping acceptance for retry",
        )
        self.approve(proposal)


class WriteOffConcurrencyTests(CEP044Fixture, TransactionTestCase):
    def test_racing_correction_has_one_atomic_result(self):
        original = self.approve()
        replacement = self.proposal(
            "replacement", "7", self.day + timedelta(days=1), original
        )
        barrier = Barrier(2)

        def worker():
            close_old_connections()
            try:
                barrier.wait(timeout=15)
                return self.correct(original, replacement).pk
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            identities = list(pool.map(lambda _: worker(), range(2)))
        self.assertEqual(identities[0], identities[1])
        self.assertEqual(WriteOffCorrection.objects.count(), 1)
        self.assertEqual(WriteOffReversal.objects.count(), 1)
        self.assertEqual(WriteOffDecision.objects.count(), 2)
        self.assertEqual(SourceRecognitionDraft.objects.count(), 3)
        first = WriteOffCorrection.objects.get(original=original)
        date2 = self.day + timedelta(days=2)
        candidates = [
            self.proposal(f"race-{n}", str(n), date2, first.replacement) for n in (4, 5)
        ]
        barrier2 = Barrier(2)

        def conflicting_worker(index):
            close_old_connections()
            try:
                barrier2.wait(timeout=15)
                self.correct(
                    first.replacement,
                    candidates[index],
                    effective_date=date2,
                    idempotency_key=f"race-correction-{index}",
                )
                return True
            except ValidationError:
                return False
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            winners = list(pool.map(conflicting_worker, range(2)))
        self.assertEqual(sum(winners), 1)
        self.assertEqual(WriteOffCorrection.objects.count(), 2)
        self.assertEqual(WriteOffReversal.objects.count(), 2)
        self.assertEqual(WriteOffDecision.objects.count(), 3)
        self.assertEqual(SourceRecognitionDraft.objects.count(), 5)
