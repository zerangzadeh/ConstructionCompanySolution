from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.test import TestCase

from apps.accounts.models import User
from apps.materials.services import (
    create_material,
    create_unit_of_measure,
    record_material_alias,
    record_material_duplicate_candidate,
    resolve_material_identifier,
    supersede_material,
)
from apps.materials.test_support import grant_material_test_owner
from apps.organizations.models import MembershipRole, MembershipStatus, Organization
from apps.procurement.services import add_purchase_request_item, create_purchase_request
from apps.projects.services import create_project


class P1S23MaterialIdentityTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="s23-owner")
        self.member = User.objects.create_user(username="s23-member")
        self.other_owner = User.objects.create_user(username="s23-other")
        self.organization = Organization.objects.create(name="S23", slug="s23")
        self.other_organization = Organization.objects.create(
            name="S23 Other", slug="s23-other"
        )
        grant_material_test_owner(
            organization=self.organization, user=self.owner, code="test-s23-owner"
        )
        self.organization.memberships.create(
            user=self.member,
            role=MembershipRole.MEMBER,
            status=MembershipStatus.ACTIVE,
        )
        grant_material_test_owner(
            organization=self.other_organization,
            user=self.other_owner,
            code="test-s23-other-owner",
        )
        self.unit = create_unit_of_measure(
            organization=self.organization,
            actor=self.owner,
            code="KG",
            name="Kilogram",
            symbol="kg",
            category="weight",
            decimal_places=3,
        )
        self.source = create_material(
            organization=self.organization,
            actor=self.owner,
            code="OLD-STEEL",
            name="Rebar steel",
            unit_of_measure=self.unit,
        )
        self.survivor = create_material(
            organization=self.organization,
            actor=self.owner,
            code="STEEL",
            name="Rebar steel canonical",
            unit_of_measure=self.unit,
        )

    def test_alias_and_supersession_are_tenant_scoped_and_non_destructive(self) -> None:
        alias = record_material_alias(
            organization=self.organization,
            actor=self.owner,
            material=self.survivor,
            code="REB-01",
            reason="known local identifier",
        )
        self.assertEqual(
            resolve_material_identifier(
                organization=self.organization, identifier=alias.code
            ),
            self.survivor,
        )
        record_material_duplicate_candidate(
            organization=self.organization,
            actor=self.owner,
            left=self.source,
            right=self.survivor,
            evidence={"basis": "manual review"},
        )
        with self.assertRaises(PermissionDenied):
            supersede_material(
                organization=self.organization,
                actor=self.member,
                source=self.source,
                survivor=self.survivor,
                reason="unauthorized",
            )

        project = create_project(
            organization=self.organization,
            actor=self.owner,
            code="P-S23",
            name="S23 project",
        )
        request = create_purchase_request(
            organization=self.organization,
            actor=self.owner,
            project=project,
            request_number="PR-S23",
            title="History retention",
        )
        item = add_purchase_request_item(
            organization=self.organization,
            actor=self.owner,
            purchase_request=request,
            material=self.source,
            quantity=Decimal(1),
        )
        supersede_material(
            organization=self.organization,
            actor=self.owner,
            source=self.source,
            survivor=self.survivor,
            reason="reviewed duplicate",
        )
        item.refresh_from_db()
        self.assertEqual(item.material, self.source)
        self.assertTrue(self.source.__class__.objects.filter(pk=self.source.pk).exists())
        self.assertEqual(
            resolve_material_identifier(
                organization=self.organization, identifier=self.source.code
            ),
            self.survivor,
        )

        with self.assertRaises(PermissionDenied):
            record_material_duplicate_candidate(
                organization=self.organization,
                actor=self.owner,
                left=self.source,
                right=create_material(
                    organization=self.other_organization,
                    actor=self.other_owner,
                    code="FOREIGN",
                    name="Foreign",
                    unit_of_measure=create_unit_of_measure(
                        organization=self.other_organization,
                        actor=self.other_owner,
                        code="KG",
                        name="Kilogram",
                        symbol="kg",
                        category="weight",
                    ),
                ),
            )
