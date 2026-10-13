"""CEP-001 tenant and company/project/site security regression evidence."""

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.organizations.authorization import (
    get_active_membership,
    has_business_permission,
    membership_has_scope,
    scope_queryset,
)
from apps.organizations.forms import MembershipScopeGrantForm
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermissionCode,
    MembershipScopeGrant,
    OrganizationMembership,
    OrganizationRole,
)
from apps.organizations.services import (
    ACTIVE_ORGANIZATION_SESSION_KEY,
    create_organization_with_owner,
)
from apps.parties.models import BusinessParty
from apps.projects.models import Project, ProjectSite
from apps.projects.services import get_organization_projects, get_organization_sites


class CEP001SecurityTests(TestCase):
    def setUp(self) -> None:
        self.actor = User.objects.create_superuser(
            username="cep001-admin",
            email="admin@example.test",
            password="test-password",
        )
        self.other_owner = User.objects.create_user(
            username="cep001-other", password="test-password"
        )
        self.organization = create_organization_with_owner(
            owner=self.actor, name="Approved Company", slug="cep001-approved"
        )
        self.other_organization = create_organization_with_owner(
            owner=self.other_owner, name="Protected Company", slug="cep001-protected"
        )
        self.membership = OrganizationMembership.objects.get(
            organization=self.organization, user=self.actor
        )
        self.project = Project.objects.create(
            organization=self.organization, code="APPROVED", name="Approved Project"
        )
        self.sibling = Project.objects.create(
            organization=self.organization, code="SIBLING", name="Protected Sibling"
        )
        self.other_project = Project.objects.create(
            organization=self.other_organization,
            code="OTHER",
            name="Protected Other Tenant",
        )
        self.site = ProjectSite.objects.create(
            organization=self.organization,
            project=self.project,
            code="APPROVED-SITE",
            name="Approved Site",
        )
        self.other_site = ProjectSite.objects.create(
            organization=self.other_organization,
            project=self.other_project,
            code="OTHER-SITE",
            name="Protected Other Site",
        )
        self.membership.scope_grants.all().delete()
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=self.membership,
            scope_type=AuthorizationScopeType.PROJECT,
            project=self.project,
            reason="CEP-001 project-only fixture",
        )
        self.client.force_login(self.actor)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.organization.pk)
        session.save()

    def test_shared_queryset_always_intersects_tenant_and_object_grants(self) -> None:
        scoped = scope_queryset(
            Project.objects.all(), membership=self.membership, project_lookup="pk"
        )
        self.assertEqual(set(scoped), {self.project})
        site_scoped = scope_queryset(
            ProjectSite.objects.all(),
            membership=self.membership,
            project_lookup="project_id",
            site_lookup="pk",
        )
        self.assertEqual(set(site_scoped), {self.site})
        self.assertEqual(
            set(
                get_organization_projects(
                    user=self.actor, organization=self.organization
                )
            ),
            {self.project},
        )
        self.assertEqual(
            set(
                get_organization_sites(user=self.actor, organization=self.organization)
            ),
            {self.site},
        )
        form = MembershipScopeGrantForm(
            organization=self.organization,
            actor_membership=self.membership,
            target_membership=self.membership,
        )
        self.assertEqual(set(form.fields["project"].queryset), {self.project})
        self.assertEqual(set(form.fields["site"].queryset), {self.site})
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=self.membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="CEP-001 organization grant",
        )
        self.assertEqual(
            set(
                scope_queryset(
                    Project.objects.all(),
                    membership=self.membership,
                    project_lookup="pk",
                )
            ),
            {self.project, self.sibling},
        )

    def test_admin_list_search_and_direct_details_enforce_scope(self) -> None:
        project_url = reverse("admin:projects_project_changelist")
        response = self.client.get(project_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Approved Project")
        self.assertNotContains(response, "Protected Sibling")
        self.assertNotContains(response, "Protected Other Tenant")
        allowed_detail = self.client.get(
            reverse("admin:projects_project_change", args=[self.project.pk])
        )
        self.assertEqual(allowed_detail.status_code, 200)
        self.assertContains(allowed_detail, "Approved Project")
        self.assertNotContains(allowed_detail, "Protected Other Tenant")

        response = self.client.get(project_url, {"q": "Protected"})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Protected Sibling")
        self.assertNotContains(response, "Protected Other Tenant")

        site_response = self.client.get(
            reverse("admin:projects_projectsite_changelist")
        )
        self.assertEqual(site_response.status_code, 200)
        self.assertContains(site_response, "Approved Site")
        self.assertNotContains(site_response, "Protected Other Site")

        for project in (self.sibling, self.other_project):
            response = self.client.get(
                reverse("admin:projects_project_change", args=[project.pk])
            )
            self.assertNotEqual(response.status_code, 200)
            self.assertNotIn(project.name.encode(), response.content)
        response = self.client.get(
            reverse("admin:projects_projectsite_change", args=[self.other_site.pk])
        )
        self.assertNotEqual(response.status_code, 200)
        self.assertNotIn(self.other_site.name.encode(), response.content)

        response = self.client.get(
            reverse("projects:detail", args=[self.other_project.pk])
        )
        self.assertEqual(response.status_code, 403)
        self.assertNotIn(self.other_project.name.encode(), response.content)

    def test_company_context_and_platform_superuser_do_not_grant_tenant_access(
        self,
    ) -> None:
        company_admin = admin.site._registry[type(self.organization)]
        project_admin = admin.site._registry[Project]
        request = RequestFactory().get("/admin/")
        request.user = self.actor
        request.organization = self.organization
        self.assertFalse(company_admin.has_view_permission(request, self.organization))
        self.assertFalse(company_admin.has_module_permission(request))
        self.assertFalse(project_admin.has_view_permission(request, self.sibling))
        self.assertFalse(project_admin.has_view_permission(request, self.other_project))
        self.assertNotIn("organization", project_admin.get_list_filter(request))

        request.organization = self.other_organization
        self.assertFalse(project_admin.has_module_permission(request))
        self.assertFalse(project_admin.get_queryset(request).exists())
        self.assertFalse(company_admin.get_queryset(request).exists())

        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=self.membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="CEP-001 company inspection fixture",
        )
        request.organization = self.organization
        self.assertTrue(company_admin.has_view_permission(request, self.organization))
        self.assertEqual(list(company_admin.get_queryset(request)), [self.organization])

        technical_user = User.objects.create_superuser(
            username="cep001-technical",
            email="technical@example.test",
            password="test-password",
        )
        request.user = technical_user
        request.organization = self.organization
        self.assertFalse(project_admin.has_module_permission(request))
        self.assertFalse(project_admin.get_queryset(request).exists())

    def test_unmapped_tenant_admin_fails_closed(self) -> None:
        request = RequestFactory().get("/admin/")
        request.user = self.actor
        request.organization = self.organization
        party_admin = admin.site._registry[BusinessParty]
        self.assertFalse(party_admin.has_module_permission(request))
        self.assertFalse(party_admin.has_view_permission(request))
        self.assertFalse(party_admin.get_queryset(request).exists())

    def test_legacy_membership_without_grant_does_not_open_admin(self) -> None:
        self.membership.scope_grants.all().delete()
        self.membership.authorization_migrated_at = None
        self.membership.save(update_fields=["authorization_migrated_at"])
        fresh_membership = get_active_membership(
            user=self.actor, organization=self.organization
        )
        self.assertFalse(membership_has_scope(fresh_membership, allow_any_scope=True))
        self.assertFalse(membership_has_scope(fresh_membership, project=self.project))
        self.assertFalse(
            has_business_permission(
                user=self.actor,
                organization=self.organization,
                permission=BusinessPermissionCode.PROJECTS_VIEW,
                allow_any_scope=True,
            )
        )
        self.assertFalse(
            scope_queryset(
                Project.objects.all(),
                membership=fresh_membership,
                project_lookup="pk",
            ).exists()
        )
        with self.assertRaises(PermissionDenied):
            get_organization_projects(user=self.actor, organization=self.organization)
        request = RequestFactory().get("/admin/")
        request.user = self.actor
        request.organization = self.organization
        project_admin = admin.site._registry[Project]
        self.assertFalse(project_admin.has_module_permission(request))
        self.assertFalse(project_admin.get_queryset(request).exists())
        response = self.client.get(reverse("projects:detail", args=[self.project.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertNotIn(self.project.name.encode(), response.content)

    def test_no_applicable_grant_denies_even_with_business_permission(self) -> None:
        self.membership.scope_grants.update(revoked_at=timezone.now())
        self.assertFalse(
            has_business_permission(
                user=self.actor,
                organization=self.organization,
                permission=BusinessPermissionCode.PROJECTS_VIEW,
                project=self.project,
            )
        )
        self.assertFalse(
            scope_queryset(
                Project.objects.all(),
                membership=self.membership,
                project_lookup="pk",
            ).exists()
        )

    def test_wrong_tenant_grant_cannot_authorize_membership(self) -> None:
        self.membership.scope_grants.all().delete()
        MembershipScopeGrant.objects.create(
            organization=self.other_organization,
            membership=self.membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="Inconsistent cross-tenant row must fail closed",
        )
        fresh_membership = get_active_membership(
            user=self.actor, organization=self.organization
        )
        self.assertFalse(membership_has_scope(fresh_membership, allow_any_scope=True))
        self.assertFalse(
            scope_queryset(
                Project.objects.all(),
                membership=fresh_membership,
                project_lookup="pk",
            ).exists()
        )
        self.assertFalse(
            has_business_permission(
                user=self.actor,
                organization=self.organization,
                permission=BusinessPermissionCode.PROJECTS_VIEW,
                project=self.project,
            )
        )

    def test_scope_grant_without_business_permission_denies_service_and_admin(
        self,
    ) -> None:
        self.membership.role_assignments.update(revoked_at=timezone.now())
        self.assertFalse(
            has_business_permission(
                user=self.actor,
                organization=self.organization,
                permission=BusinessPermissionCode.PROJECTS_VIEW,
                project=self.project,
            )
        )
        with self.assertRaises(PermissionDenied):
            get_organization_projects(user=self.actor, organization=self.organization)
        request = RequestFactory().get("/admin/")
        request.user = self.actor
        request.organization = self.organization
        project_admin = admin.site._registry[Project]
        self.assertFalse(project_admin.has_module_permission(request))
        self.assertFalse(project_admin.get_queryset(request).exists())

    def test_explicit_organization_grant_enables_tenant_only(self) -> None:
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=self.membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="CEP-001 explicit broad grant",
        )
        self.assertEqual(
            set(
                get_organization_projects(
                    user=self.actor, organization=self.organization
                )
            ),
            {self.project, self.sibling},
        )
        self.assertEqual(
            set(
                scope_queryset(
                    Project.objects.all(),
                    membership=self.membership,
                    project_lookup="pk",
                )
            ),
            {self.project, self.sibling},
        )
        request = RequestFactory().get("/admin/")
        request.user = self.actor
        request.organization = self.organization
        project_admin = admin.site._registry[Project]
        self.assertEqual(
            set(project_admin.get_queryset(request)), {self.project, self.sibling}
        )
        self.assertFalse(project_admin.has_view_permission(request, self.other_project))

    def test_platform_admin_catalog_excludes_tenant_roles_and_audit(self) -> None:
        tenant_role = OrganizationRole.objects.create(
            organization=self.organization,
            code="cep001-tenant-role",
            name="Protected Tenant Role",
        )
        tenant_event = AuditEvent.objects.create(
            organization=self.organization,
            actor=self.actor,
            action=AuditAction.PROJECT_CREATED,
            entity_type="project",
            entity_id=str(self.project.pk),
            metadata={"secret": "protected"},
        )
        platform_event = AuditEvent.objects.create(
            actor=self.actor,
            action=AuditAction.PROJECT_CREATED,
            entity_type="platform-check",
        )
        request = RequestFactory().get("/admin/")
        request.user = self.actor
        request.organization = self.organization
        role_admin = admin.site._registry[OrganizationRole]
        audit_admin = admin.site._registry[AuditEvent]
        self.assertFalse(role_admin.has_view_permission(request, tenant_role))
        self.assertNotIn(tenant_role, role_admin.get_queryset(request))
        self.assertFalse(audit_admin.has_view_permission(request, tenant_event))
        self.assertNotIn(tenant_event, audit_admin.get_queryset(request))
        self.assertIn(platform_event, audit_admin.get_queryset(request))
