"""Fail-closed CEP-028 migration-preparation checks."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from django.test import SimpleTestCase, TestCase

from apps.treasury.legacy_payment_migration import (
    ZERO_POPULATION_AUTHORITY,
    Disposition,
    ExactMatchProof,
    SourceRow,
    inventory_legacy_payments,
    reconcile_demo_population,
    reconcile_dispositions,
)


class LegacyPopulationInventoryTests(TestCase):
    def test_inventory_is_tenant_scoped_and_retains_stable_source_evidence(self):
        from apps.accounts.models import User
        from apps.documents.models import RetiredPaymentEvidence
        from apps.organizations.services import create_organization_with_owner
        from apps.projects.services import create_project

        owner = User.objects.create_user(username="retirement-inventory")
        sources = []
        for number in (1, 2):
            org = create_organization_with_owner(
                owner=owner, name=f"Inventory {number}", slug=f"inventory-{number}"
            )
            project = create_project(
                organization=org, actor=owner, code="INV", name="Inventory"
            )
            # Retained evidence represents excluded demo data, never new cash.
            from apps.treasury.legacy_payment_migration import _digest

            snapshot = {
                "payment": {
                    "direction": "receipt",
                    "amount": "10.00",
                    "paid_on": "2026-01-01",
                    "status": "posted",
                    "party_id": None,
                    "project_id": str(project.pk),
                },
                "allocations": [],
                "billing_settlements": [],
                "typed_document_links": [],
            }
            payment = RetiredPaymentEvidence.objects.create(
                organization=org,
                project=project,
                payment_number="DEMO",
                source_snapshot=snapshot,
                source_sha256=_digest(snapshot),
                authority_reference=ZERO_POPULATION_AUTHORITY,
            )
            sources.append((org, payment))
        for org, payment in sources:
            rows = inventory_legacy_payments(organization_id=org.pk, cutoff=date.max)
            self.assertEqual(tuple(row.payment_id for row in rows), (payment.pk,))
            self.assertEqual(
                rows, inventory_legacy_payments(organization_id=org.pk, cutoff=date.max)
            )
            self.assertEqual(len(rows[0].fingerprint), 64)
            result = reconcile_demo_population(
                sources=rows, authority_reference=ZERO_POPULATION_AUTHORITY
            )
            self.assertEqual(result.excluded_count, 1)
            self.assertEqual(result.source_to_target, ())


class LegacyPaymentMigrationPlanTests(SimpleTestCase):
    def setUp(self) -> None:
        self.organization_id = uuid4()
        self.payment_id = uuid4()
        self.project_id = uuid4()
        self.row = SourceRow(
            payment_id=self.payment_id,
            organization_id=self.organization_id,
            direction="receipt",
            amount=Decimal("100.00"),
            paid_on=date(2026, 1, 1),
            status="posted",
            party_id=None,
            project_id=self.project_id,
            allocation_ids=(),
            settlement_ids=(),
            document_link_ids=(),
            audit_event_ids=(),
            fingerprint="source-hash",
        )

    def test_missing_or_stale_disposition_remains_exception(self) -> None:
        missing = reconcile_dispositions(sources=[self.row], dispositions=[])
        self.assertEqual(missing.exception_count, 1)
        self.assertEqual(missing.exceptions[0][1], "missing_disposition")
        stale = reconcile_dispositions(
            sources=[self.row],
            dispositions=[
                Disposition(
                    self.payment_id, "mapped", "wrong-hash", uuid4(), "evidence"
                )
            ],
        )
        self.assertEqual(stale.exceptions[0][1], "stale_source_fingerprint")

    def test_zero_history_disposition_is_repeatable_and_has_no_financial_targets(self):
        for rows in ((), (self.row,)):
            first = reconcile_demo_population(
                sources=rows, authority_reference=ZERO_POPULATION_AUTHORITY
            )
            self.assertEqual(
                first,
                reconcile_demo_population(
                    sources=rows, authority_reference=ZERO_POPULATION_AUTHORITY
                ),
            )
            self.assertEqual(first.excluded_count, len(rows))
            self.assertEqual(first.mapped_count + first.opening_count, 0)
            self.assertEqual(first.source_to_target, ())
            self.assertEqual(first.exception_count, 0)

    def test_zero_history_disposition_rejects_unapproved_or_duplicate_sources(self):
        with self.assertRaises(ValueError):
            reconcile_demo_population(
                sources=[self.row], authority_reference="unapproved"
            )
        with self.assertRaises(ValueError):
            reconcile_demo_population(
                sources=[self.row, self.row],
                authority_reference=ZERO_POPULATION_AUTHORITY,
            )

    def test_opening_and_exclusion_require_accepted_evidence(self) -> None:
        for kind in ("opening", "excluded"):
            with self.subTest(kind=kind):
                plan = Disposition(
                    self.payment_id, kind, self.row.fingerprint, uuid4(), "reviewed"
                )
                result = reconcile_dispositions(sources=[self.row], dispositions=[plan])
                self.assertEqual(result.exception_count, 1)
                self.assertEqual(result.opening_count + result.excluded_count, 0)

    def test_exact_map_requires_accepted_proof_and_matching_target(self) -> None:
        target_id = uuid4()
        account_id = uuid4()
        period_id = uuid4()
        plan = Disposition(
            self.payment_id,
            "mapped",
            self.row.fingerprint,
            uuid4(),
            "accepted-proof",
            target_id,
            exact_match_proof=ExactMatchProof(
                source_payment_id=self.payment_id,
                source_fingerprint=self.row.fingerprint,
                cash_account_id=account_id,
                fiscal_period_id=period_id,
                source_version_reference="reviewed-source-version",
                irr_basis_reference="reviewed-irr-basis",
                status_chain_reference="reviewed-status-chain",
                supporting_evidence_reference="reviewed-document",
            ),
        )
        unproved = reconcile_dispositions(
            sources=[self.row], dispositions=[plan], targets=[]
        )
        self.assertEqual(unproved.exceptions[0][1], "unaccepted_exact_match_evidence")
        target = SimpleNamespace(
            pk=target_id,
            organization_id=self.organization_id,
            kind="receipt",
            amount=Decimal("100.00"),
            movement_date=self.row.paid_on,
            project_id=self.project_id,
            party_id=None,
            currency="IRR",
            status="posted",
            journal_id=uuid4(),
            journal=SimpleNamespace(period_id=period_id),
            legs=SimpleNamespace(
                filter=lambda **kwargs: SimpleNamespace(
                    exists=lambda: kwargs["account_id"] == account_id
                )
            ),
        )
        matched = reconcile_dispositions(
            sources=[self.row],
            dispositions=[plan],
            targets=[target],
            accepted_exact_match_evidence=frozenset({"accepted-proof"}),
        )
        self.assertEqual(matched.mapped_count, 1)
        self.assertEqual(matched.exception_count, 0)
        self.assertEqual(
            matched.source_to_target, ((str(self.payment_id), str(target_id)),)
        )
