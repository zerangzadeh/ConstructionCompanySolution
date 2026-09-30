from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.organizations.models import MembershipRole, MembershipStatus, Organization
from apps.parties.models import PartyAliasType, PartyClassificationKind
from apps.parties.services import (
    assign_party_classification,
    create_business_party,
    create_party_classification,
    find_parties_by_alias,
    get_effective_party_representatives,
    record_business_party_merge,
    record_party_alias,
    record_party_representative,
    revoke_party_classification,
    revoke_party_representative,
)


class P1S17PartyGovernanceTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="s17-owner", password="test")
        self.member = User.objects.create_user(username="s17-member", password="test")
        self.other_owner = User.objects.create_user(
            username="s17-other-owner", password="test"
        )
        self.organization = Organization.objects.create(name="S17", slug="s17")
        self.other_organization = Organization.objects.create(
            name="S17 Other", slug="s17-other"
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
        self.party = create_business_party(
            organization=self.organization,
            actor=self.owner,
            party_kind="company",
            display_name="Main Party",
        )

    def test_alias_is_normalized_immutable_and_audited(self) -> None:
        alias = record_party_alias(
            organization=self.organization,
            actor=self.owner,
            party=self.party,
            alias_type=PartyAliasType.DISPLAY_NAME,
            value="  سابقه   نام  ",
            reason="Historical trading name",
        )

        self.assertEqual(alias.value, "سابقه   نام")
        self.assertEqual(alias.normalized_value, "سابقه نام")
        alias.reason = "changed"
        with self.assertRaises(ValidationError):
            alias.save()
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.PARTY_ALIAS_RECORDED,
                entity_id=str(alias.pk),
            ).exists()
        )

    def test_alias_resolution_is_tenant_local_and_follows_merge_lineage(self) -> None:
        source = create_business_party(
            organization=self.organization,
            actor=self.owner,
            party_kind="company",
            display_name="Source",
        )
        record_party_alias(
            organization=self.organization,
            actor=self.owner,
            party=source,
            alias_type=PartyAliasType.OTHER,
            value="Shared Alias",
            reason="Known name",
        )
        other_party = create_business_party(
            organization=self.other_organization,
            actor=self.other_owner,
            party_kind="company",
            display_name="Other",
        )
        record_party_alias(
            organization=self.other_organization,
            actor=self.other_owner,
            party=other_party,
            alias_type=PartyAliasType.OTHER,
            value="Shared Alias",
            reason="Other Tenant evidence",
        )
        record_business_party_merge(
            organization=self.organization,
            actor=self.owner,
            source=source,
            survivor=self.party,
            reason="Confirmed duplicate",
        )

        self.assertEqual(
            find_parties_by_alias(
                user=self.owner,
                organization=self.organization,
                alias_type=PartyAliasType.OTHER,
                value="shared alias",
            ),
            [self.party],
        )

    def test_classification_assignment_is_historical_and_tenant_scoped(self) -> None:
        classification = create_party_classification(
            organization=self.organization,
            actor=self.owner,
            kind=PartyClassificationKind.CATEGORY,
            code=" STRATEGIC ",
            name="Strategic supplier",
        )
        assignment = assign_party_classification(
            organization=self.organization,
            actor=self.owner,
            party=self.party,
            classification=classification,
        )
        revoked = revoke_party_classification(
            organization=self.organization,
            actor=self.owner,
            assignment=assignment,
            reason="Classification reviewed",
        )

        self.assertEqual(classification.code, "strategic")
        self.assertIsNotNone(revoked.revoked_at)
        self.assertEqual(revoked.revocation_reason, "Classification reviewed")
        other_party = create_business_party(
            organization=self.other_organization,
            actor=self.other_owner,
            party_kind="company",
            display_name="Other tenant party",
        )
        with self.assertRaises(PermissionDenied):
            assign_party_classification(
                organization=self.organization,
                actor=self.owner,
                party=other_party,
                classification=classification,
            )

    def test_representative_effectivity_revocation_and_evidence(self) -> None:
        now = timezone.now()
        current = record_party_representative(
            organization=self.organization,
            actor=self.owner,
            party=self.party,
            authority="signatory",
            full_name="Authorized Signatory",
            evidence_reference="board-resolution-42",
            effective_from=now - timedelta(days=1),
        )
        record_party_representative(
            organization=self.organization,
            actor=self.owner,
            party=self.party,
            authority="representative",
            full_name="Future Representative",
            evidence_reference="letter-9",
            effective_from=now + timedelta(days=1),
        )

        self.assertEqual(
            list(
                get_effective_party_representatives(
                    user=self.owner,
                    organization=self.organization,
                    party=self.party,
                    at=now,
                )
            ),
            [current],
        )
        current.evidence_reference = "replacement-reference"
        with self.assertRaises(ValidationError):
            current.save()
        current.refresh_from_db()
        revoke_party_representative(
            organization=self.organization,
            actor=self.owner,
            representative=current,
            reason="Authority withdrawn",
        )
        self.assertFalse(
            get_effective_party_representatives(
                user=self.owner,
                organization=self.organization,
                party=self.party,
                at=now,
            ).exists()
        )

    def test_governance_mutations_require_dedicated_permission(self) -> None:
        with self.assertRaises(PermissionDenied):
            record_party_alias(
                organization=self.organization,
                actor=self.member,
                party=self.party,
                alias_type=PartyAliasType.OTHER,
                value="Denied",
                reason="No permission",
            )
