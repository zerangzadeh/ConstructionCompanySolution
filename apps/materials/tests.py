from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from apps.accounts.models import User
from apps.materials.models import Material, MaterialCategory, UnitOfMeasure
from apps.materials.services import (
    archive_material,
    archive_material_category,
    archive_unit_of_measure,
    create_material,
    create_material_category,
    create_unit_of_measure,
    get_organization_materials,
    get_organization_units,
    update_material_category,
)
from apps.organizations.models import MembershipRole, MembershipStatus, Organization


class UnitOfMeasureServiceTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(
            username="unit-owner", password="test-password"
        )
        self.other_owner = User.objects.create_user(
            username="unit-other", password="test-password"
        )
        self.organization = Organization.objects.create(
            name="Unit Company", slug="unit-company"
        )
        self.other_organization = Organization.objects.create(
            name="Other Unit Company", slug="other-unit-company"
        )
        self.organization.memberships.create(
            user=self.owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.other_organization.memberships.create(
            user=self.other_owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )

    def test_unit_code_is_normalized_unique_per_tenant_and_precision_is_validated(
        self,
    ) -> None:
        unit = create_unit_of_measure(
            organization=self.organization,
            actor=self.owner,
            code=" m2 ",
            name="Square metre",
            symbol="m²",
            category="area",
            decimal_places=2,
        )
        self.assertEqual(unit.code, "M2")
        with self.assertRaisesMessage(
            ValueError, "واحدی با این کد یا نماد از قبل وجود دارد."
        ):
            create_unit_of_measure(
                organization=self.organization,
                actor=self.owner,
                code="m2",
                name="Duplicate",
                symbol="sqm",
                category="area",
            )
        other_unit = create_unit_of_measure(
            organization=self.other_organization,
            actor=self.other_owner,
            code="m2",
            name="Square metre",
            symbol="m²",
            category="area",
        )
        self.assertEqual(other_unit.organization, self.other_organization)
        invalid = UnitOfMeasure(
            organization=self.organization,
            code="KG",
            name="Kilogram",
            symbol="kg",
            category="weight",
            decimal_places=7,
        )
        with self.assertRaises(ValidationError):
            invalid.full_clean()

    def test_archive_and_cross_tenant_access_are_enforced(self) -> None:
        unit = create_unit_of_measure(
            organization=self.organization,
            actor=self.owner,
            code="HR",
            name="Hour",
            symbol="h",
            category="time",
        )
        with self.assertRaises(PermissionDenied):
            archive_unit_of_measure(
                organization=self.other_organization, actor=self.other_owner, unit=unit
            )
        archive_unit_of_measure(
            organization=self.organization, actor=self.owner, unit=unit
        )
        self.assertFalse(
            get_organization_units(
                user=self.owner, organization=self.organization
            ).exists()
        )


class MaterialMasterServiceTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(
            username="material-owner", password="test-password"
        )
        self.member = User.objects.create_user(
            username="material-member", password="test-password"
        )
        self.other_owner = User.objects.create_user(
            username="material-other", password="test-password"
        )
        self.organization = Organization.objects.create(
            name="Material Company", slug="material-company"
        )
        self.other_organization = Organization.objects.create(
            name="Other Material Company", slug="other-material-company"
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
        self.unit = create_unit_of_measure(
            organization=self.organization,
            actor=self.owner,
            code="KG",
            name="Kilogram",
            symbol="kg",
            category="weight",
            decimal_places=3,
        )

    def test_material_is_scoped_and_requires_same_tenant_category_and_uom(self) -> None:
        category = create_material_category(
            organization=self.organization,
            actor=self.owner,
            code="aggregate",
            name="Aggregate",
        )
        material = create_material(
            organization=self.organization,
            actor=self.owner,
            code="sand-fine",
            name="Fine sand",
            category=category,
            unit_of_measure=self.unit,
            specifications="Washed",
        )
        self.assertEqual(material.code, "SAND-FINE")
        self.assertEqual(material.unit_of_measure, self.unit)
        self.assertTrue(
            get_organization_materials(
                user=self.owner, organization=self.organization, search="sand"
            )
            .filter(pk=material.pk)
            .exists()
        )
        other_unit = create_unit_of_measure(
            organization=self.other_organization,
            actor=self.other_owner,
            code="KG",
            name="Kilogram",
            symbol="kg",
            category="weight",
        )
        with self.assertRaisesMessage(ValueError, "اطلاعات مصالح معتبر نیست"):
            create_material(
                organization=self.organization,
                actor=self.owner,
                code="other",
                name="Other",
                unit_of_measure=other_unit,
            )
        other_material = create_material(
            organization=self.other_organization,
            actor=self.other_owner,
            code="sand-fine",
            name="Fine sand",
            unit_of_measure=other_unit,
        )
        self.assertEqual(other_material.organization, self.other_organization)
        with self.assertRaises(PermissionDenied):
            create_material(
                organization=self.organization,
                actor=self.member,
                code="denied",
                name="Denied",
                unit_of_measure=self.unit,
            )

    def test_archive_dependencies_and_category_cycle_are_rejected(self) -> None:
        parent = create_material_category(
            organization=self.organization, actor=self.owner, code="bulk", name="Bulk"
        )
        child = create_material_category(
            organization=self.organization,
            actor=self.owner,
            code="sand",
            name="Sand",
            parent=parent,
        )
        with self.assertRaisesMessage(ValueError, "نمی‌تواند شامل چرخه باشد"):
            update_material_category(
                organization=self.organization,
                actor=self.owner,
                category=parent,
                code="BULK",
                name="Bulk",
                parent=child,
            )
        material = create_material(
            organization=self.organization,
            actor=self.owner,
            code="sand",
            name="Sand",
            category=child,
            unit_of_measure=self.unit,
        )
        with self.assertRaisesMessage(ValueError, "زیرمجموعه یا مصالح فعال"):
            archive_material_category(
                organization=self.organization, actor=self.owner, category=child
            )
        with self.assertRaisesMessage(ValueError, "مورد استفاده مصالح فعال"):
            archive_unit_of_measure(
                organization=self.organization, actor=self.owner, unit=self.unit
            )
        archive_material(
            organization=self.organization, actor=self.owner, material=material
        )
        archive_material_category(
            organization=self.organization, actor=self.owner, category=child
        )
        archive_material_category(
            organization=self.organization, actor=self.owner, category=parent
        )
        archive_unit_of_measure(
            organization=self.organization, actor=self.owner, unit=self.unit
        )
        self.assertFalse(
            Material.objects.filter(pk=material.pk, is_active=True).exists()
        )
        self.assertFalse(
            MaterialCategory.objects.filter(pk=child.pk, is_active=True).exists()
        )
