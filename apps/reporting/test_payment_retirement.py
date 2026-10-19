"""Claim reconciliation uses exact Treasury/AR evidence, including cutoff."""

from datetime import date
from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.billing.services import reverse_progress_claim_settlement
from apps.billing.test_payment_retirement import ClaimSettlementFixture
from apps.reporting.reconciliation import ADAPTERS
from apps.subledgers.models import Obligation


class ClaimSettlementReportingTests(ClaimSettlementFixture, TestCase):
    def setUp(self):
        super().setUp()
        from apps.organizations.services import create_organization_with_owner
        from apps.projects.services import create_project

        self.other_organization = create_organization_with_owner(
            owner=self.owner, name="Other reporting", slug="other-reporting"
        )
        self.other_project = create_project(
            organization=self.other_organization,
            actor=self.owner,
            code="OTHER",
            name="Other project",
        )

    def pair(self, project=None, cutoff=None):
        return ADAPTERS["claim_settlement"](
            self.organization, project, cutoff or timezone.now()
        )

    def test_partial_settlement_counts_allocation_once_not_receipt(self):
        allocation = self.allocate()
        self.allocate()  # Idempotent retry cannot double count.
        with CaptureQueriesContext(connection) as queries:
            pair = self.pair(self.project)
        self.assertEqual(Decimal(pair.left.value["amount"]), self.claim.net_amount)
        self.assertEqual(Decimal(pair.right.value["amount"]), Decimal(40))
        self.assertEqual(pair.right.value["count"], 1)
        self.assertEqual(pair.right.model, "subledgers.SettlementAllocation")
        self.assertEqual(pair.right.manifest["ids"], [str(allocation.pk)])
        self.assertFalse(
            any(
                "payments_payment" in q["sql"]
                or "billing_claimsettlementallocation" in q["sql"]
                for q in queries
            )
        )

    def test_reversal_changes_current_but_preserves_pre_reversal_cutoff(self):
        allocation = self.allocate()
        cutoff = timezone.now()
        reverse_progress_claim_settlement(
            organization=self.organization,
            actor=self.owner,
            settlement=allocation,
            effective_date=date(2026, 10, 19),
            reason="Reporting reversal",
            idempotency_key="REPORT-REV",
        )
        self.assertEqual(
            Decimal(self.pair(cutoff=cutoff).right.value["amount"]), Decimal(40)
        )
        self.assertEqual(self.pair().right.value["count"], 0)
        self.allocate(key="REPORT-REALLOC")
        self.assertEqual(Decimal(self.pair().right.value["amount"]), Decimal(40))
        self.assertEqual(
            self.pair(cutoff=allocation.created_at).right.value["count"], 1
        )
        self.assertEqual(
            self.pair(cutoff=self.claim.created_at).right.value["count"], 0
        )

    def test_wrong_source_version_direction_and_context_are_excluded(self):
        self.allocate()
        for field, wrong in (
            ("source_kind", "unrelated"),
            ("source_version", 999),
            ("direction", "payable"),
            ("project_id", None),
            ("contract_id", None),
            ("organization_id", self.other_organization.pk),
        ):
            original = getattr(self.obligation, field)
            Obligation.objects.filter(pk=self.obligation.pk).update(**{field: wrong})
            with self.subTest(field=field):
                self.assertEqual(self.pair().right.value["count"], 0)
            Obligation.objects.filter(pk=self.obligation.pk).update(**{field: original})

    def test_tenant_and_project_scope_do_not_leak(self):
        self.allocate()
        pair = ADAPTERS["claim_settlement"](
            self.other_organization, None, timezone.now()
        )
        self.assertEqual(pair.left.value["count"], 0)
        self.assertEqual(pair.right.value["count"], 0)
        self.assertEqual(self.pair(self.other_project).right.value["count"], 0)
