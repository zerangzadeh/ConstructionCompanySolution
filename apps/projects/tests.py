from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.organizations.models import (
    MembershipRole,
    MembershipStatus,
    Organization,
)
from apps.organizations.services import ACTIVE_ORGANIZATION_SESSION_KEY
from apps.projects.models import ProjectStatus
from apps.projects.services import (
    archive_project,
    create_project,
    create_project_site,
    get_organization_project,
    get_organization_project_sites,
    get_organization_projects,
)


class ProjectServiceTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(
            username="project-owner",
            password="test-password",
        )
        self.other_user = User.objects.create_user(
            username="other-project-user",
            password="test-password",
        )
        self.organization = Organization.objects.create(
            name="Project Company",
            slug="project-company",
            created_by=self.owner,
            updated_by=self.owner,
        )
        self.other_organization = Organization.objects.create(
            name="Other Project Company",
            slug="other-project-company",
            created_by=self.other_user,
            updated_by=self.other_user,
        )
        self.organization.memberships.create(
            user=self.owner,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )

    def test_create_project_scopes_project_and_records_audit(self) -> None:
        project = create_project(
            organization=self.organization,
            actor=self.owner,
            code="P-001",
            name="Downtown Tower",
            start_date=date(2026, 9, 1),
            budget=Decimal("125000.00"),
        )

        self.assertEqual(project.organization, self.organization)
        self.assertEqual(project.budget, Decimal("125000.00"))
        self.assertEqual(project.status, ProjectStatus.PLANNING)
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.PROJECT_CREATED,
                organization=self.organization,
                entity_id=str(project.pk),
            ).exists()
        )

    def test_project_code_is_unique_only_inside_organization(self) -> None:
        create_project(
            organization=self.organization,
            actor=self.owner,
            code="P-001",
            name="First project",
        )
        with self.assertRaises(IntegrityError):
            create_project(
                organization=self.organization,
                actor=self.owner,
                code="P-001",
                name="Duplicate project",
            )

        other_membership = self.other_organization.memberships.create(
            user=self.owner,
            role=MembershipRole.MANAGER,
            status=MembershipStatus.ACTIVE,
        )
        self.assertIsNotNone(other_membership)
        project = create_project(
            organization=self.other_organization,
            actor=self.owner,
            code="P-001",
            name="Other tenant project",
        )
        self.assertEqual(project.organization, self.other_organization)

    def test_project_creation_rejects_cross_tenant_user(self) -> None:
        with self.assertRaises(PermissionDenied):
            create_project(
                organization=self.organization,
                actor=self.other_user,
                code="P-002",
                name="Unauthorized project",
            )

    def test_project_creation_rejects_member_role(self) -> None:
        member = User.objects.create_user(
            username="project-member",
            password="test-password",
        )
        self.organization.memberships.create(
            user=member,
            role=MembershipRole.MEMBER,
            status=MembershipStatus.ACTIVE,
        )

        with self.assertRaisesMessage(
            PermissionDenied,
            "You cannot create projects in this organization.",
        ):
            create_project(
                organization=self.organization,
                actor=member,
                code="P-MEMBER",
                name="Unauthorized member project",
            )

    def test_project_creation_validates_dates_and_budget(self) -> None:
        with self.assertRaisesMessage(
            ValueError,
            "Project end date cannot be before start date.",
        ):
            create_project(
                organization=self.organization,
                actor=self.owner,
                code="P-003",
                name="Invalid dates",
                start_date=date(2026, 10, 1),
                end_date=date(2026, 9, 1),
            )

        with self.assertRaisesMessage(
            ValueError,
            "Project budget cannot be negative.",
        ):
            create_project(
                organization=self.organization,
                actor=self.owner,
                code="P-004",
                name="Invalid budget",
                budget=Decimal("-1.00"),
            )

    def test_project_queryset_excludes_other_organization(self) -> None:
        self.organization.projects.create(
            code="P-005",
            name="Visible project",
            created_by=self.owner,
            updated_by=self.owner,
        )
        self.other_organization.projects.create(
            code="P-005",
            name="Hidden project",
            created_by=self.other_user,
            updated_by=self.other_user,
        )

        projects = get_organization_projects(
            user=self.owner,
            organization=self.organization,
        )

        self.assertEqual(
            list(projects.values_list("name", flat=True)), ["Visible project"]
        )

    def test_project_list_requires_active_organization(self) -> None:
        user_without_membership = User.objects.create_user(
            username="project-user-without-membership",
            password="test-password",
        )
        self.client.force_login(user_without_membership)

        response = self.client.get(reverse("projects:list"))

        self.assertRedirects(response, reverse("organizations:select"))

    def test_project_list_is_tenant_scoped(self) -> None:
        self.organization.projects.create(
            code="P-006",
            name="Visible project",
            created_by=self.owner,
            updated_by=self.owner,
        )
        self.other_organization.projects.create(
            code="P-006",
            name="Hidden project",
            created_by=self.other_user,
            updated_by=self.other_user,
        )
        self.client.force_login(self.owner)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.organization.pk)
        session.save()

        response = self.client.get(reverse("projects:list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Visible project")
        self.assertNotContains(response, "Hidden project")

    def test_project_detail_is_tenant_scoped(self) -> None:
        project = self.organization.projects.create(
            code="P-007",
            name="Detailed project",
            created_by=self.owner,
            updated_by=self.owner,
        )
        self.client.force_login(self.owner)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.organization.pk)
        session.save()

        response = self.client.get(
            reverse("projects:detail", kwargs={"project_id": project.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Detailed project")

    def test_archive_project_soft_deletes_and_records_audit(self) -> None:
        project = create_project(
            organization=self.organization,
            actor=self.owner,
            code="P-008",
            name="Archived project",
        )

        archive_project(
            user=self.owner,
            organization=self.organization,
            project_id=str(project.pk),
        )

        project.refresh_from_db()
        self.assertIsNotNone(project.deleted_at)
        self.assertFalse(
            get_organization_projects(
                user=self.owner,
                organization=self.organization,
            )
            .filter(pk=project.pk)
            .exists()
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.PROJECT_ARCHIVED,
                entity_id=str(project.pk),
            ).exists()
        )

    def test_member_cannot_archive_project(self) -> None:
        member = User.objects.create_user(
            username="archive-member",
            password="test-password",
        )
        self.organization.memberships.create(
            user=member,
            role=MembershipRole.MEMBER,
            status=MembershipStatus.ACTIVE,
        )
        project = self.organization.projects.create(
            code="P-009",
            name="Protected project",
            created_by=self.owner,
            updated_by=self.owner,
        )

        with self.assertRaises(PermissionDenied):
            archive_project(
                user=member,
                organization=self.organization,
                project_id=str(project.pk),
            )

    def test_project_lookup_rejects_other_organization(self) -> None:
        project = self.other_organization.projects.create(
            code="P-010",
            name="Other tenant project",
            created_by=self.other_user,
            updated_by=self.other_user,
        )

        with self.assertRaises(PermissionDenied):
            get_organization_project(
                user=self.owner,
                organization=self.organization,
                project_id=str(project.pk),
            )

    def test_create_project_site_is_tenant_scoped_and_audited(self) -> None:
        project = create_project(
            organization=self.organization,
            actor=self.owner,
            code="P-SITE",
            name="Site project",
        )

        site = create_project_site(
            organization=self.organization,
            project=project,
            actor=self.owner,
            code="SITE-001",
            name="Main worksite",
            address="123 Construction Road",
        )

        self.assertEqual(site.organization, self.organization)
        self.assertEqual(site.project, project)
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.PROJECT_SITE_CREATED,
                organization=self.organization,
                entity_id=str(site.pk),
            ).exists()
        )
        self.assertEqual(
            list(
                get_organization_project_sites(
                    user=self.owner,
                    organization=self.organization,
                    project_id=str(project.pk),
                )
            ),
            [site],
        )

    def test_project_site_rejects_project_from_another_organization(self) -> None:
        other_project = self.other_organization.projects.create(
            code="P-OTHER-SITE",
            name="Other site project",
            created_by=self.other_user,
            updated_by=self.other_user,
        )

        with self.assertRaises(PermissionDenied):
            create_project_site(
                organization=self.organization,
                project=other_project,
                actor=self.owner,
                code="SITE-OTHER",
                name="Unauthorized worksite",
            )
