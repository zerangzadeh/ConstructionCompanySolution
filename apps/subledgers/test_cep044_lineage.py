"""Structural persistence only; no write-off financial policy is activated."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from apps.accounts.models import User
from apps.organizations.models import OrganizationMembership
from apps.organizations.services import create_organization_with_owner

from .models import Obligation, WriteOffDecision, WriteOffProposal
from .services import approve_write_off, reverse_write_off


class WriteOffLineageFixture:
    def setUp(self):
        self.actor = User.objects.create_user(username="cep044-source-owner")
        self.organization = create_organization_with_owner(
            owner=self.actor, name="CEP044 synthetic", slug="cep044-source"
        )
        self.membership = OrganizationMembership.objects.get(
            organization=self.organization, user=self.actor
        )
        self.obligation = self.make_obligation()
        self.original = self.make_proposal("original")
        # Rejection is an existing supported model state. Structural lineage
        # neither assumes an approval nor changes the predecessor's balance.
        self.decision = WriteOffDecision.objects.create(
            organization=self.organization,
            proposal=self.original,
            decision="rejected",
            reason="Retained synthetic decision",
            decided_by=self.membership,
        )

    def make_obligation(self, **overrides):
        identity = uuid4()
        values = {
            "organization": self.organization,
            "direction": "payable",
            "source_kind": "synthetic.retained.cep044",
            "source_uuid": identity,
            "source_version": 1,
            "source_status": "retained",
            "source_hash": "retained",
            "source_snapshot": {"source_id": str(identity), "version": 1},
            "party_name_snapshot": "Synthetic retained party",
            "original_amount": Decimal("100.000000"),
            "recognized_on": date(2026, 10, 19),
            "idempotency_key": str(identity),
            "payload_hash": "retained",
            "recognized_by": self.membership,
        }
        values.update(overrides)
        return Obligation.objects.create(**values)

    def make_proposal(self, key, **overrides):
        values = {
            "organization": self.organization,
            "obligation": self.obligation,
            "amount": Decimal("5.000000"),
            "effective_date": date(2026, 10, 19),
            "reason": "Synthetic retained source proposal",
            "idempotency_key": key,
            "payload_hash": key,
            "proposed_by": self.membership,
        }
        values.update(overrides)
        return WriteOffProposal.objects.create(**values)


class WriteOffLineageTests(WriteOffLineageFixture, TestCase):
    def test_optional_link_preserves_existing_source_and_exact_predecessor(self):
        before = Obligation.objects.values().get(pk=self.obligation.pk)
        replacement = self.make_proposal("linked", corrects=self.decision)
        replacement.refresh_from_db()
        self.original.refresh_from_db()
        self.assertIsNone(self.original.corrects_id)
        self.assertEqual(replacement.corrects_id, self.decision.pk)
        self.assertEqual(self.decision.replacement_proposals.get().pk, replacement.pk)
        self.assertEqual(Obligation.objects.values().get(pk=self.obligation.pk), before)
        self.assertEqual(self.obligation.outstanding_amount, Decimal("100.000000"))
        self.assertFalse(hasattr(replacement, "decision"))

    def test_foreign_tenant_predecessor_and_foreign_actor_are_rejected(self):
        outsider = User.objects.create_user(username="cep044-other-owner")
        other = create_organization_with_owner(
            owner=outsider, name="Other synthetic", slug="cep044-other"
        )
        other_member = OrganizationMembership.objects.get(
            organization=other, user=outsider
        )
        other_obligation = self.make_obligation(
            organization=other, recognized_by=other_member
        )
        other_proposal = self.make_proposal(
            "other",
            organization=other,
            obligation=other_obligation,
            proposed_by=other_member,
        )
        other_decision = WriteOffDecision.objects.create(
            organization=other,
            proposal=other_proposal,
            decision="rejected",
            reason="Other retained decision",
            decided_by=other_member,
        )
        for changes in (
            {"corrects": other_decision},
            {"corrects": self.decision, "proposed_by": other_member},
            {
                "organization": other,
                "obligation": other_obligation,
                "proposed_by": other_member,
                "corrects": self.decision,
            },
        ):
            with (
                self.subTest(changes=tuple(changes)),
                self.assertRaises(ValidationError),
            ):
                self.make_proposal("denied", **changes)
        self.assertFalse(
            WriteOffProposal.objects.filter(idempotency_key="denied").exists()
        )

    def test_different_obligation_and_self_reference_are_rejected(self):
        second = self.make_obligation()
        with self.assertRaises(ValidationError):
            self.make_proposal(
                "wrong-obligation", obligation=second, corrects=self.decision
            )
        self.original.corrects = self.decision
        with self.assertRaises(ValidationError):
            self.original.clean()

    def test_source_link_cannot_be_rewritten_deleted_or_bulk_bypassed(self):
        replacement = self.make_proposal("immutable", corrects=self.decision)
        replacement.corrects = None
        with self.assertRaises(ValidationError):
            replacement.save()
        queryset = WriteOffProposal.objects.filter(pk=replacement.pk)
        for action in (
            lambda: queryset.update(corrects=None),
            lambda: queryset.bulk_update([replacement], ["corrects"]),
            queryset.delete,
            replacement.delete,
            lambda: WriteOffProposal.objects.bulk_create([replacement]),
        ):
            with self.subTest(action=action), self.assertRaises(ValidationError):
                action()
        replacement.refresh_from_db()
        self.assertEqual(replacement.corrects_id, self.decision.pk)
        with self.assertRaises(ValidationError):
            WriteOffDecision.objects.filter(pk=self.decision.pk).delete()
        with self.assertRaises(ProtectedError):
            WriteOffDecision._base_manager.filter(pk=self.decision.pk).delete()

    def test_existing_unique_business_key_remains_database_enforced(self):
        self.make_proposal("duplicate", corrects=self.decision)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_proposal("duplicate", corrects=self.decision)

    def test_persistence_does_not_activate_approval_or_reversal(self):
        self.make_proposal("held", corrects=self.decision)
        for operation in (approve_write_off, reverse_write_off):
            with (
                self.subTest(operation=operation.__name__),
                self.assertRaisesMessage(ValidationError, "P3-S27-Q03"),
            ):
                operation()
