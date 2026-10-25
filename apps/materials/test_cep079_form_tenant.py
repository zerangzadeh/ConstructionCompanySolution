from django.test import TestCase

from apps.materials.forms import MaterialForm
from apps.materials.models import MaterialCategory, UnitOfMeasure
from apps.organizations.models import Organization


class MaterialFormTenantTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Form", slug="cep079-form")
        self.foreign = Organization.objects.create(
            name="Foreign", slug="cep079-foreign"
        )
        self.unit = UnitOfMeasure.objects.create(
            organization=self.organization,
            code="EA",
            name="Each",
            symbol="ea",
            category="count",
        )
        self.foreign_unit = UnitOfMeasure.objects.create(
            organization=self.foreign,
            code="EA",
            name="Other Each",
            symbol="ea",
            category="count",
        )

    def form(self, **overrides):
        return MaterialForm(
            {
                "code": "CEP079-FORM",
                "name": "Synthetic",
                "unit_of_measure": self.unit.pk,
                **overrides,
            },
            organization_id=self.organization.pk,
        )

    def test_new_material_validates_with_server_tenant_and_local_unit(self):
        form = self.form()
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.instance.organization_id, self.organization.pk)

    def test_foreign_unit_and_category_are_rejected(self):
        category = MaterialCategory.objects.create(
            organization=self.foreign,
            code="CAT",
            name="Foreign category",
        )
        for overrides, field in (
            ({"unit_of_measure": self.foreign_unit.pk}, "unit_of_measure"),
            ({"category": category.pk}, "category"),
        ):
            with self.subTest(field=field):
                form = self.form(**overrides)
                self.assertFalse(form.is_valid())
                self.assertIn(field, form.errors)
