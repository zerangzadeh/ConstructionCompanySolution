from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.materials.models import Material, UnitCategory, UnitOfMeasure
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermission,
    BusinessPermissionCode,
    MembershipScopeGrant,
    MembershipStatus,
    OrganizationMembership,
    OrganizationRole,
)
from apps.organizations.services import (
    create_organization_with_owner,
    set_active_organization,
)
from apps.projects.models import Project


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class Cep019GlobalSearchTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="cep019-owner")
        self.organization = create_organization_with_owner(
            owner=self.owner, name="CEP019", slug="cep019"
        )
        self.other_owner = User.objects.create_user(username="cep019-other")
        self.other_organization = create_organization_with_owner(
            owner=self.other_owner, name="CEP019 Other", slug="cep019-other"
        )
        self.project = Project.objects.create(
            organization=self.organization,
            code="SEARCH-OWN",
            name="پروژه جستجوی مجاز",
        )
        self.other_project = Project.objects.create(
            organization=self.other_organization,
            code="SEARCH-OTHER",
            name="پروژه خارج از سازمان",
        )
        unit = UnitOfMeasure.objects.create(
            organization=self.organization,
            code="EA",
            name="عدد",
            symbol="ea",
            category=UnitCategory.COUNT,
        )
        self.material = Material.objects.create(
            organization=self.organization,
            code="SEARCH-MAT",
            name="مصالح جستجوی مجاز",
            unit_of_measure=unit,
        )

    def _login(self, user: User, organization) -> None:
        self.client.force_login(user)
        set_active_organization(self.client.session, organization)
        self.client.session.save()

    def _scoped_viewer(self) -> User:
        user = User.objects.create_user(username="cep019-viewer")
        for code in (BusinessPermissionCode.PROJECTS_VIEW,):
            BusinessPermission.objects.update_or_create(
                code=code,
                defaults={
                    "name": str(code),
                    "description": str(code),
                    "is_active": True,
                },
            )
        role = OrganizationRole.objects.create(
            organization=self.organization,
            code="cep019_viewer",
            name="CEP019 Viewer",
            created_by=self.owner,
        )
        role.permissions.add(
            *BusinessPermission.objects.filter(
                code__in={BusinessPermissionCode.PROJECTS_VIEW}
            )
        )
        membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=user,
            role_definition=role,
            status=MembershipStatus.ACTIVE,
            assigned_by=self.owner,
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type=AuthorizationScopeType.PROJECT,
            project=self.project,
            reason="CEP-019 explicit project scope fixture",
        )
        return user

    def test_search_returns_only_tenant_authorized_safe_family_results(self) -> None:
        self._login(self.owner, self.organization)

        response = self.client.get(reverse("global_search"), {"q": "جستجو"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "پروژه جستجوی مجاز")
        self.assertContains(response, "مصالح جستجوی مجاز")
        self.assertNotContains(response, "پروژه خارج از سازمان")
        self.assertContains(
            response, reverse("projects:detail", args=[self.project.pk])
        )
        self.assertContains(
            response, reverse("materials:material_detail", args=[self.material.pk])
        )
        self.assertEqual(
            {item.family for item in response.context["search"].results},
            {"project", "material"},
        )

    def test_project_scope_and_direct_source_route_are_reenforced(self) -> None:
        viewer = self._scoped_viewer()
        self._login(viewer, self.organization)

        response = self.client.get(reverse("global_search"), {"q": "جستجو"})

        self.assertContains(response, "پروژه جستجوی مجاز")
        self.assertNotContains(response, "مصالح جستجوی مجاز")
        self.assertEqual(
            self.client.get(
                reverse("projects:detail", args=[self.other_project.pk])
            ).status_code,
            403,
        )

    def test_empty_short_and_unauthorized_searches_do_not_leak_existence(self) -> None:
        self._login(self.owner, self.organization)
        empty = self.client.get(reverse("global_search"))
        self.assertEqual(empty.status_code, 200)
        self.assertNotContains(
            empty, reverse("projects:detail", args=[self.project.pk])
        )
        short = self.client.get(reverse("global_search"), {"q": "ا"})
        self.assertContains(short, "دست‌کم دو نویسه")
        self.assertNotContains(
            short, reverse("projects:detail", args=[self.project.pk])
        )

        no_access = User.objects.create_user(username="cep019-no-access")
        role = OrganizationRole.objects.create(
            organization=self.organization,
            code="cep019_no_access",
            name="CEP019 No Access",
            created_by=self.owner,
        )
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=no_access,
            role_definition=role,
            status=MembershipStatus.ACTIVE,
            assigned_by=self.owner,
        )
        self._login(no_access, self.organization)
        denied = self.client.get(reverse("global_search"), {"q": "جستجو"})
        self.assertEqual(denied.status_code, 200)
        self.assertNotContains(denied, "پروژه جستجوی مجاز")
        self.assertNotContains(denied, "مصالح جستجوی مجاز")

    def test_search_requires_authenticated_active_organization_and_is_rtl(self) -> None:
        self.client.logout()
        self.assertEqual(self.client.get(reverse("global_search")).status_code, 302)

        self._login(self.owner, self.organization)
        response = self.client.get(reverse("global_search"), {"q": "جستجو"})
        self.assertContains(response, 'dir="rtl"')
        self.assertContains(response, 'name="q"')
        self.assertEqual(self.client.post(reverse("global_search")).status_code, 405)
