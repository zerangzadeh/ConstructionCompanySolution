from django.contrib import admin
from django.test import RequestFactory, TestCase

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.organizations.admin import (
    OrganizationAdmin,
    OrganizationRoleAdmin,
    OrganizationRoleAdminForm,
)
from apps.organizations.forms import OrganizationAdminForm
from apps.organizations.models import (
    BusinessPermission,
    BusinessPermissionCode,
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    OrganizationSettings,
)
from apps.organizations.services import create_organization_with_owner


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
        form = OrganizationAdminForm(
            data={
                "name": "شرکت سازه آزمون",
                "legal_name": "شرکت سازه آزمون ایرانیان",
                "slug": "test-construction-company",
                "settings_timezone": "Asia/Tehran",
                "default_currency": "IRR",
                "language": "fa",
                "fiscal_year_start_month": 1,
                "fiscal_year_start_day": 1,
                "project_code_prefix": "PRJ",
                "contract_code_prefix": "CTR",
                "site_code_prefix": "SITE",
                "document_code_prefix": "DOC",
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

    def test_settings_are_not_registered_as_a_separate_admin_section(self) -> None:
        self.assertNotIn(OrganizationSettings, admin.site._registry)

    def test_admin_change_page_loads_and_saves_company_and_settings(self) -> None:
        organization = create_organization_with_owner(
            owner=self.user,
            name="شرکت اولیه",
            slug="initial-company",
            timezone_name="UTC",
            currency="USD",
        )
        form = OrganizationAdminForm(
            data={
                "name": "شرکت ویرایش‌شده",
                "legal_name": "شرکت ویرایش‌شده ایرانیان",
                "slug": "updated-company",
                "city": "تهران",
                "settings_timezone": "Asia/Tehran",
                "default_currency": "IRR",
                "language": "fa",
                "fiscal_year_start_month": 1,
                "fiscal_year_start_day": 1,
                "project_code_prefix": "SITE",
                "contract_code_prefix": "CON",
                "site_code_prefix": "WORK",
                "document_code_prefix": "FILE",
            },
            instance=organization,
        )
        self.assertTrue(form.is_valid(), form.errors)
        request = RequestFactory().post(
            f"/admin/organizations/organization/{organization.pk}/change/"
        )
        request.user = self.user
        changed_organization = form.save(commit=False)

        self.model_admin.save_model(
            request,
            changed_organization,
            form,
            change=True,
        )

        organization.refresh_from_db()
        self.assertEqual(organization.name, "شرکت ویرایش‌شده")
        self.assertEqual(organization.city, "تهران")
        self.assertEqual(organization.timezone, "Asia/Tehran")
        self.assertEqual(organization.settings.currency, "IRR")
        self.assertEqual(organization.settings.project_code_prefix, "SITE")
        self.assertEqual(organization.settings.site_code_prefix, "WORK")
        self.assertEqual(organization.settings.document_code_prefix, "FILE")
        self.assertTrue(
            AuditEvent.objects.filter(
                organization=organization,
                actor=self.user,
                action=AuditAction.ORGANIZATION_SETTINGS_UPDATED,
            ).exists()
        )


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

    def test_role_form_displays_searchable_grouped_permission_catalog(self) -> None:
        permission = BusinessPermission.objects.get(
            code=BusinessPermissionCode.PROJECTS_CREATE
        )
        field = OrganizationRoleAdminForm().fields["permissions"]

        self.assertEqual(
            field.label_from_instance(permission),
            "پروژه‌ها | ایجاد پروژه | projects.create",
        )
        self.assertGreaterEqual(field.queryset.count(), 100)

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
