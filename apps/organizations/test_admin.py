from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase

from apps.accounts.models import User
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
    Organization,
    OrganizationRole,
    OrganizationSettings,
)


class OrganizationAdminTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_superuser(
            username="admin-user",
            email="admin@example.com",
            password="test-password",
        )
        self.model_admin = OrganizationAdmin(Organization, admin.site)

    def test_admin_cannot_add_organization(self) -> None:
        request = RequestFactory().get("/admin/organizations/organization/")
        request.user = self.user

        self.assertFalse(self.model_admin.has_add_permission(request))

    def test_admin_creation_path_is_hard_disabled(self) -> None:
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

        with self.assertRaisesMessage(PermissionDenied, "Django Admin غیرفعال است"):
            self.model_admin.save_model(request, organization, form, change=False)

        self.assertFalse(
            Organization.objects.filter(slug="test-construction-company").exists()
        )

    def test_settings_are_not_registered_as_a_separate_admin_section(self) -> None:
        self.assertNotIn(OrganizationSettings, admin.site._registry)

    def test_admin_change_path_is_hard_disabled(self) -> None:
        organization = Organization.objects.create(
            name="شرکت اولیه",
            slug="initial-company",
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

        with self.assertRaisesMessage(PermissionDenied, "Django Admin غیرفعال است"):
            self.model_admin.save_model(
                request,
                changed_organization,
                form,
                change=True,
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

    def test_global_role_catalog_is_read_only(self) -> None:
        admin_request = self.factory.get("/admin/organizations/organizationrole/")
        admin_request.user = self.admin_user
        staff_request = self.factory.get("/admin/organizations/organizationrole/")
        staff_request.user = self.staff_user

        self.assertFalse(self.model_admin.has_add_permission(admin_request))
        self.assertFalse(self.model_admin.has_change_permission(admin_request))
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

    def test_admin_cannot_delete_custom_role(self) -> None:
        role = OrganizationRole.objects.create(
            code="unused_custom_role",
            name="نقش سفارشی بلااستفاده",
            created_by=self.admin_user,
            updated_by=self.admin_user,
        )
        request = self.factory.post("/")
        request.user = self.admin_user

        self.assertFalse(self.model_admin.has_delete_permission(request, role))
        with self.assertRaisesMessage(PermissionDenied, "migration قابل تغییر است"):
            self.model_admin.delete_model(request, role)

        self.assertTrue(OrganizationRole.objects.filter(pk=role.pk).exists())

    def test_admin_cannot_create_global_role(self) -> None:
        role = OrganizationRole(
            code="contract_reviewer",
            name="بازبین قرارداد",
            description="نقش سراسری تعریف‌شده توسط ادمین سامانه",
        )
        request = self.factory.post("/")
        request.user = self.admin_user

        with self.assertRaisesMessage(PermissionDenied, "migration قابل تغییر است"):
            self.model_admin.save_model(request, role, form=None, change=False)

        self.assertFalse(OrganizationRole.objects.filter(pk=role.pk).exists())

    def test_system_role_code_and_flags_are_read_only(self) -> None:
        role = OrganizationRole.objects.get(code=MembershipRole.COMPANY_OWNER)
        request = self.factory.get("/")
        request.user = self.admin_user

        readonly = self.model_admin.get_readonly_fields(request, role)

        self.assertIn("code", readonly)
        self.assertIn("is_system", readonly)
        self.assertIn("is_owner", readonly)
