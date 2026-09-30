from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.organizations.models import MembershipRole, MembershipStatus, Organization
from apps.parties.models import (
    PartyRestriction,
    PartyRestrictionEffect,
    PartyRestrictionScope,
)
from apps.parties.services import (
    assert_party_transaction_allowed,
    assign_party_role,
    create_business_party,
    create_tenant_party_restriction,
    find_duplicate_candidates,
    record_business_party_merge,
    resolve_canonical_party,
    revoke_tenant_party_restriction,
    update_business_party,
)


class P1S16PartyFoundationTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(
            username="p1-s16-owner", password="test-password"
        )
        self.member = User.objects.create_user(
            username="p1-s16-member", password="test-password"
        )
        self.other_owner = User.objects.create_user(
            username="p1-s16-other-owner", password="test-password"
        )
        self.organization = Organization.objects.create(
            name="P1 S16 Company", slug="p1-s16-company"
        )
        self.other_organization = Organization.objects.create(
            name="P1 S16 Other", slug="p1-s16-other"
        )
        self.organization.memberships.create(
            user=self.owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.organization.memberships.create(
            user=self.member,
            role=MembershipRole.MEMBER,
            status=MembershipStatus.ACTIVE,
        )
        self.other_organization.memberships.create(
            user=self.other_owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )

    def create_party(self, name: str, *, organization=None, actor=None, identifier=""):
        return create_business_party(
            organization=organization or self.organization,
            actor=actor or self.owner,
            party_kind="company",
            display_name=name,
            tax_identifier=identifier,
        )

    def test_identity_normalization_preserves_originals_and_appends_snapshots(
        self,
    ) -> None:
        party = self.create_party("  Acme   Builders  ", identifier=" Ab-۱۲۳ ")

        self.assertEqual(party.display_name, "Acme   Builders")
        self.assertEqual(party.tax_identifier, "Ab-۱۲۳")
        self.assertEqual(party.normalized_display_name, "acme builders")
        self.assertEqual(party.normalized_tax_identifier, "ab-۱۲۳")
        first = party.identity_snapshots.get(sequence=1)
        self.assertEqual(first.display_name, "Acme   Builders")

        update_business_party(
            organization=self.organization,
            actor=self.owner,
            party=party,
            party_kind="company",
            display_name="ACME Builders Group",
            legal_name="Acme Legal",
            tax_identifier="AB-۱۲۳",
        )

        snapshots = list(party.identity_snapshots.order_by("sequence"))
        self.assertEqual(len(snapshots), 2)
        self.assertEqual(snapshots[0].display_name, "Acme   Builders")
        self.assertEqual(snapshots[1].display_name, "ACME Builders Group")
        snapshots[0].reason = "changed"
        with self.assertRaises(ValidationError):
            snapshots[0].save()

    def test_duplicate_candidates_are_explainable_tenant_local_and_non_mutating(
        self,
    ) -> None:
        first = self.create_party("Alpha   Construction")
        second = self.create_party("ALPHA construction")
        self.create_party(
            "alpha construction",
            organization=self.other_organization,
            actor=self.other_owner,
        )

        candidates = find_duplicate_candidates(
            user=self.owner,
            organization=self.organization,
            party=first,
        )

        self.assertEqual([candidate.party for candidate in candidates], [second])
        self.assertEqual(candidates[0].matched_fields, ("display_name",))
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertIsNone(first.merged_into_id)
        self.assertIsNone(second.merged_into_id)

    def test_normalized_identifier_collision_is_tenant_scoped_and_fails_closed(
        self,
    ) -> None:
        self.create_party("First", identifier=" Ref-001 ")
        with self.assertRaisesMessage(
            ValueError, "طرف تجاری با این شناسه مالیاتی از قبل وجود دارد."
        ):
            self.create_party("Duplicate", identifier="REF-001")

        other = self.create_party(
            "Other Tenant",
            organization=self.other_organization,
            actor=self.other_owner,
            identifier="ref-001",
        )
        self.assertEqual(other.organization, self.other_organization)

    def test_merge_records_lineage_without_rewriting_historical_references(
        self,
    ) -> None:
        source = self.create_party("Source Party", identifier="SOURCE-001")
        survivor = self.create_party("Survivor Party")
        historical_role = assign_party_role(
            organization=self.organization,
            actor=self.owner,
            party=source,
            role="supplier",
        )

        merged = record_business_party_merge(
            organization=self.organization,
            actor=self.owner,
            source=source,
            survivor=survivor,
            reason="Confirmed duplicate identity",
        )

        historical_role.refresh_from_db()
        self.assertEqual(historical_role.party_id, source.pk)
        self.assertEqual(merged.merged_into_id, survivor.pk)
        self.assertIsNotNone(merged.archived_at)
        self.assertEqual(
            resolve_canonical_party(
                user=self.owner,
                organization=self.organization,
                party=source,
            ),
            survivor,
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.BUSINESS_PARTY_MERGED,
                entity_id=str(source.pk),
            ).exists()
        )
        updated_survivor = update_business_party(
            organization=self.organization,
            actor=self.owner,
            party=survivor,
            party_kind="company",
            display_name=survivor.display_name,
            tax_identifier="source-001",
        )
        self.assertEqual(updated_survivor.normalized_tax_identifier, "source-001")

    def test_merge_rejects_unauthorized_cross_tenant_and_chain_operations(self) -> None:
        source = self.create_party("Source")
        survivor = self.create_party("Survivor")
        other = self.create_party(
            "Other",
            organization=self.other_organization,
            actor=self.other_owner,
        )
        with self.assertRaises(PermissionDenied):
            record_business_party_merge(
                organization=self.organization,
                actor=self.member,
                source=source,
                survivor=survivor,
                reason="Denied",
            )
        with self.assertRaises(PermissionDenied):
            record_business_party_merge(
                organization=self.organization,
                actor=self.owner,
                source=source,
                survivor=other,
                reason="Cross Tenant",
            )
        record_business_party_merge(
            organization=self.organization,
            actor=self.owner,
            source=source,
            survivor=survivor,
            reason="First merge",
        )
        third = self.create_party("Third")
        with self.assertRaises(ValueError):
            record_business_party_merge(
                organization=self.organization,
                actor=self.owner,
                source=survivor,
                survivor=third,
                reason="Would create a chain",
            )

    def test_restrictions_are_explicit_effective_scoped_and_audited(self) -> None:
        party = self.create_party("Restricted Party")
        informational = create_tenant_party_restriction(
            organization=self.organization,
            actor=self.owner,
            party=party,
            code=" REVIEW_REQUIRED ",
            effect=PartyRestrictionEffect.INFORMATION_ONLY,
            reason="Generic internal review",
        )
        assert_party_transaction_allowed(organization=self.organization, party=party)
        blocking = create_tenant_party_restriction(
            organization=self.organization,
            actor=self.owner,
            party=party,
            code="manual_hold",
            effect=PartyRestrictionEffect.BLOCK_NEW_TRANSACTIONS,
            reason="Explicit generic hold",
        )
        with self.assertRaises(PermissionDenied):
            assert_party_transaction_allowed(
                organization=self.organization, party=party
            )
        revoke_tenant_party_restriction(
            organization=self.organization,
            actor=self.owner,
            restriction=blocking,
            reason="Hold cleared",
        )
        assert_party_transaction_allowed(organization=self.organization, party=party)
        self.assertEqual(informational.code, "review_required")
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.PARTY_RESTRICTION_CREATED
            ).exists()
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.PARTY_RESTRICTION_REVOKED
            ).exists()
        )

    def test_tenant_actor_cannot_weaken_platform_restriction(self) -> None:
        party = self.create_party("Platform Restricted")
        platform_restriction = PartyRestriction.objects.create(
            organization=self.organization,
            party=party,
            scope=PartyRestrictionScope.PLATFORM,
            code="platform_hold",
            effect=PartyRestrictionEffect.BLOCK_NEW_TRANSACTIONS,
            reason="Platform-owned generic restriction fixture",
            effective_from=timezone.now(),
            created_by=self.owner,
        )

        with self.assertRaises(PermissionDenied):
            revoke_tenant_party_restriction(
                organization=self.organization,
                actor=self.owner,
                restriction=platform_restriction,
                reason="Tenant cannot revoke",
            )
        with self.assertRaises(PermissionDenied):
            assert_party_transaction_allowed(
                organization=self.organization, party=party
            )

    def test_future_and_expired_restrictions_do_not_block(self) -> None:
        party = self.create_party("Date Scoped")
        now = timezone.now()
        PartyRestriction.objects.create(
            organization=self.organization,
            party=party,
            scope=PartyRestrictionScope.TENANT,
            code="future_hold",
            effect=PartyRestrictionEffect.BLOCK_NEW_TRANSACTIONS,
            reason="Future generic hold",
            effective_from=now + timedelta(days=1),
            created_by=self.owner,
        )
        PartyRestriction.objects.create(
            organization=self.organization,
            party=party,
            scope=PartyRestrictionScope.TENANT,
            code="expired_hold",
            effect=PartyRestrictionEffect.BLOCK_NEW_TRANSACTIONS,
            reason="Expired generic hold",
            effective_from=now - timedelta(days=2),
            effective_until=now - timedelta(days=1),
            created_by=self.owner,
        )

        assert_party_transaction_allowed(
            organization=self.organization, party=party, at=now
        )
