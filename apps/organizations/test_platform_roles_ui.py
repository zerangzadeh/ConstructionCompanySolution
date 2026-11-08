"""UI projections must preserve the existing role/tenant mutation boundary."""

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.organizations.access_services import assign_platform_admin
from apps.organizations.models import (
    BusinessPermission,
    BusinessPermissionCode,
    MembershipRole,
    MembershipRoleAssignment,
    MembershipScopeGrant,
    OrganizationMembership,
    OrganizationRole,
)
from apps.organizations.services import create_organization_with_owner


@override_settings(PRODUCT_SURFACE_PROFILE="MVP")
class PlatformRoleWorkspaceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        root = User.objects.create_superuser(username="roles-ui-root")
        cls.admin = User.objects.create_user(username="roles-ui-admin")
        assign_platform_admin(
            actor=root, approver=root, target=cls.admin, reason="UI test bootstrap"
        )
        cls.owner = User.objects.create_user(username="roles-ui-owner")
        cls.company = create_organization_with_owner(
            owner=cls.owner, name="UI target", slug="roles-ui-target"
        )
        cls.other = create_organization_with_owner(
            owner=cls.owner, name="Other UI target", slug="roles-ui-other"
        )
        cls.permission = BusinessPermission.objects.get(
            code=BusinessPermissionCode.PROJECTS_VIEW
        )
        cls.role = OrganizationRole.objects.create(code="a-ui-custom", name="A UI role")
        cls.role.permissions.add(cls.permission)
        cls.tenant_role = OrganizationRole.objects.create(
            organization=cls.company, code="ui-tenant", name="Tenant UI role"
        )
        cls.tenant_role.permissions.add(cls.permission)
        cls.url = reverse("organizations:platform_role_catalog")

    def setUp(self):
        self.client.force_login(self.admin)

    def payload(self, role=None, **changes):
        role = role or self.role
        result = {
            "role_id": role.pk,
            "name": role.name,
            "code": role.code,
            "description": role.description,
            "reason": "UI verified change",
            "permissions": list(role.permissions.values_list("pk", flat=True)),
            "expected_updated_at": role.updated_at.isoformat(),
            "action": "save",
        }
        result.update(changes)
        return result

    def test_default_is_bounded_read_view_and_registry_choices_are_exact(self):
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, "organizations/platform_roles.html")
        self.assertLessEqual(len(response.context["roles"]), 10)
        self.assertFalse(response.context["editing"])
        self.assertNotContains(response, 'name="action" value="save"')
        self.assertNotContains(response, '<details class="role-permission-group" open')
        groups = response.context["permission_groups"]
        ids = [item["permission"].pk for group in groups for item in group["items"]]
        expected = list(response.context["form"].fields["permissions"].queryset)
        self.assertCountEqual(ids, [item.pk for item in expected])
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(
            any(group["label"] == "پروژه‌ها و کنترل پروژه" for group in groups)
        )

    def test_search_filter_pagination_and_explicit_creation(self):
        response = self.client.get(
            self.url, {"q": "A UI", "kind": "custom", "status": "active"}
        )
        self.assertEqual(list(response.context["roles"]), [self.role])
        self.assertEqual(response.context["selected_role"], self.role)
        response = self.client.get(self.url, {"page": 2})
        self.assertEqual(response.context["page_obj"].number, 2)
        response = self.client.get(self.url, {"new": 1})
        self.assertTrue(response.context["editing"])
        self.assertIsNone(response.context["selected_role"])
        self.assertContains(response, 'name="action" value="save"')

    def test_tenant_search_keeps_exact_scope_and_forged_target_fails(self):
        response = self.client.get(
            self.url, {"organization": self.company.pk, "q": "UI"}
        )
        self.assertEqual(list(response.context["roles"]), [self.tenant_role])
        self.assertEqual(
            response.context["tenant_selector"].initial["organization"], self.company
        )
        self.assertEqual(
            self.client.get(
                self.url, {"organization": self.other.pk, "edit": self.tenant_role.pk}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                self.url + f"?organization={self.other.pk}",
                self.payload(self.tenant_role, catalog_organization=self.company.pk),
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(self.url, {"section": "tenant"})
            .context["page_obj"]
            .paginator.count,
            0,
        )

    def test_authorized_save_and_reloaded_permissions_use_existing_service(self):
        response = self.client.post(self.url, self.payload(name="Saved UI role"))
        self.assertEqual(response.status_code, 302)
        self.role.refresh_from_db()
        self.assertEqual(self.role.name, "Saved UI role")
        response = self.client.get(self.url, {"edit": self.role.pk})
        self.assertEqual(response.context["permission_selected"], 1)
        self.assertEqual(set(self.role.permissions.all()), {self.permission})

    def test_validation_and_stale_version_preserve_submission_and_database(self):
        response = self.client.post(self.url, self.payload(name="Attempted", reason=""))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].has_error("reason"))
        self.assertTrue(response.context["editing"])
        self.assertEqual(response.context["form"]["name"].value(), "Attempted")
        response = self.client.post(
            self.url,
            self.payload(name="Stale", expected_updated_at=timezone.now().isoformat()),
        )
        self.assertContains(response, "نقش تغییر کرده است")
        self.role.refresh_from_db()
        self.assertEqual(self.role.name, "A UI role")

    def test_protected_permissions_locked_in_ui_and_forged_post_rejected(self):
        role = OrganizationRole.objects.get(
            code=MembershipRole.TENANT_OWNER, organization__isnull=True
        )
        response = self.client.get(self.url, {"edit": role.pk, "mode": "edit"})
        self.assertTrue(response.context["permissions_locked"])
        self.assertContains(response, "حفاظت‌شده")
        previous = set(role.permissions.values_list("pk", flat=True))
        response = self.client.post(
            self.url, self.payload(role, permissions=[self.permission.pk])
        )
        self.assertContains(response, "قابل تغییر نیستند")
        self.assertEqual(set(role.permissions.values_list("pk", flat=True)), previous)

    def test_retired_assignments_and_archived_roles_are_visible_read_only(self):
        self.permission.is_active = False
        self.permission.save(update_fields=["is_active"])
        response = self.client.get(self.url, {"edit": self.role.pk, "mode": "edit"})
        self.assertFalse(response.context["can_edit_role"])
        self.assertContains(response, "غیرفعال / غیرقابل تخصیص")
        self.assertNotContains(response, 'name="action" value="save"')
        self.assertEqual(response.context["permission_selected"], 1)
        self.role.is_active = False
        self.role.save(update_fields=["is_active"])
        response = self.client.get(self.url, {"edit": self.role.pk})
        self.assertFalse(response.context["can_edit_role"])

    def test_platform_role_does_not_grant_tenant_delegation_or_owner_access(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, self.payload()).status_code, 403)
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("organizations:platform_member_roles"),
            {"organization": self.company.pk},
        )
        self.assertIsNone(response.context["page_obj"])
        self.assertContains(response, "به عضویت و مجوزهای لازم")

    def test_member_inspector_sees_history_without_mutation_controls(self):
        role = OrganizationRole.objects.create(code="ui-inspector", name="UI inspector")
        role.permissions.set(
            BusinessPermission.objects.filter(
                code__in=[
                    BusinessPermissionCode.MEMBERSHIP_VIEW,
                    BusinessPermissionCode.AUTHORIZATION_ROLES_VIEW,
                ]
            )
        )
        inspector = OrganizationMembership.objects.create(
            organization=self.company,
            user=self.admin,
            status="active",
            role=MembershipRole.MEMBER,
            role_definition=role,
        )
        MembershipRoleAssignment.objects.create(
            organization=self.company,
            membership=inspector,
            role=role,
            reason="Read-only fixture",
            source="test",
        )
        MembershipScopeGrant.objects.create(
            organization=self.company,
            membership=inspector,
            scope_type="organization",
            reason="Read-only fixture",
            source="test",
        )
        member = self.company.memberships.get(user=self.owner)
        response = self.client.get(
            reverse(
                "organizations:platform_member_authorization",
                args=[self.company.pk, member.pk],
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["can_assign_roles"])
        self.assertFalse(response.context["can_revoke_roles"])
        self.assertNotContains(response, 'value="assign_role"')
        self.assertNotContains(response, 'value="revoke_role"')
        self.assertContains(response, "تاریخچه نقش‌ها")
