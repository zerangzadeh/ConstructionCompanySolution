"""Treasury/AR replacement-flow coverage for Legacy Payment retirement."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse

from apps.accounting.services import create_control_account_mapping_version
from apps.accounts.models import User
from apps.billing import tests as billing_fixture
from apps.billing.handoffs import PROGRESS_CLAIM_SOURCE_KIND
from apps.billing.services import (
    allocate_progress_claim_settlement,
    create_progress_claim_correction,
    get_progress_claim_settlement_summary,
    reverse_progress_claim_settlement,
)
from apps.organizations.models import OrganizationStatus
from apps.organizations.services import create_organization_with_owner
from apps.projects.services import create_project
from apps.subledgers.models import Obligation, SettlementAllocation
from apps.subledgers.services import recognize_obligation
from apps.treasury.models import TreasuryMovement
from apps.treasury.services import create_movement, reverse_posted_movement
from tests.retirement_fixtures import CashFixture


class ClaimSettlementFixture:
    _publish_regulatory_rules = (
        billing_fixture.ProjectBaselineWorkflowTests._publish_regulatory_rules
    )
    _baseline = billing_fixture.ProjectBaselineWorkflowTests._baseline
    _approved_baseline = billing_fixture.ProgressRecordWorkflowTests._approved_baseline
    _record = billing_fixture.ProgressRecordWorkflowTests._record
    _verified_record = billing_fixture.ProgressClaimCalculationTests._verified_record
    _claim = billing_fixture.ProgressClaimCalculationTests._claim
    _claim_for_approval = (
        billing_fixture.ProgressClaimApprovalWorkflowTests._claim_for_approval
    )
    _configure_reporting_line = (
        billing_fixture.ProgressClaimApprovalWorkflowTests._configure_reporting_line
    )
    _approve_claim = billing_fixture.ProgressClaimApprovalWorkflowTests._approve_claim

    def setUp(self):
        billing_fixture.ProjectBaselineWorkflowTests.setUp(self)
        self._configure_reporting_line()
        self.claim = self._approve_claim(self._claim_for_approval())
        self.cash = CashFixture(organization=self.organization, owner=self.owner)
        create_control_account_mapping_version(
            organization=self.organization,
            actor=self.owner,
            source_kind=PROGRESS_CLAIM_SOURCE_KIND,
            direction="receivable",
            control_account=self.cash.cash_gl,
            effective_from=date(2026, 1, 1),
            effective_to=None,
            reason="Explicit test-only AR mapping",
        )
        if getattr(self, "recognize_source", True):
            self.obligation = recognize_obligation(
                organization=self.organization,
                actor=self.owner,
                source_kind=PROGRESS_CLAIM_SOURCE_KIND,
                source_uuid=self.claim.pk,
                source_version=self.claim.revision_number,
                idempotency_key="CLAIM-AR",
            )
        self.movement = self.cash.post(
            create_movement(
                organization=self.organization,
                actor=self.owner,
                project=self.project,
                party=self.party,
                kind="receipt",
                amount=Decimal(100),
                movement_date=date(2026, 10, 19),
                description="Settlement test receipt",
                idempotency_key="CLAIM-RECEIPT",
                account=self.cash.bank,
            )
        )

    def allocate(self, *, amount="40", key="CLAIM-ALLOC", **overrides):
        args = {
            "organization": self.organization,
            "actor": self.owner,
            "claim": self.claim,
            "movement": self.movement,
            "amount": Decimal(amount),
            "effective_date": date(2026, 10, 19),
            "reason": "Explicit test settlement",
            "idempotency_key": key,
        }
        args.update(overrides)
        return allocate_progress_claim_settlement(**args)


class TreasuryClaimSettlementTransitionTests(ClaimSettlementFixture, TestCase):
    def test_partial_settlement_retry_and_caps_use_one_subledger_authority(self):
        before = TreasuryMovement.objects.count()
        allocation = self.allocate()
        self.assertEqual(allocation.pk, self.allocate().pk)
        self.assertEqual(allocation.obligation_id, self.obligation.pk)
        self.assertEqual(allocation.treasury_movement_id, self.movement.pk)
        self.assertEqual(SettlementAllocation.objects.count(), 1)
        self.assertEqual(TreasuryMovement.objects.count(), before)
        with self.assertRaises(ValidationError):
            self.allocate(amount="40", key="OVER-CAP")
        with self.assertRaises(ValidationError):
            self.allocate(amount="30")
        summary = get_progress_claim_settlement_summary(
            organization=self.organization, actor=self.owner, claim=self.claim
        )
        self.assertEqual(summary.settled_amount, Decimal(40))
        self.assertEqual(
            summary.outstanding_amount, self.claim.net_amount - Decimal(40)
        )

    def test_reversal_retains_history_reopens_capacity_and_blocks_cash_reversal_until_clear(
        self,
    ):
        allocation = self.allocate()
        with self.assertRaises(ValidationError):
            reverse_posted_movement(
                organization=self.organization,
                actor=self.owner,
                movement=self.movement,
                requested_by=self.cash.accountant_membership,
                accounting_date=date(2026, 10, 19),
                period=self.cash.period,
                reason="Must first reverse allocation",
            )
        reversal = reverse_progress_claim_settlement(
            organization=self.organization,
            actor=self.owner,
            settlement=allocation,
            effective_date=date(2026, 10, 19),
            reason="Retained reversal",
            idempotency_key="REV-ALLOC",
        )
        self.assertEqual(reversal.allocation_id, allocation.pk)
        self.assertEqual(self.allocate(key="REALLOC").amount, allocation.amount)
        self.assertEqual(SettlementAllocation.objects.count(), 2)

    def test_active_subledger_allocation_blocks_claim_correction(self):
        self.allocate()
        with self.assertRaisesMessage(ValidationError, "تسویه فعال"):
            create_progress_claim_correction(
                organization=self.organization,
                actor=self.owner,
                claim=self.claim,
                correction_kind="cancellation",
                reason="Must first reverse settlement",
            )

    def test_draft_disbursement_and_wrong_project_receipts_are_not_settlement_sources(
        self,
    ):
        other_project = create_project(
            organization=self.organization,
            actor=self.owner,
            code="MISMATCH",
            name="Other project",
        )
        for key, kind, project, posted in (
            ("DRAFT", "receipt", self.project, False),
            ("DISBURSEMENT", "disbursement", self.project, True),
            ("WRONG-PROJECT", "receipt", other_project, True),
            ("NO-PARTY", "receipt", self.project, True),
        ):
            movement = create_movement(
                organization=self.organization,
                actor=self.owner,
                project=project,
                party=None if key == "NO-PARTY" else self.party,
                kind=kind,
                amount=Decimal(100),
                movement_date=date(2026, 10, 19),
                description=key,
                idempotency_key=key,
                account=self.cash.bank,
            )
            if posted:
                movement = self.cash.post(movement)
            with self.subTest(key=key), self.assertRaises(ValidationError):
                self.allocate(movement=movement, key=key)
        self.assertEqual(SettlementAllocation.objects.count(), 0)

    def test_tenant_permission_state_and_receipt_context_fail_closed(self):
        other_owner = User.objects.create_user(username="retirement-other")
        other = create_organization_with_owner(
            owner=other_owner, name="Other", slug="retirement-other"
        )
        for overrides in (
            {"organization": other, "actor": other_owner},
            {"actor": self.member},
        ):
            with (
                self.subTest(overrides=tuple(overrides)),
                self.assertRaises(PermissionDenied),
            ):
                self.allocate(**overrides)
        self.organization.status = OrganizationStatus.SUSPENDED
        self.organization.save(update_fields=["status"])
        with self.assertRaises(PermissionDenied):
            self.allocate()
        self.assertEqual(SettlementAllocation.objects.count(), 0)

    def test_claim_endpoint_uses_posted_treasury_receipt_with_csrf(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.owner)
        session = csrf_client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()
        url = reverse("billing:claim_settlement_allocate", args=[self.claim.pk])
        self.assertEqual(csrf_client.post(url, {}).status_code, 403)
        self.client.force_login(self.owner)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()
        response = self.client.post(
            url,
            {
                "movement": str(self.movement.pk),
                "amount": "20",
                "effective_date": "2026-10-19",
                "reason": "UI replacement flow",
                "idempotency_key": "UI-ALLOC",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(SettlementAllocation.objects.get().amount, Decimal(20))


class TreasuryClaimSettlementConcurrencyTests(
    ClaimSettlementFixture, TransactionTestCase
):
    def test_concurrent_partial_settlements_cannot_exceed_claim_capacity(self):
        barrier = Barrier(2)

        def allocate(index):
            close_old_connections()
            try:
                barrier.wait(timeout=30)
                try:
                    self.allocate(key=f"CONCURRENT-{index}")
                    return "allocated"
                except ValidationError:
                    return "capacity_denied"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(allocate, (1, 2)))
        self.assertCountEqual(outcomes, ["allocated", "capacity_denied"])
        self.assertEqual(SettlementAllocation.objects.count(), 1)
        self.assertEqual(SettlementAllocation.objects.get().amount, Decimal(40))


class UnrecognizedClaimSettlementTests(ClaimSettlementFixture, TestCase):
    recognize_source = False

    def test_settlement_does_not_implicitly_recognize_ar(self):
        with self.assertRaises(ValidationError):
            self.allocate()
        self.assertEqual(Obligation.objects.count(), 0)
        self.assertEqual(SettlementAllocation.objects.count(), 0)
