from django.contrib import admin
from django.test import RequestFactory, TestCase

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.organizations.admin import OrganizationAdmin, OrganizationRoleAdmin
from apps.organizations.forms import OrganizationForm
from apps.organizations.models import (
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationRole,
)


class OrganizationAdminTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_superuser(
            username="admin-user",
            email="admin@example.com",
            password="test-password",
        )
        self.model_admin = OrganizationAdmin(Organization, admin.site)

    def test_admin_with_permission_can_add_organization(self) -> None:
        request = RequestFactory().get("/admin/organizations/organization/")
        request.user = self.user

        self.assertTrue(self.model_admin.has_add_permission(request))

    def test_admin_creation_uses_organization_creation_service(self) -> None:
        form = OrganizationForm(
            data={
                "name": "شرکت سازه آزمون",
                "legal_name": "شرکت سازه آزمون ایرانیان",
                "slug": "test-construction-company",
                "timezone": "Asia/Tehran",
                "currency": "IRR",
            }
        )
        self.assertTrue(form.is_valid())
        request = RequestFactory().post("/admin/organizations/organization/add/")
        request.user = self.user
        organization = form.save(commit=False)

        self.model_admin.save_model(request, organization, form, change=False)

        membership = OrganizationMembership.objects.get(
            organization=organization,
            user=self.user,
        )
        self.assertEqual(membership.role, MembershipRole.COMPANY_OWNER)
        self.assertEqual(membership.status, MembershipStatus.ACTIVE)
        self.assertEqual(organization.settings.timezone, "Asia/Tehran")


class OrganizationRoleAdminTests(TestCase):
    def setUp(self) -> None:
        self.admin_user = User.objects.create_superuser(
            username="role-admin",
            email="role-admin@example.com",
        )
        self.staff_user = User.objects.create_user(
            username="ordinary-staff",
            is_staff=True,
        )
        self.model_admin = OrganizationRoleAdmin(OrganizationRole, admin.site)
        self.factory = RequestFactory()

    def test_only_system_admin_can_manage_global_roles(self) -> None:
        admin_request = self.factory.get("/admin/organizations/organizationrole/")
        admin_request.user = self.admin_user
        staff_request = self.factory.get("/admin/organizations/organizationrole/")
        staff_request.user = self.staff_user

        self.assertTrue(self.model_admin.has_add_permission(admin_request))
        self.assertTrue(self.model_admin.has_change_permission(admin_request))
        self.assertFalse(self.model_admin.has_add_permission(staff_request))
        self.assertFalse(self.model_admin.has_change_permission(staff_request))

    def test_admin_can_delete_only_unused_custom_role_and_action_is_audited(
        self,
    ) -> None:
        role = OrganizationRole.objects.create(
            code="unused_custom_role",
            name="نقش سفارشی بلااستفاده",
            created_by=self.admin_user,
            updated_by=self.admin_user,
        )
        request = self.factory.post("/")
        request.user = self.admin_user

        self.assertTrue(self.model_admin.has_delete_permission(request, role))
        self.model_admin.delete_model(request, role)

        self.assertFalse(OrganizationRole.objects.filter(pk=role.pk).exists())
        event = AuditEvent.objects.get(action=AuditAction.ROLE_DELETED)
        self.assertEqual(event.actor, self.admin_user)
        self.assertEqual(event.metadata["code"], "unused_custom_role")

    def test_admin_can_create_global_role_and_creation_is_audited(self) -> None:
        role = OrganizationRole(
            code="contract_reviewer",
            name="بازبین قرارداد",
            description="نقش سراسری تعریف‌شده توسط ادمین سامانه",
        )
        request = self.factory.post("/")
        request.user = self.admin_user

        self.model_admin.save_model(request, role, form=None, change=False)

        role.refresh_from_db()
        self.assertEqual(role.created_by, self.admin_user)
        self.assertEqual(role.updated_by, self.admin_user)
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.ROLE_CREATED,
                actor=self.admin_user,
                entity_id=str(role.pk),
            ).exists()
        )

    def test_system_role_code_and_flags_are_read_only(self) -> None:
        role = OrganizationRole.objects.get(code=MembershipRole.COMPANY_OWNER)
        request = self.factory.get("/")
        request.user = self.admin_user

        readonly = self.model_admin.get_readonly_fields(request, role)

        self.assertIn("code", readonly)
        self.assertIn("is_system", readonly)
        self.assertIn("is_owner", readonly)
