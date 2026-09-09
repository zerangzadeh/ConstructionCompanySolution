from django.contrib import admin
from django.test import RequestFactory, TestCase

from apps.accounts.models import User
from apps.organizations.admin import OrganizationAdmin
from apps.organizations.forms import OrganizationForm
from apps.organizations.models import (
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationMembership,
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
        self.assertEqual(membership.role, MembershipRole.OWNER)
        self.assertEqual(membership.status, MembershipStatus.ACTIVE)
        self.assertEqual(organization.settings.timezone, "Asia/Tehran")
