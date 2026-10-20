"""Synthetic Payroll identities; native Treasury cash, failures and replay."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.test import TestCase, TransactionTestCase

from apps.accounting.models import JournalEntry
from apps.organizations.models import BusinessPermission, PlatformPolicy
from apps.payroll import test_p7_s29_s32_financial_handoffs as fixtures
from apps.payroll.financial_handoff_services import (
    prepare_financial_handoff,
    review_financial_handoff,
)
from apps.payroll.models import (
    FinancialHandoffAcknowledgement,
    FinancialHandoffLine,
    PayrollRun,
)
from apps.payroll.services import reverse_run
from apps.projects.models import ProjectCostFact
from apps.subledgers.models import Obligation
from apps.subledgers.test_cep043_payroll_handoff import PayrollAPFixture
from tests.retirement_fixtures import CashFixture, explicit_fixture_roles

from . import payroll_handoffs as api
from .models import PaymentRequest, PayrollDisbursementReversal, TreasuryMovement
from .services import (
    cancel_payment_request,
    create_movement,
    create_payment_request,
    decide_payment_request,
    release_payment_request,
    reverse_posted_movement,
    submit_payment_request,
)


class PayrollTreasuryFixture:
    _member = fixtures.PayrollFinancialHandoffTests._member
    _monetary_versions = fixtures.PayrollFinancialHandoffTests._monetary_versions
    correction_sources = PayrollAPFixture.correction_sources

    def setUp(self):
        fixtures.PayrollFinancialHandoffTests.setUp(self)
        self.organization.memberships.get(
            user=self.actor
        ).role_definition.permissions.add(
            BusinessPermission.objects.get(code="payroll.adjust")
        )
        explicit_fixture_roles(self.organization)
        activate = CashFixture._activate_policy

        def missing_only(cash, code, parameters):
            if not PlatformPolicy.objects.filter(code=code).exists():
                activate(cash, code, parameters)

        with patch.object(CashFixture, "_activate_policy", missing_only):
            self.cash = CashFixture(organization=self.organization, owner=self.owner)
        explicit_fixture_roles(self.organization)
        self.proposal = self.source(self.run, "original")
        self.line = self.proposal.lines.get()

    def source(self, run, key):
        result = prepare_financial_handoff(
            organization=self.organization,
            actor=self.actor,
            run=run,
            family="payment",
            idempotency_key=key,
            reason="Synthetic payment source",
        )
        review_financial_handoff(
            organization=self.organization,
            actor=self.reviewer,
            proposal=result,
            disposition="accepted",
            reason="Explicit source review",
        )
        return result

    def consume(self, line=None, **overrides):
        args = {
            "organization": self.organization,
            "actor": self.owner,
            "line_id": (line or self.line).pk,
            "reason": "Synthetic salary request",
        }
        args.update(overrides)
        return api.consume_payment_line(**args)

    def paid(self):
        request = self.consume()
        submit_payment_request(
            organization=self.organization,
            actor=self.owner,
            request=request,
            reason="Submit",
        )
        decide_payment_request(
            organization=self.organization,
            actor=self.owner,
            request=request,
            approve=True,
            reason="Approve",
        )
        movement = create_movement(
            organization=self.organization,
            actor=self.owner,
            kind="disbursement",
            movement_date=date(2026, 10, 20),
            amount=request.amount,
            description="Salary settlement",
            idempotency_key="cash",
            account=self.cash.bank,
            origin_request=request,
        )
        self.cash.post(movement)
        movement.refresh_from_db()
        release_payment_request(
            organization=self.organization,
            actor=self.owner,
            request=request,
            movement=movement,
            reason="Paid",
        )
        return request, movement

    def reversal_source(self):
        reversal = reverse_run(
            organization=self.organization,
            actor=self.actor,
            original_run=self.run,
            idempotency_key="reverse-source",
            reason="Synthetic correction",
        )
        return self.source(reversal.reversal_run, "reversal").lines.get()


class PayrollTreasuryTests(PayrollTreasuryFixture, TestCase):
    def test_rejected_or_corrupt_source_version_cannot_create_request(self):
        review = self.proposal.review
        # Normal ORM mutation is prohibited; inject corruption only in this
        # disposable synthetic database to exercise consumer revalidation.
        with self.assertRaises(ValidationError):
            type(review).objects.filter(pk=review.pk).update(disposition="rejected")
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE payroll_financialhandoffreview SET disposition=%s WHERE id=%s",
                ["rejected", review.pk],
            )
        with self.assertRaises(ValidationError):
            self.consume()
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE payroll_financialhandoffreview SET disposition=%s WHERE id=%s",
                ["accepted", review.pk],
            )
            cursor.execute(
                "UPDATE payroll_financialhandoffline SET content_digest=%s WHERE id=%s",
                ["bad-version", self.line.pk],
            )
        with self.assertRaises(ValidationError):
            self.consume()
        self.assertFalse(PaymentRequest.objects.exists())

    def test_rejected_payment_request_reversal_retains_terminal_history(self):
        request = self.consume()
        submit_payment_request(
            organization=self.organization,
            actor=self.owner,
            request=request,
            reason="Submit",
        )
        decide_payment_request(
            organization=self.organization,
            actor=self.owner,
            request=request,
            approve=False,
            reason="Reject",
        )
        link = self.consume(self.reversal_source())
        request.refresh_from_db()
        self.assertEqual(request.status, "rejected")
        self.assertEqual(link.request_id, request.pk)
        self.assertFalse(TreasuryMovement.objects.exists())

    def test_pre_migration_manual_request_replay_keeps_legacy_hash(self):
        from apps.parties.models import BusinessParty

        party = BusinessParty.objects.create(
            organization=self.organization,
            party_kind="individual",
            display_name="Synthetic payee",
        )
        args = {
            "organization": self.organization,
            "actor": self.owner,
            "kind": "payment",
            "amount": Decimal(100),
            "purpose": "Legacy request",
            "idempotency_key": "legacy",
            "party": party,
        }
        request = create_payment_request(**args)
        legacy_payload = {
            "kind": "payment",
            "amount": "100",
            "purpose": "Legacy request",
            "employee": None,
            "party": str(party.pk),
            "project": None,
            "site": None,
            "source_expense": None,
            "source_expense_version": None,
        }
        legacy_hash = hashlib.sha256(
            json.dumps(
                legacy_payload, sort_keys=True, separators=(",", ":"), default=str
            ).encode()
        ).hexdigest()
        PaymentRequest.objects.filter(pk=request.pk).update(payload_hash=legacy_hash)
        self.assertEqual(create_payment_request(**args).pk, request.pk)

    def test_replacement_waits_for_original_reversal_and_keeps_both_versions(self):
        original = self.consume()
        reverse, replacement = self.correction_sources()
        line = replacement.lines.get()
        with self.assertRaises(ValidationError):
            self.consume(line)
        self.consume(reverse.lines.get())
        fresh = self.consume(line)
        self.assertEqual(fresh.amount, Decimal(1000))
        self.assertNotEqual(fresh.pk, original.pk)
        self.assertEqual(
            fresh.source_payroll_line.proposal.predecessor_id, self.proposal.pk
        )
        self.assertEqual(PaymentRequest.objects.count(), 2)
        self.assertFalse(TreasuryMovement.objects.exists())

    def test_draft_replay_identity_and_authority(self):
        request = self.consume()
        self.assertEqual(self.consume().pk, request.pk)
        self.assertEqual(request.source_payroll_version, self.line.content_digest)
        self.assertEqual(request.employee_id, self.employee.pk)
        self.assertEqual(request.amount, Decimal(900))
        self.assertEqual(PaymentRequest.objects.count(), 1)
        for model in (TreasuryMovement, JournalEntry, Obligation, ProjectCostFact):
            self.assertEqual(model.objects.count(), 0)
        with self.assertRaises(ValidationError):
            self.consume(reason="Conflicting replay")
        with self.assertRaises(ValidationError):
            request.amount = Decimal(901)
            request.save()
        with self.assertRaises(ValidationError):
            request.delete()

    def test_failure_rolls_back_target_and_retry_rechecks_source(self):
        with (
            patch.object(
                PaymentRequest, "save", side_effect=ValidationError("Injected")
            ),
            self.assertRaises(ValidationError),
        ):
            self.consume()
        self.assertFalse(PaymentRequest.objects.exists())
        self.assertEqual(
            FinancialHandoffAcknowledgement.objects.get().downstream_status, "failed"
        )
        PayrollRun.objects.filter(pk=self.run.pk).update(calculation_digest="stale")
        with self.assertRaises(ValidationError):
            self.consume()
        self.assertFalse(PaymentRequest.objects.exists())
        PayrollRun.objects.filter(pk=self.run.pk).update(
            calculation_digest="calculation-v1"
        )
        self.assertEqual(self.consume().amount, Decimal(900))

    def test_permissions_tenant_status_and_unreviewed_source_fail_closed(self):
        with self.assertRaises(PermissionDenied):
            self.consume(actor=self.denied)
        from apps.organizations.services import create_organization_with_owner

        other = create_organization_with_owner(
            owner=self.owner, name="Foreign", slug="foreign"
        )
        with self.assertRaises(FinancialHandoffLine.DoesNotExist):
            self.consume(organization=other)
        self.organization.status = "suspended"
        self.organization.save(update_fields=["status"])
        with self.assertRaises(PermissionDenied):
            self.consume()

    def test_native_cash_post_release_and_retained_cash_reversal(self):
        request, movement = self.paid()
        self.assertEqual(movement.status, "posted")
        line = self.reversal_source()
        with self.assertRaises(ValidationError):
            self.consume(line)
        reversal = reverse_posted_movement(
            organization=self.organization,
            actor=self.owner,
            movement=movement,
            period=self.cash.period,
            requested_by=self.cash.accountant_membership,
            accounting_date=date(2026, 10, 20),
            reason="Native exact reversal",
        )
        link = self.consume(line, reversal_movement=reversal)
        self.assertEqual(self.consume(line, reversal_movement=reversal).pk, link.pk)
        self.assertEqual(link.request_id, request.pk)
        self.assertEqual(link.reversal_movement_id, reversal.pk)
        trace = api.reconcile_payment_handoff(
            organization=self.organization,
            actor=self.owner,
            proposal_id=line.proposal_id,
        )
        self.assertEqual(trace["rows"][0]["issues"], [])
        self.assertEqual(trace["rows"][0]["cash_reversal"], str(reversal.pk))
        Path("docs/governance/cep/evidence/CEP-061_INTEGRATION_TRACE.json").write_text(
            json.dumps(trace, indent=2, default=str), encoding="utf-8"
        )
        self.assertFalse(Obligation.objects.exists())
        self.assertFalse(ProjectCostFact.objects.exists())

    def test_unpaid_reversal_cancels_without_cash_and_preserves_source(self):
        request = self.consume()
        line = self.reversal_source()
        link = self.consume(line)
        request.refresh_from_db()
        self.assertEqual(request.status, "cancelled")
        self.assertEqual(link.request_id, request.pk)
        self.assertIsNone(link.reversal_movement_id)
        self.assertFalse(TreasuryMovement.objects.exists())
        with self.assertRaises(ValidationError):
            link.save()
        self.assertEqual(PayrollDisbursementReversal.objects.count(), 1)

    def test_database_duplicate_source_and_missing_source_guard(self):
        request = self.consume()
        with self.assertRaises(ValidationError):
            create_payment_request(
                organization=self.organization,
                actor=self.owner,
                kind="payroll",
                employee=self.employee,
                amount=Decimal(900),
                purpose="No source",
                idempotency_key="no-source",
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            PaymentRequest.objects.filter(pk=request.pk).update(
                source_payroll_line=None
            )

    def test_cancel_after_pending_cash_and_stale_source_posting_are_blocked(self):
        request = self.consume()
        submit_payment_request(
            organization=self.organization,
            actor=self.owner,
            request=request,
            reason="Submit",
        )
        decide_payment_request(
            organization=self.organization,
            actor=self.owner,
            request=request,
            approve=True,
            reason="Approve",
        )
        movement = create_movement(
            organization=self.organization,
            actor=self.owner,
            kind="disbursement",
            movement_date=date(2026, 10, 20),
            amount=request.amount,
            description="Salary settlement",
            idempotency_key="cash",
            account=self.cash.bank,
            origin_request=request,
        )
        with self.assertRaises(ValidationError):
            cancel_payment_request(
                organization=self.organization,
                actor=self.owner,
                request=request,
                reason="Cannot cancel",
            )
        line = self.reversal_source()
        with self.assertRaises(ValidationError):
            self.cash.post(movement)
        self.consume(line)
        request.refresh_from_db()
        self.assertEqual(request.status, "cancelled")
        self.assertEqual(TreasuryMovement.objects.get(pk=movement.pk).status, "submitted")
        self.assertFalse(TreasuryMovement.objects.filter(status="posted").exists())

    def test_source_reversal_between_cash_post_and_release_retains_native_reversal(
        self,
    ):
        # A post/release failure cannot strand the already-recorded cash effect.
        with patch("apps.treasury.test_cep061.release_payment_request"):
            request, movement = self.paid()
        line = self.reversal_source()
        with self.assertRaises(ValidationError):
            self.consume(line)
        cash_reversal = reverse_posted_movement(
            organization=self.organization,
            actor=self.owner,
            movement=movement,
            requested_by=self.cash.accountant_membership,
            period=self.cash.period,
            accounting_date=date(2026, 10, 20),
            reason="Reverse posted, unreleased cash",
        )
        link = self.consume(line, reversal_movement=cash_reversal)
        request.refresh_from_db()
        self.assertEqual(request.status, "cancelled")
        self.assertEqual(link.reversal_movement_id, cash_reversal.pk)


class PayrollSourceRegressionTests(fixtures.PayrollFinancialHandoffTests):
    def setUp(self):
        super().setUp()
        explicit_fixture_roles(self.organization)


class PayrollTreasuryConcurrencyTests(PayrollTreasuryFixture, TransactionTestCase):
    def test_same_source_race_creates_one_request(self):
        def consume():
            close_old_connections()
            try:
                return self.consume().pk
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            ids = list(pool.map(lambda _: consume(), range(2)))
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(PaymentRequest.objects.count(), 1)
