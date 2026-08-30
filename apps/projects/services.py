from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.models import (
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationStatus,
)
from apps.projects.models import (
    Project,
    ProjectPhase,
    ProjectPhaseStatus,
    ProjectSite,
    ProjectStatus,
)


def _has_active_membership(user: User, organization: Organization) -> bool:
    return organization.memberships.filter(
        user=user,
        status=MembershipStatus.ACTIVE,
    ).exists()


def _can_manage_projects(user: User, organization: Organization) -> bool:
    return organization.memberships.filter(
        user=user,
        status=MembershipStatus.ACTIVE,
        role__in=[
            MembershipRole.OWNER,
            MembershipRole.ADMIN,
            MembershipRole.MANAGER,
        ],
    ).exists()


@transaction.atomic
def create_project(
    *,
    organization: Organization,
    actor: User,
    code: str,
    name: str,
    description: str = "",
    status: str = ProjectStatus.PLANNING,
    start_date: date | None = None,
    end_date: date | None = None,
    budget: Decimal = Decimal("0.00"),
) -> Project:
    """Create a project after validating organization scope and core rules."""

    if not actor.is_authenticated or not actor.is_active:
        raise PermissionDenied("Authentication is required.")
    if (
        organization.status != OrganizationStatus.ACTIVE
        or organization.deleted_at is not None
    ):
        raise PermissionDenied("The organization is not active.")
    if not _can_manage_projects(actor, organization):
        raise PermissionDenied("You cannot create projects in this organization.")
    if not code.strip() or not name.strip():
        raise ValueError("Project code and name are required.")
    if status not in ProjectStatus.values:
        raise ValueError("Invalid project status.")
    if start_date and end_date and end_date < start_date:
        raise ValueError("Project end date cannot be before start date.")
    if budget < Decimal("0.00"):
        raise ValueError("Project budget cannot be negative.")

    project = Project.objects.create(
        organization=organization,
        code=code.strip(),
        name=name.strip(),
        description=description.strip(),
        status=status,
        start_date=start_date,
        end_date=end_date,
        budget=budget,
        created_by=actor,
        updated_by=actor,
    )
    record_audit_event(
        action=AuditAction.PROJECT_CREATED,
        entity_type="project",
        entity_id=project.pk,
        organization=organization,
        actor=actor,
        metadata={"code": project.code, "name": project.name},
    )
    return project


def get_organization_projects(
    *,
    user: User,
    organization: Organization,
) -> QuerySet[Project]:
    """Return non-deleted projects for a user's active organization."""

    if not user.is_authenticated:
        raise PermissionDenied("Authentication is required.")
    if (
        organization.status != OrganizationStatus.ACTIVE
        or organization.deleted_at is not None
    ):
        raise PermissionDenied("The organization is not active.")
    if not _has_active_membership(user, organization):
        raise PermissionDenied("You do not have access to this organization.")
    return (
        Project.objects.filter(
            organization=organization,
            deleted_at__isnull=True,
        )
        .select_related("created_by", "updated_by")
        .order_by("name")
    )


def get_organization_project(
    *,
    user: User,
    organization: Organization,
    project_id: str,
) -> Project:
    """Return one non-deleted project from the active organization."""

    projects = get_organization_projects(user=user, organization=organization)
    try:
        return projects.get(pk=project_id)
    except Project.DoesNotExist as exc:
        raise PermissionDenied("Project not found in this organization.") from exc


@transaction.atomic
def create_project_site(
    *,
    organization: Organization,
    project: Project,
    actor: User,
    code: str,
    name: str,
    address: str = "",
) -> ProjectSite:
    """Create a site after enforcing organization and project scope."""

    if not actor.is_authenticated or not actor.is_active:
        raise PermissionDenied("Authentication is required.")
    if (
        organization.status != OrganizationStatus.ACTIVE
        or organization.deleted_at is not None
    ):
        raise PermissionDenied("The organization is not active.")
    if not _can_manage_projects(actor, organization):
        raise PermissionDenied("You cannot manage project sites in this organization.")
    if project.organization_id != organization.pk or project.deleted_at is not None:
        raise PermissionDenied("The project does not belong to this organization.")
    if not code.strip() or not name.strip():
        raise ValueError("Site code and name are required.")
    normalized_code = code.strip()
    if ProjectSite.objects.filter(
        organization=organization,
        project=project,
        code=normalized_code,
    ).exists():
        raise ValueError("A site with this code already exists for the project.")

    site = ProjectSite.objects.create(
        organization=organization,
        project=project,
        code=normalized_code,
        name=name.strip(),
        address=address.strip(),
        created_by=actor,
        updated_by=actor,
    )
    record_audit_event(
        action=AuditAction.PROJECT_SITE_CREATED,
        entity_type="project_site",
        entity_id=site.pk,
        organization=organization,
        actor=actor,
        metadata={"project_id": str(project.pk), "code": site.code},
    )
    return site


