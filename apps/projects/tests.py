from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.materials.services import create_unit_of_measure
from apps.organizations.models import (
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationStatus,
)
from apps.organizations.services import ACTIVE_ORGANIZATION_SESSION_KEY
from apps.projects.models import ActivityStatus, ProjectPhaseStatus, ProjectStatus
from apps.projects.services import (
    archive_activity,
    archive_project,
    archive_wbs_node,
    create_activity,
    create_project,
    create_project_phase,
    create_project_site,
    create_wbs_node,
    get_organization_project,
    get_organization_project_phases,
    get_organization_project_sites,
    get_organization_projects,
    get_organization_sites,
    get_organization_wbs_nodes,
    transition_activity_status,
    transition_project_phase_status,
    update_wbs_node,
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
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )

    def test_create_project_scopes_project_and_records_audit(self) -> None:
        project = create_project(
            organization=self.organization,
            actor=self.owner,
            code="P-001",
            name="Downtown Tower",
            start_date=date(2026, 9, 1),
            estimated_budget=Decimal("125000.00"),
            actual_budget=Decimal("50000.00"),
        )

        self.assertEqual(project.organization, self.organization)
        self.assertEqual(project.estimated_budget, Decimal("125000.00"))
        self.assertEqual(project.actual_budget, Decimal("50000.00"))
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
            role=MembershipRole.OPERATIONS_MANAGER,
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

    def test_project_creation_rejects_cancelled_organization(self) -> None:
        self.organization.status = OrganizationStatus.CANCELLED
        self.organization.save(update_fields=["status"])

        with self.assertRaisesMessage(
            PermissionDenied,
            "سازمان فعال نیست.",
        ):
            create_project(
                organization=self.organization,
                actor=self.owner,
                code="P-CANCELLED",
                name="Blocked project",
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
            "اجازه ایجاد پروژه در این سازمان را ندارید.",
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
            "تاریخ پایان پروژه نمی‌تواند پیش از تاریخ شروع باشد.",
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
            "بودجه پروژه نمی‌تواند منفی باشد.",
        ):
            create_project(
                organization=self.organization,
                actor=self.owner,
                code="P-004",
                name="Invalid budget",
                estimated_budget=Decimal("-1.00"),
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
        project = self.organization.projects.create(
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
        self.assertContains(
            response,
            reverse("projects:detail", kwargs={"project_id": project.pk}),
        )
        self.assertContains(response, "پروژه جدید")
        self.assertContains(response, reverse("projects:all_site_list"))

    def test_all_site_list_is_tenant_scoped(self) -> None:
        project = self.organization.projects.create(
            code="P-SITES",
            name="Visible project",
            created_by=self.owner,
            updated_by=self.owner,
        )
        visible_site = self.organization.project_sites.create(
            project=project,
            code="SITE-VISIBLE",
            name="Visible worksite",
            created_by=self.owner,
            updated_by=self.owner,
        )
        other_project = self.other_organization.projects.create(
            code="P-SITES",
            name="Hidden project",
            created_by=self.other_user,
            updated_by=self.other_user,
        )
        self.other_organization.project_sites.create(
            project=other_project,
            code="SITE-HIDDEN",
            name="Hidden worksite",
            created_by=self.other_user,
            updated_by=self.other_user,
        )
        self.client.force_login(self.owner)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.organization.pk)
        session.save()

        response = self.client.get(reverse("projects:all_site_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Visible worksite")
        self.assertNotContains(response, "Hidden worksite")
        self.assertContains(
            response,
            reverse(
                "projects:site_list",
                kwargs={"project_id": visible_site.project_id},
            ),
        )

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
        with self.assertRaises(PermissionDenied):
            archive_project(
                user=self.owner,
                organization=self.organization,
                project_id=str(project.pk),
            )
        self.assertEqual(
            AuditEvent.objects.filter(
                action=AuditAction.PROJECT_ARCHIVED,
                entity_id=str(project.pk),
            ).count(),
            1,
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
        self.assertEqual(
            list(
                get_organization_sites(
                    user=self.owner,
                    organization=self.organization,
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

    def test_create_project_phase_is_tenant_scoped_and_audited(self) -> None:
        project = create_project(
            organization=self.organization,
            actor=self.owner,
            code="P-PHASE",
            name="Phase project",
        )
        site = create_project_site(
            organization=self.organization,
            project=project,
            actor=self.owner,
            code="SITE-PHASE",
            name="Phase worksite",
        )

        phase = create_project_phase(
            organization=self.organization,
            site=site,
            actor=self.owner,
            code="PH-001",
            name="Foundation works",
            status=ProjectPhaseStatus.ACTIVE,
            planned_start_date=date(2026, 9, 1),
            planned_end_date=date(2026, 9, 30),
        )

        self.assertEqual(phase.organization, self.organization)
        self.assertEqual(phase.site, site)
        self.assertEqual(phase.status, ProjectPhaseStatus.ACTIVE)
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.PROJECT_PHASE_CREATED,
                organization=self.organization,
                entity_id=str(phase.pk),
            ).exists()
        )
        self.assertEqual(
            list(
                get_organization_project_phases(
                    user=self.owner,
                    organization=self.organization,
                    project_id=str(project.pk),
                    site_id=str(site.pk),
                )
            ),
            [phase],
        )

    def test_project_phase_rejects_cross_tenant_site_and_invalid_dates(self) -> None:
        project = create_project(
            organization=self.organization,
            actor=self.owner,
            code="P-VALID-PHASE",
            name="Valid phase project",
        )
        site = create_project_site(
            organization=self.organization,
            project=project,
            actor=self.owner,
            code="SITE-VALID-PHASE",
            name="Valid phase worksite",
        )
        with self.assertRaisesMessage(
            ValueError,
            "تاریخ پایان فاز نمی‌تواند پیش از تاریخ شروع باشد.",
        ):
            create_project_phase(
                organization=self.organization,
                site=site,
                actor=self.owner,
                code="PH-DATE",
                name="Invalid date phase",
                planned_start_date=date(2026, 9, 2),
                planned_end_date=date(2026, 9, 1),
            )

        other_project = self.other_organization.projects.create(
            code="P-OTHER-PHASE",
            name="Other phase project",
            created_by=self.other_user,
            updated_by=self.other_user,
        )
        other_site = self.other_organization.project_sites.create(
            project=other_project,
            code="SITE-OTHER-PHASE",
            name="Other phase worksite",
            created_by=self.other_user,
            updated_by=self.other_user,
        )
        with self.assertRaises(PermissionDenied):
            create_project_phase(
                organization=self.organization,
                site=other_site,
                actor=self.owner,
                code="PH-OTHER",
                name="Unauthorized phase",
            )

    def test_project_phase_allows_only_valid_audited_status_transitions(self) -> None:
        project = create_project(
            organization=self.organization,
            actor=self.owner,
            code="P-PHASE-WORKFLOW",
            name="Phase workflow project",
        )
        site = create_project_site(
            organization=self.organization,
            project=project,
            actor=self.owner,
            code="SITE-PHASE-WORKFLOW",
            name="Phase workflow worksite",
        )
        phase = create_project_phase(
            organization=self.organization,
            site=site,
            actor=self.owner,
            code="PH-WORKFLOW",
            name="Structural works",
        )

        activated_phase = transition_project_phase_status(
            organization=self.organization,
            project_id=str(project.pk),
            site_id=str(site.pk),
            phase_id=str(phase.pk),
            actor=self.owner,
            target_status=ProjectPhaseStatus.ACTIVE,
        )
        completed_phase = transition_project_phase_status(
            organization=self.organization,
            project_id=str(project.pk),
            site_id=str(site.pk),
            phase_id=str(phase.pk),
            actor=self.owner,
            target_status=ProjectPhaseStatus.COMPLETED,
        )

        self.assertEqual(activated_phase.status, ProjectPhaseStatus.ACTIVE)
        self.assertEqual(completed_phase.status, ProjectPhaseStatus.COMPLETED)
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.PROJECT_PHASE_STATUS_CHANGED,
                entity_id=str(phase.pk),
            ).exists()
        )
        with self.assertRaisesMessage(
            ValueError,
            "این تغییر وضعیت برای فاز پروژه مجاز نیست.",
        ):
            transition_project_phase_status(
                organization=self.organization,
                project_id=str(project.pk),
                site_id=str(site.pk),
                phase_id=str(phase.pk),
                actor=self.owner,
                target_status=ProjectPhaseStatus.ACTIVE,
            )


class ProjectControlsServiceTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(
            username="controls-owner", password="test-password"
        )
        self.other_owner = User.objects.create_user(
            username="controls-other", password="test-password"
        )
        self.organization = Organization.objects.create(
            name="Controls Co", slug="controls-co"
        )
        self.other_organization = Organization.objects.create(
            name="Other Controls Co", slug="other-controls-co"
        )
        self.organization.memberships.create(
            user=self.owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.other_organization.memberships.create(
            user=self.other_owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.project = create_project(
            organization=self.organization,
            actor=self.owner,
            code="CTRL",
            name="Controls Project",
        )
        self.unit = create_unit_of_measure(
            organization=self.organization,
            actor=self.owner,
            code="M",
            name="Metre",
            symbol="m",
            category="length",
            decimal_places=2,
        )

    def test_wbs_hierarchy_activity_scope_and_lifecycle_are_enforced(self) -> None:
        root = create_wbs_node(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            code="01",
            title="Structure",
        )
        child = create_wbs_node(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            code="01-01",
            title="Concrete",
            parent=root,
        )
        with self.assertRaisesMessage(ValueError, "نمی‌تواند شامل چرخه باشد"):
            update_wbs_node(
                organization=self.organization,
                actor=self.owner,
                node=root,
                code="01",
                title="Structure",
                parent=child,
            )
        activity = create_activity(
            organization=self.organization,
            project=self.project,
            wbs_node=child,
            actor=self.owner,
            code="CAST",
            name="Cast concrete",
            unit_of_measure=self.unit,
            planned_quantity=Decimal("25.0000"),
        )
        active = transition_activity_status(
            organization=self.organization,
            actor=self.owner,
            activity=activity,
            target_status=ActivityStatus.ACTIVE,
        )
        self.assertEqual(active.status, ActivityStatus.ACTIVE)
        with self.assertRaisesMessage(ValueError, "زیرگره یا فعالیت فعال"):
            archive_wbs_node(
                organization=self.organization, actor=self.owner, node=child
            )
        archive_activity(
            organization=self.organization, actor=self.owner, activity=activity
        )
        archive_wbs_node(organization=self.organization, actor=self.owner, node=child)
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.ACTIVITY_STATUS_CHANGED, entity_id=str(activity.pk)
            ).exists()
        )

    def test_controls_are_tenant_scoped(self) -> None:
        other_project = create_project(
            organization=self.other_organization,
            actor=self.other_owner,
            code="OTHER",
            name="Other",
        )
        other_node = create_wbs_node(
            organization=self.other_organization,
            project=other_project,
            actor=self.other_owner,
            code="01",
            title="Other",
        )
        with self.assertRaises(PermissionDenied):
            create_activity(
                organization=self.organization,
                project=self.project,
                wbs_node=other_node,
                actor=self.owner,
                code="BAD",
                name="Cross tenant",
            )
        self.assertFalse(
            get_organization_wbs_nodes(
                user=self.owner,
                organization=self.organization,
                project_id=str(self.project.pk),
            )
            .filter(pk=other_node.pk)
            .exists()
        )
