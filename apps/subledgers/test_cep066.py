"""Native AP/AR cutoffs, source states, scope and projection-only behavior."""

import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from django.core.exceptions import PermissionDenied
from django.test import TestCase

from apps.accounting.models import JournalEntry
from apps.organizations.services import create_organization_with_owner
from apps.treasury.models import TreasuryMovement
from tests.retirement_fixtures import explicit_fixture_roles

from . import test_cep044_writeoffs as retained
from . import tests as foundation
from .closeout_projection import settlement_reconciliation
from .models import Obligation, SubledgerReconciliationRun
from .services import allocate_settlement, reverse_settlement
from .test_cep044_writeoffs import CEP044Fixture


class ProjectionFixture:
    _member = foundation.SubledgerFoundationTests._member
    _activate_policy = foundation.SubledgerFoundationTests._activate_policy
    _obligation = foundation.SubledgerFoundationTests._obligation
    _posted_receipt = foundation.SubledgerFoundationTests._posted_receipt

    def setUp(self):
        foundation.SubledgerFoundationTests.setUp(self)
        explicit_fixture_roles(self.organization)

    def read(self, day=date(2026, 6, 1), **extra):
        return settlement_reconciliation(
            organization=self.organization, actor=self.owner, as_of_date=day, **extra
        )


class SettlementProjectionTests(ProjectionFixture, TestCase):
    def test_native_settlement_reversal_cutoffs_and_no_write(self):
        obligation = self._obligation()
        movement = self._posted_receipt()
        before = self.read()
        self.assertEqual(before["rows"][0]["state"], "open")
        allocation = allocate_settlement(
            organization=self.organization,
            actor=self.owner,
            obligation=obligation,
            movement=movement,
            amount=Decimal(100),
            effective_date=date(2026, 6, 1),
            reason="Synthetic exact settlement",
            idempotency_key="projection-allocate",
        )
        counts = [
            model.objects.count()
            for model in (
                JournalEntry,
                TreasuryMovement,
                Obligation,
                SubledgerReconciliationRun,
            )
        ]
        self.assertEqual(self.read()["rows"][0]["state"], "settled")
        self.assertEqual(self.read(date(2026, 5, 31))["rows"][0]["state"], "open")
        self.assertEqual(
            counts,
            [
                model.objects.count()
                for model in (
                    JournalEntry,
                    TreasuryMovement,
                    Obligation,
                    SubledgerReconciliationRun,
                )
            ],
        )
        reverse_settlement(
            organization=self.organization,
            actor=self.owner,
            allocation=allocation,
            effective_date=date(2026, 6, 2),
            reason="Synthetic settlement reversal",
            idempotency_key="projection-reverse",
        )
        self.assertEqual(self.read()["rows"][0]["state"], "settled")
        self.assertEqual(self.read(date(2026, 6, 2))["rows"][0]["state"], "open")
        self.assertEqual(len(self.read(date(2026, 6, 2))["rows"]), 1)

    def test_missing_mapping_is_not_zero_or_reliable_gl(self):
        self._obligation()
        row = self.read()["rows"][0]
        self.assertIsNone(row["gl"])
        self.assertIn("CONTROL_MAPPING_NOT_APPROVED", row["issues"])
        self.assertEqual(Decimal(row["outstanding"]), Decimal(100))

    def test_foreign_tenant_and_unassigned_user_fail_closed(self):
        from apps.accounts.models import User
        from apps.projects.models import Project

        denied = User.objects.create_user(username="projection-denied")
        with self.assertRaises(PermissionDenied):
            settlement_reconciliation(
                organization=self.organization,
                actor=denied,
                as_of_date=date(2026, 6, 1),
            )
        other = create_organization_with_owner(
            owner=denied, name="Other", slug="projection-other"
        )
        project = Project.objects.create(
            organization=other, code="FOREIGN", name="Foreign", created_by=denied
        )
        with self.assertRaises(PermissionDenied):
            self.read(project=project)


class NativeCorrectionProjectionTests(CEP044Fixture, TestCase):
    def read(self, day=None):
        return settlement_reconciliation(
            organization=self.organization, actor=self.owner, as_of_date=day or self.day
        )

    def test_writeoff_and_inverse_keep_original_cutoff_and_source_version(self):
        original = self.approve(self.proposal(amount=str(self.target.original_amount)))
        row = self.read()["rows"][0]
        self.assertEqual(row["state"], "written_off")
        before = row["economic_hash"]
        self.correct(original, effective_date=self.day + timedelta(days=1))
        self.assertEqual(self.read()["rows"][0]["economic_hash"], before)
        self.assertEqual(
            self.read(self.day + timedelta(days=1))["rows"][0]["state"], "open"
        )

    def test_repeat_native_exact_grain_uses_one_current_source_snapshot(self):
        from .services import run_subledger_reconciliation

        first = run_subledger_reconciliation(
            organization=self.organization,
            actor=self.owner,
            direction="payable",
            as_of_date=self.day,
            idempotency_key="first-native",
        )
        second = run_subledger_reconciliation(
            organization=self.organization,
            actor=self.owner,
            direction="payable",
            as_of_date=self.day,
            idempotency_key="second-native",
        )
        rows = self.read()["rows"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["native_slice"], str(second.account_slices.get().pk))
        self.assertEqual(
            rows[0]["native_revision"], first.account_slices.get().grain_revision + 1
        )
        self.assertEqual(rows[0]["source_version"], self.target.source_version)
        Path("docs/governance/cep/evidence/CEP-066_APAR_TRACE.json").write_text(
            json.dumps(
                {
                    "synthetic": True,
                    "first_native_run": str(first.pk),
                    "second_native_run": str(second.pk),
                    "as_of": self.day.isoformat(),
                    "result": self.read(),
                    "no_projection_write": True,
                },
                indent=2,
            )
        )

    def test_native_source_reversal_is_visible_without_duplicate_obligation(self):
        retained.WriteOffGovernanceTests.test_native_ap_reversal_and_replacement_accounting_chain(
            self
        )
        rows = self.read()["rows"]
        original = next(row for row in rows if row["obligation"] == str(self.target.pk))
        self.assertEqual(original["state"], "reversed")
        self.assertEqual(len({row["obligation"] for row in rows}), len(rows))
