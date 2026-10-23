"""Choice narrowing uses canonical posted Treasury evidence and allocation caps."""

from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.test import TestCase

from apps.subledgers import tests as foundation
from apps.subledgers.services import allocate_settlement, settlement_movement_choices
from apps.treasury.services import create_movement


class SettlementChoiceTests(TestCase):
    setUp = foundation.SubledgerFoundationTests.setUp
    _member = foundation.SubledgerFoundationTests._member
    _activate_policy = foundation.SubledgerFoundationTests._activate_policy
    _obligation = foundation.SubledgerFoundationTests._obligation
    _posted_receipt = foundation.SubledgerFoundationTests._posted_receipt

    def test_only_posted_compatible_unconsumed_movement_is_offered(self):
        obligation = self._obligation()
        posted = self._posted_receipt()
        create_movement(
            organization=self.organization,
            actor=self.owner,
            kind="receipt",
            movement_date=date(2026, 6, 1),
            amount=Decimal(100),
            description="Draft must not be offered",
            idempotency_key="draft-source",
            account=self.bank,
        )
        choices = settlement_movement_choices(
            organization=self.organization, actor=self.owner, obligation=obligation
        )
        self.assertEqual(list(choices.values_list("pk", flat=True)), [posted.pk])
        allocate_settlement(
            organization=self.organization,
            actor=self.owner,
            obligation=obligation,
            movement=posted,
            amount=Decimal(100),
            effective_date=date(2026, 6, 1),
            reason="Explicit full allocation",
            idempotency_key="full-choice",
        )
        self.assertFalse(
            settlement_movement_choices(
                organization=self.organization, actor=self.owner, obligation=obligation
            ).exists()
        )

    def test_unauthorized_actor_cannot_discover_settlement_sources(self):
        from apps.accounts.models import User

        with self.assertRaises(PermissionDenied):
            settlement_movement_choices(
                organization=self.organization,
                actor=User.objects.create_user(username="no-allocation"),
                obligation=self._obligation(),
            )
