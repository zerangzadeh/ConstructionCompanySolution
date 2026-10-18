"""CEP-031: secondary governance UI preserves existing source authority."""

from uuid import uuid4

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.materials import services
from apps.materials.models import MaterialTechnicalApprovalStatus
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermission,
    MembershipScopeGrant,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    OrganizationSettings,
)
from apps.organizations.models import (
    BusinessPermissionCode as P,
)


class MaterialsGovernanceSurfaceTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="CEP031", slug="cep031")
        OrganizationSettings.objects.create(organization=self.organization, timezone="Asia/Tehran")
        self.other = Organization.objects.create(name="Other", slug="cep031-other")
        self.steward = self.member("steward", {P.MATERIALS_VIEW, P.MATERIALS_CREATE, P.MATERIAL_CATEGORIES_CREATE, P.UNITS_CREATE, P.MATERIALS_STEWARD, P.MATERIAL_RELATIONSHIPS_MANAGE, P.MATERIAL_TECHNICAL_SUBMIT, P.MATERIAL_TECHNICAL_REVIEW, P.MATERIAL_TECHNICAL_APPROVE, P.MATERIAL_ATTRIBUTE_DEFINITIONS_MANAGE, P.MATERIAL_ATTRIBUTES_APPLY, P.UOM_CONVERSIONS_MANAGE, P.UOM_ROUNDING_MANAGE})
        self.reader = self.member("reader", {P.MATERIALS_VIEW})
        self.category = services.create_material_category(organization=self.organization, actor=self.steward, code="STEEL", name="Steel")
        self.unit = services.create_unit_of_measure(organization=self.organization, actor=self.steward, code="KG", name="Kilogram", symbol="kg", category="weight")
        self.material = services.create_material(organization=self.organization, actor=self.steward, code="A", name="Steel A", category=self.category, unit_of_measure=self.unit)
        self.candidate = services.create_material(organization=self.organization, actor=self.steward, code="B", name="Steel B", category=self.category, unit_of_measure=self.unit)
        self.login(self.steward)

    def member(self, name, codes):
        user = User.objects.create_user(username="cep031-" + name)
        role = OrganizationRole.objects.create(code="cep031-" + name, name=name)
        role.permissions.set(BusinessPermission.objects.filter(code__in=codes))
        membership = OrganizationMembership.objects.create(organization=self.organization, user=user, role_definition=role, status="active")
        MembershipScopeGrant.objects.create(organization=self.organization, membership=membership, scope_type=AuthorizationScopeType.ORGANIZATION, reason="CEP-031")
        return user

    def login(self, user):
        self.client.force_login(user)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()

    def url(self, action=None):
        if action:
            return reverse("materials:governance_action", args=[action])
        return reverse("materials:governance")

    def post(self, action, data):
        return self.client.post(self.url(action), {"material": self.material.pk, **{f"{action}-{key}": value for key, value in data.items()}})

    def test_reader_cannot_enter_governance_or_learn_material_state(self):
        self.login(self.reader)
        response = self.client.get(self.url(), {"material": self.material.pk})
        self.assertEqual(response.status_code, 403)
        self.assertNotContains(response, self.material.name, status_code=403)

    def test_steward_can_view_tenant_local_history_and_create_alias_relationship(self):
        response = self.client.get(self.url(), {"material": self.material.pk})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "حاکمیت مصالح")
        response = self.post("alias", {"code": "ALT-A", "label": "", "reason": "legacy code"})
        self.assertEqual(response.status_code, 302)
        response = self.post("relationship", {"candidate": self.candidate.pk, "relationship_type": "equivalent", "reason": "approved technical comparison"})
        self.assertEqual(response.status_code, 302)
        response = self.client.get(self.url(), {"material": self.material.pk})
        self.assertContains(response, "ALT-A")
        self.assertContains(response, self.candidate.name)

    def test_cross_tenant_target_and_invalid_transition_are_denied_without_leakage(self):
        foreign_id = uuid4()
        response = self.post("relationship", {"candidate": foreign_id, "relationship_type": "equivalent", "reason": "attack"})
        self.assertEqual(response.status_code, 400)
        self.assertNotContains(response, str(foreign_id), status_code=400)
        created = services.create_material_technical_revision(organization=self.organization, actor=self.steward, material=self.material)
        response = self.post("transition_decide", {"approval": created.pk, "reason": "should fail"})
        self.assertEqual(response.status_code, 400)
        created.refresh_from_db()
        self.assertEqual(created.status, MaterialTechnicalApprovalStatus.DRAFT)

    def test_versioned_forms_render_jalali_inputs_and_errors_are_explicit(self):
        response = self.post("conversion", {"unit": self.unit.pk, "factor_to_base": "1", "effective_from": "1405/07/26 10:00", "source_reference": "certificate"})
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "ثبت نسخه تبدیل", status_code=400)
        response = self.client.get(self.url(), {"material": self.material.pk})
        self.assertContains(response, "data-jalali-date")
