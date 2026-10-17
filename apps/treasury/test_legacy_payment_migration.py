"""Fail-closed CEP-028 migration-preparation checks."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from django.test import SimpleTestCase

from apps.treasury.legacy_payment_migration import (
    Disposition,
    ExactMatchProof,
    SourceRow,
    reconcile_dispositions,
)


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
                Disposition(self.payment_id, "mapped", "wrong-hash", uuid4(), "evidence")
            ],
        )
        self.assertEqual(stale.exceptions[0][1], "stale_source_fingerprint")

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
        self.assertEqual(matched.source_to_target, ((str(self.payment_id), str(target_id)),))
