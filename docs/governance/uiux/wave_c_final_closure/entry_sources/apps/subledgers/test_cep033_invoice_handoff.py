"""INT-B01 source, AP target, rollback/retry and preserved correction lineage."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from apps.accounting.models import (
    Account,
    AccountType,
    ControlAccountMappingVersion,
    JournalEntry,
)
from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermission,
    BusinessPermissionCode,
    MembershipRole,
    MembershipScopeGrant,
    MembershipStatus,
    OrganizationRole,
    OrganizationSettings,
)
from apps.procurement.tests import ProcurementFixtureMixin
from apps.subledgers import models as m
from apps.subledgers.services import (
    _canonical_hash,
    allocate_settlement,
    decide_supplier_invoice,
    prepare_supplier_invoice,
    propose_write_off,
    recognize_obligation,
    resolve_pinned_control_account_for_posting,
    reverse_settlement,
    run_aging,
    run_subledger_reconciliation,
    run_supplier_invoice_match,
    submit_supplier_invoice,
)
from apps.subledgers.supplier_invoice_handoffs import (
    INVOICE_MATCH_SOURCE_KIND,
    handoff_supplier_invoice_match,
    reconcile_supplier_invoice_ap,
    reverse_supplier_invoice_obligation,
)
from apps.subledgers.test_p5_s26_s27_match_review import P5S26S27MatchReviewTests
from apps.subledgers.tests import SubledgerFoundationTests


class InvoiceAPFixture(ProcurementFixtureMixin):
    def setUp(self):
        super().setUp()
        OrganizationSettings.objects.get_or_create(
            organization=self.organization,
            defaults={"timezone": "UTC", "currency": "IRR"},
        )
        self.approver = User.objects.create_user(username="cep033-checker")
        self.organization.memberships.create(
            user=self.approver,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        for user in (self.owner, self.member, self.approver):
            membership = self.organization.memberships.get(user=user)
            role = OrganizationRole.objects.create(
                code=f"cep033-{user.pk}", name="Explicit test grants"
            )
            role.permissions.set(BusinessPermission.objects.filter(is_active=True))
            membership.role_definition = role
            membership.save(update_fields=["role_definition"])
            MembershipScopeGrant.objects.create(
                organization=self.organization,
                membership=membership,
                scope_type=AuthorizationScopeType.ORGANIZATION,
                reason="CEP-033 isolated fixture",
            )
        self.membership = self.organization.memberships.get(user=self.owner)
        self.owner_membership = self.membership
        self.match = P5S26S27MatchReviewTests._retained_match(self)
        account = Account.objects.create(
            organization=self.organization,
            code="AP033",
            name="AP control",
            account_type=AccountType.LIABILITY,
            is_posting=True,
            created_by=self.owner,
        )
        self.mapping = ControlAccountMappingVersion.objects.create(
            organization=self.organization,
            source_kind=INVOICE_MATCH_SOURCE_KIND,
            direction=m.ObligationDirection.PAYABLE,
            version=1,
            control_account=account,
            effective_from=date(2026, 1, 1),
            reason="Explicit test Accounting mapping",
            created_by=self.membership,
        )

    def handoff(self, match=None, key="ap033", **kwargs):
        return handoff_supplier_invoice_match(
            organization=self.organization,
            actor=self.owner,
            match=match or self.match,
            idempotency_key=key,
            **kwargs,
        )

    def correction_source(self):
        previous = self.match.invoice_version
        previous.refresh_from_db()
        invoice = prepare_supplier_invoice(
            organization=self.organization,
            actor=self.owner,
            supplier=self.supplier,
            project=self.project,
            invoice_number=previous.invoice.invoice_number,
            invoice_date=previous.invoice_date,
            due_date=previous.due_date,
            lines=[
                {
                    "kind": "goods",
                    "purchase_order_version_line": previous.lines.get().purchase_order_version_line,
                    "quantity": Decimal("4.0000"),
                    "unit_price": Decimal("12.34"),
                }
            ],
            idempotency_key="ap033-source-correction",
            supersedes=previous,
        )
        submit_supplier_invoice(
            organization=self.organization, actor=self.owner, invoice_version=invoice
        )
        decide_supplier_invoice(
            organization=self.organization,
            actor=self.approver,
            invoice_version=invoice,
            approve=True,
            reason="Independent correction approval",
        )
        return run_supplier_invoice_match(
            organization=self.organization,
            actor=self.owner,
            invoice_version=invoice,
            idempotency_key="ap033-corrected-match",
        )

    def reverse(self, target, key="reverse033", **kwargs):
        return reverse_supplier_invoice_obligation(
            organization=self.organization,
            actor=self.owner,
            obligation=target,
            effective_date=target.recognized_on,
            reason="Source reversal",
            idempotency_key=key,
            **kwargs,
        )

    def posted_disbursement(self):
        from apps.accounting.services import (
            create_account,
            create_fiscal_period,
            create_fiscal_year,
        )
        from apps.organizations.policy_specs import (
            ACCOUNTING_INITIAL_POLICY_PARAMETERS,
            ACCOUNTING_MONEY_PRECISION_POLICY_CODE,
            ACCOUNTING_ROUNDING_POLICY_CODE,
            TREASURY_SELF_APPROVAL_POLICY_CODE,
        )
        from apps.treasury.services import (
            approve_and_post_movement,
            create_account_mapping_version,
            create_movement,
            create_treasury_account,
            submit_movement,
            transition_treasury_account,
        )

        for code in (
            ACCOUNTING_MONEY_PRECISION_POLICY_CODE,
            ACCOUNTING_ROUNDING_POLICY_CODE,
        ):
            SubledgerFoundationTests._activate_policy(
                self, code, ACCOUNTING_INITIAL_POLICY_PARAMETERS[code]
            )
        SubledgerFoundationTests._activate_policy(
            self, TREASURY_SELF_APPROVAL_POLICY_CODE, {"allow_self_approval": True}
        )
        year = create_fiscal_year(
            organization=self.organization,
            actor=self.owner,
            code="FY033",
            name="Test year",
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 12, 31),
            calendar_version=1,
        )
        period = create_fiscal_period(
            organization=self.organization,
            actor=self.owner,
            fiscal_year=year,
            number=1,
            name="Test period",
            starts_on=year.starts_on,
            ends_on=year.ends_on,
        )
        cash = create_account(
            organization=self.organization,
            actor=self.owner,
            code="C033",
            name="Cash",
            account_type="asset",
            is_posting=True,
        )
        clearing = create_account(
            organization=self.organization,
            actor=self.owner,
            code="CL033",
            name="Clearing",
            account_type="liability",
            is_posting=True,
        )
        bank = create_treasury_account(
            organization=self.organization,
            actor=self.owner,
            code="BANK033",
            name="Test bank",
            kind="bank",
            sensitive_identifier="IR0000000033",
        )
        create_account_mapping_version(
            organization=self.organization,
            actor=self.owner,
            account=bank,
            cash_ledger_account=cash,
            clearing_ledger_account=clearing,
            effective_from=year.starts_on,
            reason="Test mapping",
        )
        bank = transition_treasury_account(
            organization=self.organization,
            actor=self.owner,
            account=bank,
            to_status="active",
            reason="Test activation",
        )
        movement = create_movement(
            organization=self.organization,
            actor=self.owner,
            kind="disbursement",
            movement_date=timezone.localdate(),
            amount=Decimal(10),
            description="Test cash payment",
            idempotency_key="cash033",
            account=bank,
            project=self.project,
            party=self.supplier,
        )
        movement = submit_movement(
            organization=self.organization,
            actor=self.owner,
            movement=movement,
            reason="Submit",
        )
        return approve_and_post_movement(
            organization=self.organization,
            actor=self.owner,
            movement=movement,
            accounting_preparer=self.organization.memberships.get(user=self.approver),
            period=period,
            reason="Independent Treasury/Accounting operation",
        )


class SupplierInvoiceAPHandoffTests(InvoiceAPFixture, TestCase):
    def test_settlement_writeoff_and_source_reversal_keep_their_own_authorities(self):
        target = self.handoff()
        movement = self.posted_disbursement()
        allocation = allocate_settlement(
            organization=self.organization,
            actor=self.owner,
            obligation=target,
            movement=movement,
            amount=Decimal(1),
            effective_date=target.recognized_on,
            reason="Valid independent cash allocation",
            idempotency_key="allocate033",
        )
        with self.assertRaises(ValidationError):
            self.reverse(target)
        tomorrow = target.recognized_on + timedelta(days=1)
        reverse_settlement(
            organization=self.organization,
            actor=self.owner,
            allocation=allocation,
            effective_date=tomorrow,
            reason="Independent allocation reversal",
            idempotency_key="cash-reverse033",
        )
        with self.assertRaises(ValidationError):
            self.reverse(target)
        reverse_supplier_invoice_obligation(
            organization=self.organization,
            actor=self.owner,
            obligation=target,
            effective_date=tomorrow,
            reason="After independent reversal",
            idempotency_key="source-reverse033",
        )
        with self.assertRaises(ValidationError):
            allocate_settlement(
                organization=self.organization,
                actor=self.owner,
                obligation=target,
                movement=movement,
                amount=Decimal(1),
                effective_date=tomorrow,
                reason="Cannot consume reversed source",
                idempotency_key="allocate-again033",
            )
        with self.assertRaises(ValidationError):
            propose_write_off(
                organization=self.organization,
                actor=self.owner,
                obligation=target,
                amount=Decimal(1),
                effective_date=tomorrow,
                reason="No write-off substitution",
                idempotency_key="writeoff033",
            )
        self.assertFalse(m.WriteOffProposal.objects.exists())
        self.assertEqual(m.SettlementAllocation.objects.count(), 1)
        self.assertIsNone(m.Obligation.objects.get(pk=target.pk).recognition_journal_id)

    def test_reversal_permission_has_no_implicit_system_role_grants(self):
        self.assertFalse(
            OrganizationRole.objects.filter(
                is_system=True,
                permissions__code=BusinessPermissionCode.SUBLEDGERS_SOURCES_REVERSE,
            ).exists()
        )

    def test_exactly_once_explicit_ap_acceptance_preserves_source_and_has_no_gl(self):
        self.assertFalse(m.Obligation.objects.exists())
        source_hash = self.match.source_fingerprint
        journals = JournalEntry.objects.count()
        target = self.handoff()
        self.assertEqual(self.handoff().pk, target.pk)
        self.assertEqual(self.handoff(key="another-key").pk, target.pk)
        self.assertEqual(m.Obligation.objects.count(), 1)
        self.assertEqual(target.original_amount, Decimal("61.700000"))
        self.assertEqual(target.source_uuid, self.match.pk)
        self.assertEqual(target.source_snapshot["invoice_version"], 1)
        self.assertEqual(target.source_snapshot["match_version"], 1)
        self.assertEqual(target.control_account_mapping_id, self.mapping.pk)
        self.assertIsNone(target.recognition_journal_id)
        self.assertEqual(JournalEntry.objects.count(), journals)
        self.match.refresh_from_db()
        self.assertEqual(self.match.source_fingerprint, source_hash)
        self.assertEqual(
            AuditEvent.objects.filter(
                action=AuditAction.SUBLEDGER_OBLIGATION_RECOGNIZED
            ).count(),
            1,
        )

    def test_only_current_approved_unblocked_complete_source_is_accepted(self):
        for status in (m.InvoiceMatchStatus.BLOCKED, m.InvoiceMatchStatus.INCOMPLETE):
            m.SupplierInvoiceMatch.objects.filter(pk=self.match.pk).update(
                status=status
            )
            with self.assertRaises(ValidationError):
                self.handoff()
        m.SupplierInvoiceMatch.objects.filter(pk=self.match.pk).update(status="matched")
        m.SupplierInvoiceVersion.objects.filter(
            pk=self.match.invoice_version_id
        ).update(status="submitted")
        with self.assertRaises(ValidationError):
            self.handoff()
        m.SupplierInvoiceVersion.objects.filter(
            pk=self.match.invoice_version_id
        ).update(status="approved")
        m.SupplierInvoiceMatchLine.objects.filter(match=self.match).update(
            status="blocked"
        )
        with self.assertRaises(ValidationError):
            self.handoff()
        self.assertFalse(m.Obligation.objects.exists())

    def test_rematch_supersedes_source_and_never_falls_back_to_older_match(self):
        latest = run_supplier_invoice_match(
            organization=self.organization,
            actor=self.owner,
            invoice_version=self.match.invoice_version,
            idempotency_key="rematch033",
        )
        with self.assertRaises(ValidationError):
            self.handoff()
        m.SupplierInvoiceMatch.objects.filter(pk=latest.pk).update(status="blocked")
        with self.assertRaises(ValidationError):
            self.handoff(latest)
        self.assertFalse(m.Obligation.objects.exists())

    def test_source_identity_version_fingerprint_and_full_line_evidence_are_required(
        self,
    ):
        with self.assertRaises(ValidationError):
            recognize_obligation(
                organization=self.organization,
                actor=self.owner,
                source_kind=INVOICE_MATCH_SOURCE_KIND,
                source_uuid=self.match.pk,
                source_version=2,
                idempotency_key="wrong-version",
            )
        original = self.match.source_fingerprint
        m.SupplierInvoiceMatch.objects.filter(pk=self.match.pk).update(
            source_fingerprint="0" * 64
        )
        with self.assertRaises(ValidationError):
            self.handoff()
        m.SupplierInvoiceMatch.objects.filter(pk=self.match.pk).update(
            source_fingerprint=original
        )
        m.SupplierInvoiceMatchLine.objects.filter(match=self.match).delete()
        with self.assertRaises(ValidationError):
            self.handoff()
        self.assertFalse(m.Obligation.objects.exists())

    def test_mapping_failure_is_retained_and_retry_revalidates_source(self):
        with (
            patch(
                "apps.accounting.services.resolve_control_account_mapping",
                side_effect=ValidationError("missing policy"),
            ),
            self.assertRaises(ValidationError),
        ):
            self.handoff()
        self.assertFalse(m.Obligation.objects.exists())
        self.assertEqual(
            AuditEvent.objects.filter(
                action=AuditAction.SUPPLIER_INVOICE_AP_FAILED
            ).count(),
            1,
        )
        target = self.handoff()
        m.SupplierInvoiceMatch.objects.filter(pk=self.match.pk).update(status="blocked")
        with self.assertRaises(ValidationError):
            self.handoff()
        self.assertEqual(m.Obligation.objects.get().pk, target.pk)

    def test_tenant_permission_scope_and_reversal_grant_fail_closed(self):
        with self.assertRaises(PermissionDenied):
            handoff_supplier_invoice_match(
                organization=self.other_organization,
                actor=self.outsider,
                match=self.match,
                idempotency_key="outside",
            )
        self.assertFalse(m.Obligation.objects.exists())
        target = self.handoff()
        self.membership.role_definition.permissions.remove(
            BusinessPermission.objects.get(
                code=BusinessPermissionCode.SUBLEDGERS_SOURCES_REVERSE
            )
        )
        with self.assertRaises(PermissionDenied):
            self.reverse(target)
        self.assertFalse(m.SupplierInvoiceAPReversal.objects.exists())
        MembershipScopeGrant.objects.filter(membership=self.membership).delete()
        with self.assertRaises(PermissionDenied):
            self.handoff()

    def test_correction_is_atomic_and_reconciles_versions_without_overwriting_history(
        self,
    ):
        old = self.handoff()
        old_payload = old.source_snapshot.copy()
        replacement = self.correction_source()
        with self.assertRaises(ValidationError):
            self.handoff(replacement, key="uncontrolled")
        with self.assertRaises(ValidationError):
            recognize_obligation(
                organization=self.organization,
                actor=self.owner,
                source_kind=INVOICE_MATCH_SOURCE_KIND,
                source_uuid=replacement.pk,
                source_version=replacement.version_number,
                idempotency_key="bypass",
            )
        kwargs = {
            "corrects": old,
            "effective_date": old.recognized_on,
            "reason": "Approved source supersession",
        }
        with (
            patch(
                "apps.accounting.services.resolve_control_account_mapping",
                side_effect=ValidationError("target failure"),
            ),
            self.assertRaises(ValidationError),
        ):
            self.handoff(replacement, key="correct033", **kwargs)
        self.assertFalse(m.SupplierInvoiceAPReversal.objects.exists())
        self.assertEqual(m.Obligation.objects.count(), 1)
        new = self.handoff(replacement, key="correct033", **kwargs)
        self.assertEqual(
            self.handoff(replacement, key="correct033", **kwargs).pk, new.pk
        )
        old.refresh_from_db()
        self.assertEqual(old.original_amount, Decimal("61.700000"))
        self.assertEqual(old.source_snapshot, old_payload)
        self.assertEqual(old.outstanding_amount, 0)
        self.assertEqual(new.outstanding_amount, Decimal("49.360000"))
        trace = reconcile_supplier_invoice_ap(
            organization=self.organization,
            actor=self.owner,
            invoice=replacement.invoice_version.invoice,
        )
        self.assertEqual(trace["active_invoice_version"], 2)
        self.assertEqual(trace["active_match_id"], str(replacement.pk))
        self.assertEqual(trace["targets"][0]["replacement_obligation_id"], str(new.pk))
        self.assertTrue(trace["targets"][1]["current_source"])
        self.assertFalse(
            JournalEntry.objects.filter(subledger_recognition__in=[old, new]).exists()
        )
        if path := os.environ.get("CEP033_TRACE_PATH"):
            Path(path).write_text(
                json.dumps(
                    {
                        "scenario": "Approved invoice/match -> L2 AP -> atomic source correction",
                        "trace": trace,
                        "source_versions_retained": m.SupplierInvoiceVersion.objects.filter(
                            invoice=replacement.invoice_version.invoice
                        ).count(),
                        "reversal_count": m.SupplierInvoiceAPReversal.objects.count(),
                        "audit": list(
                            AuditEvent.objects.filter(
                                action__in=[
                                    AuditAction.SUPPLIER_INVOICE_AP_FAILED,
                                    AuditAction.SUPPLIER_INVOICE_AP_REVERSED,
                                    AuditAction.SUBLEDGER_OBLIGATION_RECOGNIZED,
                                ]
                            )
                            .order_by("created_at")
                            .values("action", "entity_id", "metadata")
                        ),
                        "automatic_gl_journals": 0,
                        "failed_target_before_retry": {
                            "obligations": 1,
                            "source_reversals": 0,
                        },
                        "assertions": "PASS",
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

    def test_explicit_reversal_is_idempotent_and_cannot_reactivate_or_post(self):
        target = self.handoff()
        reversal = self.reverse(target)
        self.assertEqual(self.reverse(target).pk, reversal.pk)
        self.assertEqual(target.outstanding_amount, 0)
        self.assertEqual(target.settlement_status, "reversed")
        with self.assertRaises(ValidationError):
            self.handoff()
        with self.assertRaises(ValidationError):
            resolve_pinned_control_account_for_posting(
                organization=self.organization, obligation=target
            )
        with self.assertRaises(ValidationError):
            self.reverse(target, key="different-reversal")
        for operation in (
            reversal.save,
            reversal.delete,
            lambda: m.SupplierInvoiceAPReversal.objects.all().update(reason="rewrite"),
            lambda: m.SupplierInvoiceAPReversal.objects.all().delete(),
        ):
            with self.assertRaises(ValidationError):
                operation()
        # DB concurrency backstop, bypassing the application save intentionally.
        with (
            self.assertRaises(IntegrityError),
            transaction.atomic(),
            patch.object(m.SupplierInvoiceAPReversal, "full_clean"),
        ):
            m.SupplierInvoiceAPReversal.objects.create(
                organization=self.organization,
                obligation=target,
                effective_date=target.recognized_on,
                reason="Duplicate",
                idempotency_key="duplicate",
                payload_hash=_canonical_hash("duplicate"),
                reversed_by=self.membership,
            )

    def test_reversal_preserves_aging_cutoff_and_reconciliation_amount(self):
        target = self.handoff()
        tomorrow = timezone.localdate() + timedelta(days=1)
        reversal = reverse_supplier_invoice_obligation(
            organization=self.organization,
            actor=self.owner,
            obligation=target,
            effective_date=tomorrow,
            reason="Explicit effective cutoff",
            idempotency_key="cutoff",
        )
        for cutoff, expected in (
            (target.recognized_on, target.original_amount),
            (tomorrow, Decimal(0)),
        ):
            aging = run_aging(
                organization=self.organization,
                actor=self.owner,
                direction="payable",
                as_of_date=cutoff,
                idempotency_key=f"aging-{cutoff}",
            )
            self.assertEqual(aging.outstanding_total, expected)
        reconciliation = run_subledger_reconciliation(
            organization=self.organization,
            actor=self.owner,
            direction="payable",
            as_of_date=reversal.effective_date,
            idempotency_key="reconcile-cutoff",
        )
        self.assertEqual(reconciliation.subledger_outstanding_total, 0)

    def test_failure_after_target_insert_rolls_back_and_retains_retry_evidence(self):
        with (
            patch(
                "apps.subledgers.services.record_audit_event",
                side_effect=IntegrityError("injected after insert"),
            ),
            self.assertRaises(IntegrityError),
        ):
            self.handoff()
        self.assertFalse(m.Obligation.objects.exists())
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.SUPPLIER_INVOICE_AP_FAILED
            ).exists()
        )
        self.assertEqual(self.handoff().source_uuid, self.match.pk)


class InvoiceAPConcurrencyTests(InvoiceAPFixture, TransactionTestCase):
    serialized_rollback = True

    def test_concurrent_acceptance_creates_one_target_occurrence(self):
        barrier = Barrier(2)

        def accept(index):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return self.handoff(key=f"race033-{index}").pk
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(accept, (1, 2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(m.Obligation.objects.count(), 1)


class InvoiceAPMigrationTests(InvoiceAPFixture, TransactionTestCase):
    serialized_rollback = True

    def test_additive_migration_preserves_existing_obligation_and_source_history(self):
        target = self.handoff()
        before = m.Obligation.objects.filter(pk=target.pk).values().get()
        source_before = (
            m.SupplierInvoiceVersion.objects.filter(pk=self.match.invoice_version_id)
            .values()
            .get()
        )
        latest = ("subledgers", "0005_supplierinvoiceapreversal")
        previous = ("subledgers", "0004_obligation_control_account_and_more")
        executor = MigrationExecutor(connection)
        try:
            executor.migrate([previous])
            self.assertNotIn(
                "subledgers_supplierinvoiceapreversal",
                connection.introspection.table_names(),
            )
            self.assertEqual(
                m.Obligation.objects.filter(pk=target.pk).values().get(), before
            )
            executor = MigrationExecutor(connection)
            executor.migrate([latest])
            self.assertEqual(
                m.Obligation.objects.filter(pk=target.pk).values().get(), before
            )
            self.assertEqual(
                m.SupplierInvoiceVersion.objects.filter(
                    pk=self.match.invoice_version_id
                )
                .values()
                .get(),
                source_before,
            )
            self.assertFalse(m.SupplierInvoiceAPReversal.objects.exists())
            self.assertEqual(self.reverse(target).obligation_id, target.pk)
        finally:
            MigrationExecutor(connection).migrate([latest])
