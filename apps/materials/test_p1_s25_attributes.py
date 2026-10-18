from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.materials.models import MaterialAttributeOperator, MaterialAttributeValueType
from apps.materials.services import (
    create_material,
    create_material_attribute_definition,
    create_material_attribute_definition_version,
    create_material_category,
    create_unit_of_measure,
    import_material_attribute_rows,
    record_material_attribute_value,
    record_material_price_observation,
    search_organization_materials,
)
from apps.materials.test_support import grant_material_test_owner
from apps.organizations.models import MembershipRole, MembershipStatus, Organization


class P1S25GovernedMaterialAttributeTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="s25-owner")
        self.member = User.objects.create_user(username="s25-member")
        self.other_owner = User.objects.create_user(username="s25-other-owner")
        self.organization = Organization.objects.create(name="S25", slug="s25")
        self.other_organization = Organization.objects.create(
            name="S25 Other", slug="s25-other"
        )
        grant_material_test_owner(
            organization=self.organization, user=self.owner, code="test-s25-owner"
        )
        self.organization.memberships.create(
            user=self.member, role=MembershipRole.MEMBER, status=MembershipStatus.ACTIVE
        )
        grant_material_test_owner(
            organization=self.other_organization,
            user=self.other_owner,
            code="test-s25-other-owner",
        )
        self.category = create_material_category(
            organization=self.organization,
            actor=self.owner,
            code="STEEL",
            name="Steel",
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
        self.material = create_material(
            organization=self.organization,
            actor=self.owner,
            code="REBAR",
            name="Rebar",
            category=self.category,
            unit_of_measure=self.unit,
        )
        self.definition = create_material_attribute_definition(
            organization=self.organization,
            actor=self.owner,
            category=self.category,
            code="GRADE",
            name="Steel grade",
            value_type=MaterialAttributeValueType.CHOICE,
            allowed_operators=[MaterialAttributeOperator.EQUALS],
            choice_values=["A3", "A4"],
            effective_from=timezone.now(),
        )
        self.version = self.definition.versions.get(version=1)

    def test_values_validate_against_immutable_version_and_preserve_price_source(self) -> None:
        value = record_material_attribute_value(
            organization=self.organization,
            actor=self.owner,
            material=self.material,
            definition=self.definition,
            definition_version=self.version,
            value="A4",
            source_reference="mill certificate",
        )
        self.assertEqual(value.normalized_value, "A4")
        value.value = "A3"
        with self.assertRaises(ValidationError):
            value.save()
        with self.assertRaises(ValidationError):
            record_material_attribute_value(
                organization=self.organization,
                actor=self.owner,
                material=self.material,
                definition=self.definition,
                definition_version=self.version,
                value="A5",
            )
        observation = record_material_price_observation(
            organization=self.organization,
            actor=self.owner,
            material=self.material,
            unit=self.unit,
            amount=Decimal("1250.25"),
            currency="irr",
            source_reference="supplier reference only",
            observed_at=timezone.now(),
            effective_from=timezone.now(),
        )
        self.assertEqual(observation.currency, "IRR")
        self.assertEqual(
            list(
                search_organization_materials(
                    user=self.owner, organization=self.organization, term="A4"
                )
            ),
            [self.material],
        )

    def test_import_is_idempotent_reviewable_and_cross_tenant_fails_closed(self) -> None:
        run = import_material_attribute_rows(
            organization=self.organization,
            actor=self.owner,
            idempotency_key="catalogue-2026-09-30",
            source_label="reviewed spreadsheet rows",
            rows=(
                {
                    "material_identifier": "REBAR",
                    "definition_code": "GRADE",
                    "value": "A3",
                },
                {
                    "material_identifier": "REBAR",
                    "definition_code": "GRADE",
                    "value": "UNKNOWN",
                },
            ),
        )
        self.assertEqual((run.total_rows, run.accepted_rows, run.rejected_rows), (2, 1, 1))
        self.assertEqual(
            import_material_attribute_rows(
                organization=self.organization,
                actor=self.owner,
                idempotency_key="catalogue-2026-09-30",
                source_label="ignored repeat",
                rows=(),
            ).pk,
            run.pk,
        )
        with self.assertRaises(PermissionDenied):
            create_material_attribute_definition_version(
                organization=self.other_organization,
                actor=self.other_owner,
                definition=self.definition,
                value_type=MaterialAttributeValueType.TEXT,
                allowed_operators=[MaterialAttributeOperator.CONTAINS],
                effective_from=timezone.now(),
            )
        with self.assertRaises(PermissionDenied):
            record_material_attribute_value(
                organization=self.organization,
                actor=self.member,
                material=self.material,
                definition=self.definition,
                definition_version=self.version,
                value="A4",
            )