def get_organization_project_sites(
    *,
    user: User,
    organization: Organization,
    project_id: str,
) -> QuerySet[ProjectSite]:
    """Return sites only for a project in the active organization."""

    project = get_organization_project(
        user=user,
        organization=organization,
        project_id=project_id,
    )
    return ProjectSite.objects.filter(
        organization=organization,
        project=project,
    ).select_related("project")


def get_organization_project_site(
    *,
    user: User,
    organization: Organization,
    project_id: str,
    site_id: str,
) -> ProjectSite:
    """Return one site only when it belongs to the active project and tenant."""

    sites = get_organization_project_sites(
        user=user,
        organization=organization,
        project_id=project_id,
    )
    try:
        return sites.get(pk=site_id)
    except ProjectSite.DoesNotExist as exc:
        raise PermissionDenied("Worksite not found in this project.") from exc


@transaction.atomic
def create_project_phase(
    *,
    organization: Organization,
    site: ProjectSite,
    actor: User,
    code: str,
    name: str,
    status: str = ProjectPhaseStatus.PLANNING,
    planned_start_date: date | None = None,
    planned_end_date: date | None = None,
) -> ProjectPhase:
    """Create a phase after enforcing active tenant and site scope."""

    if not actor.is_authenticated or not actor.is_active:
        raise PermissionDenied("Authentication is required.")
    if (
        organization.status != OrganizationStatus.ACTIVE
        or organization.deleted_at is not None
    ):
        raise PermissionDenied("The organization is not active.")
    if not _can_manage_projects(actor, organization):
        raise PermissionDenied("You cannot manage project phases in this organization.")
    if (
        site.organization_id != organization.pk
        or site.project.deleted_at is not None
        or not site.is_active
    ):
        raise PermissionDenied("The worksite does not belong to this organization.")
    if not code.strip() or not name.strip():
        raise ValueError("Phase code and name are required.")
    if status not in ProjectPhaseStatus.values:
        raise ValueError("Invalid project phase status.")
    if (
        planned_start_date
        and planned_end_date
        and planned_end_date < planned_start_date
    ):
        raise ValueError("Phase end date cannot be before start date.")
    normalized_code = code.strip()
    if ProjectPhase.objects.filter(
        organization=organization,
        site=site,
        code=normalized_code,
    ).exists():
        raise ValueError("A phase with this code already exists for the worksite.")

    return ProjectPhase.objects.create(
        organization=organization,
        site=site,
        code=normalized_code,
        name=name.strip(),
        status=status,
        planned_start_date=planned_start_date,
        planned_end_date=planned_end_date,
        created_by=actor,
        updated_by=actor,
    )


def get_organization_project_phases(
    *,
    user: User,
    organization: Organization,
    project_id: str,
    site_id: str,
) -> QuerySet[ProjectPhase]:
    """Return phases only for a site in the active organization."""

    site = get_organization_project_site(
        user=user,
        organization=organization,
        project_id=project_id,
        site_id=site_id,
    )
    return ProjectPhase.objects.filter(
        organization=organization,
        site=site,
    ).select_related("site", "site__project")


@transaction.atomic
def archive_project(
    *,
    user: User,
    organization: Organization,
    project_id: str,
) -> None:
    """Soft-delete a project after validating tenant and management scope."""

    if not _can_manage_projects(user, organization):
        raise PermissionDenied("You cannot archive projects in this organization.")
    project = get_organization_project(
        user=user,
        organization=organization,
        project_id=project_id,
    )
    project.deleted_at = timezone.now()
    project.updated_by = user
    project.save(update_fields=["deleted_at", "updated_by", "updated_at"])
    record_audit_event(
        action=AuditAction.PROJECT_ARCHIVED,
        entity_type="project",
        entity_id=project.pk,
        organization=organization,
        actor=user,
        metadata={"code": project.code, "name": project.name},
    )
