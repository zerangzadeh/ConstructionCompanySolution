from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.organizations.models import MembershipRole, MembershipStatus, Organization
from apps.parties.models import PartyContact, PartyKind
from apps.parties.services import (
    add_party_contact,
    archive_business_party,
    assign_party_role,
    create_business_party,
    get_organization_parties,
)


class BusinessPartyServiceTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(
            username="party-owner", password="test-password"
        )
        self.member = User.objects.create_user(
            username="party-member", password="test-password"
        )
        self.other_owner = User.objects.create_user(
            username="party-other", password="test-password"
        )
        self.organization = Organization.objects.create(
            name="Party Company", slug="party-company"
        )
        self.other_organization = Organization.objects.create(
            name="Other Party Company", slug="other-party-company"
        )
        self.organization.memberships.create(
            user=self.owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.organization.memberships.create(
            user=self.member, role=MembershipRole.MEMBER, status=MembershipStatus.ACTIVE
        )
        self.other_organization.memberships.create(
            user=self.other_owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )

    def test_create_role_contact_and_primary_invariant_are_scoped_and_audited(
        self,
    ) -> None:
        party = create_business_party(
            organization=self.organization,
            actor=self.owner,
            party_kind=PartyKind.COMPANY,
            display_name="Concrete Supply",
            tax_identifier="TAX-001",
        )
        assign_party_role(
            organization=self.organization,
            actor=self.owner,
            party=party,
            role="supplier",
        )
        first = add_party_contact(
            organization=self.organization,
            actor=self.owner,
            party=party,
            contact_type="email",
            value="orders@example.com",
            is_primary=True,
        )
        second = add_party_contact(
            organization=self.organization,
            actor=self.owner,
            party=party,
            contact_type="phone",
            value="555-0100",
            is_primary=True,
        )

        first.refresh_from_db()
        self.assertFalse(first.is_primary)
        self.assertTrue(second.is_primary)
        self.assertTrue(
            PartyContact.objects.filter(party=party, is_primary=True).exists()
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.BUSINESS_PARTY_CREATED, entity_id=str(party.pk)
            ).exists()
        )
        self.assertTrue(
            AuditEvent.objects.filter(action=AuditAction.PARTY_ROLE_ASSIGNED).exists()
        )

    def test_party_tax_identifier_is_unique_per_tenant(self) -> None:
        create_business_party(
            organization=self.organization,
            actor=self.owner,
            party_kind="company",
            display_name="First",
            tax_identifier="TAX-001",
        )
        with self.assertRaisesMessage(
            ValueError, "طرف تجاری با این شناسه مالیاتی از قبل وجود دارد."
        ):
            create_business_party(
                organization=self.organization,
                actor=self.owner,
                party_kind="company",
                display_name="Duplicate",
                tax_identifier="TAX-001",
            )
        other_party = create_business_party(
            organization=self.other_organization,
            actor=self.other_owner,
            party_kind="company",
            display_name="Other",
            tax_identifier="TAX-001",
        )
        self.assertEqual(other_party.organization, self.other_organization)

    def test_cross_tenant_party_operations_and_member_mutation_are_denied(self) -> None:
        party = create_business_party(
            organization=self.other_organization,
            actor=self.other_owner,
            party_kind="company",
            display_name="Other",
        )
        with self.assertRaises(PermissionDenied):
            assign_party_role(
                organization=self.organization,
                actor=self.owner,
                party=party,
                role="supplier",
            )
        with self.assertRaises(PermissionDenied):
            create_business_party(
                organization=self.organization,
                actor=self.member,
                party_kind="company",
                display_name="Denied",
            )

    def test_archived_parties_are_hidden_from_tenant_listing(self) -> None:
        party = create_business_party(
            organization=self.organization,
            actor=self.owner,
            party_kind="company",
            display_name="Archive Me",
        )
        archive_business_party(
            organization=self.organization, actor=self.owner, party=party
        )
        self.assertFalse(
            get_organization_parties(
                user=self.owner, organization=self.organization
            ).exists()
        )

    def test_contact_model_rejects_cross_tenant_party(self) -> None:
        party = create_business_party(
            organization=self.other_organization,
            actor=self.other_owner,
            party_kind="company",
            display_name="Other",
        )
        contact = PartyContact(
            organization=self.organization,
            party=party,
            contact_type="email",
            value="x@example.com",
        )
        with self.assertRaises(ValidationError):
            contact.full_clean()
