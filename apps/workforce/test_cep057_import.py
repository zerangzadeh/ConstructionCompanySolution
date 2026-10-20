"""Actual opening writes, atomic recovery and tenant/security checks."""

from dataclasses import replace
from datetime import date
from decimal import Decimal as D
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.test import TestCase, override_settings

from . import test_cep057 as fixtures
from .leave_models import LeaveBalanceEntry
from .leave_opening_import import AUTHORITY, import_leave_opening, reverse_leave_opening
from .leave_services import balance_as_of


class LeaveOpeningImportTests(TestCase):
    setUp = fixtures.LeaveOpeningPreparationTests.setUp
    policy = fixtures.LeaveOpeningPreparationTests.policy
    source = fixtures.LeaveOpeningPreparationTests.source

    def dataset(self):
        return replace(self.source(), approval_reference=AUTHORITY)

    def execute(self, dataset, **kwargs):
        return import_leave_opening(
            organization=kwargs.get("organization", self.organization),
            actor=kwargs.get("actor", self.actor),
            dataset=dataset,
        )

    def test_import_reconciles_and_retry_preserves_stable_ids(self):
        ds = self.dataset()
        first = self.execute(ds)
        retry = self.execute(ds)
        self.assertEqual(first["mapping"], retry["mapping"])
        self.assertEqual((first["created"], retry["created"]), (1, 0))
        entry = LeaveBalanceEntry.objects.get()
        self.assertEqual(entry.kind, "opening")
        self.assertIn(AUTHORITY, entry.reason)
        self.assertEqual(
            balance_as_of(
                organization=self.organization,
                actor=self.actor,
                relationship=self.relationship,
                category_code="EXPLICIT",
                as_of=ds.as_of,
            ).quantity,
            D("120.5"),
        )

    def test_changed_source_with_same_key_is_rejected(self):
        ds = self.dataset()
        self.execute(ds)
        changed = replace(ds, rows=(replace(ds.rows[0], evidence_reference="changed"),))
        with self.assertRaises(ValidationError):
            self.execute(changed)
        self.assertEqual(LeaveBalanceEntry.objects.count(), 1)

    def test_reordered_source_and_controls_are_idempotent(self):
        ds = self.dataset()
        other = self.policy(category_code="SECOND")
        second = replace(ds.rows[0], source_id="row-2", policy_id=other.pk)
        ds = replace(
            ds,
            expected_count=2,
            rows=ds.rows + (second,),
            expected_totals=ds.expected_totals
            + (replace(ds.expected_totals[0], policy_id=other.pk),),
        )
        first = self.execute(ds)
        repeated = self.execute(
            replace(
                ds,
                rows=tuple(reversed(ds.rows)),
                expected_totals=tuple(reversed(ds.expected_totals)),
            )
        )
        self.assertEqual(first["mapping"], repeated["mapping"])
        self.assertEqual(repeated["created"], 0)

    def test_bad_controls_never_write(self):
        ds = self.dataset()
        with self.assertRaises(ValidationError):
            self.execute(
                replace(
                    ds, expected_totals=(replace(ds.expected_totals[0], quantity=D(3)),)
                )
            )
        self.assertFalse(LeaveBalanceEntry.objects.exists())

    def test_cutover_must_follow_asof(self):
        with self.assertRaises(ValidationError):
            self.execute(replace(self.dataset(), cutover_on=date(2026, 1, 1)))

    def test_cross_tenant_mapping_and_actor_denied(self):
        ds = self.dataset()
        with self.assertRaises(PermissionDenied):
            self.execute(ds, organization=self.other, actor=self.other_actor)
        with self.assertRaises(PermissionDenied):
            self.execute(ds, actor=self.other_actor)
        self.assertFalse(LeaveBalanceEntry.objects.exists())

    @override_settings(SETTINGS_MODULE="config.settings.production")
    def test_production_execution_denied(self):
        with self.assertRaises(PermissionDenied):
            self.execute(self.dataset())

    def test_unapproved_authority_denied(self):
        with self.assertRaises(PermissionDenied):
            self.execute(replace(self.dataset(), approval_reference="unapproved"))

    def test_transaction_failure_rolls_back_and_retry_recovers(self):
        ds = self.dataset()
        from .leave_opening_import import _append

        def fail(**kwargs):
            _append(**kwargs)
            raise RuntimeError("Injected failure after target write")

        with (
            patch("apps.workforce.leave_opening_import._append", side_effect=fail),
            self.assertRaises(RuntimeError),
        ):
            self.execute(ds)
        self.assertFalse(LeaveBalanceEntry.objects.exists())
        self.assertEqual(self.execute(ds)["created"], 1)

    def test_compensating_rollback_retains_original_and_is_idempotent(self):
        ds = self.dataset()
        self.execute(ds)
        original = LeaveBalanceEntry.objects.get()
        for _ in range(2):
            reverse_leave_opening(
                organization=self.organization, actor=self.actor, entries=[original]
            )
        self.assertEqual(LeaveBalanceEntry.objects.count(), 2)
        self.assertEqual(
            balance_as_of(
                organization=self.organization,
                actor=self.actor,
                relationship=self.relationship,
                category_code="EXPLICIT",
                as_of=ds.as_of,
            ).quantity,
            0,
        )
        with self.assertRaises(ValidationError):
            self.execute(ds)

    def test_rollback_rehearsal_recovers_committed_state(self):
        ds = self.dataset()
        self.execute(ds)
        original = LeaveBalanceEntry.objects.get()
        with transaction.atomic():
            reverse_leave_opening(
                organization=self.organization, actor=self.actor, entries=[original]
            )
            transaction.set_rollback(True)
        self.assertEqual(LeaveBalanceEntry.objects.count(), 1)
        self.assertEqual(self.execute(ds)["created"], 0)
