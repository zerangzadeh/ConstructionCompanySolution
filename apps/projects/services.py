from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
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
    Activity,
    ActivityStatus,
    Project,
    ProjectPhase,
    ProjectPhaseStatus,
    ProjectSite,
    ProjectStatus,
    WBSNode,
)
from core.identifiers import canonicalize_upper_identifier

_ALLOWED_PHASE_STATUS_TRANSITIONS: dict[str, tuple[str, ...]] = {
    ProjectPhaseStatus.PLANNING: (
        ProjectPhaseStatus.ACTIVE,
        ProjectPhaseStatus.ON_HOLD,
    ),
    ProjectPhaseStatus.ACTIVE: (
        ProjectPhaseStatus.ON_HOLD,
        ProjectPhaseStatus.COMPLETED,
    ),
    ProjectPhaseStatus.ON_HOLD: (ProjectPhaseStatus.ACTIVE,),
    ProjectPhaseStatus.COMPLETED: (),
}

_ALLOWED_ACTIVITY_STATUS_TRANSITIONS: dict[str, tuple[str, ...]] = {
    ActivityStatus.PLANNING: (
        ActivityStatus.ACTIVE,
        ActivityStatus.ON_HOLD,
        ActivityStatus.CANCELLED,
    ),
    ActivityStatus.ACTIVE: (
        ActivityStatus.ON_HOLD,
        ActivityStatus.COMPLETED,
        ActivityStatus.CANCELLED,
    ),
    ActivityStatus.ON_HOLD: (ActivityStatus.ACTIVE, ActivityStatus.CANCELLED),
    ActivityStatus.COMPLETED: (),
    ActivityStatus.CANCELLED: (),
}


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


def _require_project_management_access(
    *, organization: Organization, actor: User
) -> None:
    if not actor.is_authenticated or not actor.is_active:
        raise PermissionDenied("Authentication is required.")
    if (
        organization.status != OrganizationStatus.ACTIVE
        or organization.deleted_at is not None
    ):
        raise PermissionDenied("The organization is not active.")
    if not _can_manage_projects(actor, organization):
        raise PermissionDenied(
            "You cannot manage project controls in this organization."
        )


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

    normalized_code = canonicalize_upper_identifier(code)
    project = Project.objects.create(
        organization=organization,
        code=normalized_code,
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
    normalized_code = canonicalize_upper_identifier(code)
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
    normalized_code = canonicalize_upper_identifier(code)
    if ProjectPhase.objects.filter(
        organization=organization,
        site=site,
        code=normalized_code,
    ).exists():
        raise ValueError("A phase with this code already exists for the worksite.")

    phase = ProjectPhase.objects.create(
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
    record_audit_event(
        action=AuditAction.PROJECT_PHASE_CREATED,
        entity_type="project_phase",
        entity_id=phase.pk,
        organization=organization,
        actor=actor,
        metadata={"site_id": str(site.pk), "code": phase.code},
    )
    return phase


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


def get_organization_project_phase(
    *,
    user: User,
    organization: Organization,
    project_id: str,
    site_id: str,
    phase_id: str,
) -> ProjectPhase:
    """Return one phase only when it belongs to the active tenant hierarchy."""

    phases = get_organization_project_phases(
        user=user,
        organization=organization,
        project_id=project_id,
        site_id=site_id,
    )
    try:
        return phases.get(pk=phase_id)
    except ProjectPhase.DoesNotExist as exc:
        raise PermissionDenied("Project phase not found in this worksite.") from exc


def get_available_phase_statuses(
    phase: ProjectPhase,
) -> tuple[tuple[str, str], ...]:
    """Return valid next status values for display in a phase detail page."""

    return tuple(
        (status, ProjectPhaseStatus(status).label)
        for status in _ALLOWED_PHASE_STATUS_TRANSITIONS[phase.status]
    )


@transaction.atomic
def transition_project_phase_status(
    *,
    organization: Organization,
    project_id: str,
    site_id: str,
    phase_id: str,
    actor: User,
    target_status: str,
) -> ProjectPhase:
    """Apply one allowed, audited phase status transition atomically."""

    if not actor.is_authenticated or not actor.is_active:
        raise PermissionDenied("Authentication is required.")
    if (
        organization.status != OrganizationStatus.ACTIVE
        or organization.deleted_at is not None
    ):
        raise PermissionDenied("The organization is not active.")
    if not _can_manage_projects(actor, organization):
        raise PermissionDenied("You cannot update project phases in this organization.")
    site = get_organization_project_site(
        user=actor,
        organization=organization,
        project_id=project_id,
        site_id=site_id,
    )
    if not site.is_active or site.project.deleted_at is not None:
        raise PermissionDenied("The worksite is not active.")
    try:
        phase = (
            ProjectPhase.objects.select_for_update()
            .select_related("site", "site__project")
            .get(pk=phase_id, organization=organization, site=site)
        )
    except ProjectPhase.DoesNotExist as exc:
        raise PermissionDenied("Project phase not found in this worksite.") from exc
    if target_status not in ProjectPhaseStatus.values:
        raise ValueError("Invalid project phase status.")
    if target_status not in _ALLOWED_PHASE_STATUS_TRANSITIONS[phase.status]:
        raise ValueError("This project phase status transition is not allowed.")

    previous_status = phase.status
    phase.status = target_status
    phase.updated_by = actor
    phase.save(update_fields=["status", "updated_by", "updated_at"])
    record_audit_event(
        action=AuditAction.PROJECT_PHASE_STATUS_CHANGED,
        entity_type="project_phase",
        entity_id=phase.pk,
        organization=organization,
        actor=actor,
        metadata={
            "site_id": str(site.pk),
            "previous_status": previous_status,
            "new_status": phase.status,
        },
    )
    return phase


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
    projects = get_organization_projects(user=user, organization=organization)
    try:
        project = projects.select_related(None).select_for_update().get(pk=project_id)
    except Project.DoesNotExist as exc:
        raise PermissionDenied("Project not found in this organization.") from exc
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


def _validate_wbs_parent(node: WBSNode) -> None:
    parent = node.parent
    while parent is not None:
        if parent.pk == node.pk:
            raise ValueError("WBS hierarchy cannot contain a cycle.")
        parent = parent.parent


@transaction.atomic
def create_wbs_node(
    *,
    organization: Organization,
    project: Project,
    actor: User,
    code: str,
    title: str,
    parent: WBSNode | None = None,
    sort_order: int = 0,
) -> WBSNode:
    _require_project_management_access(organization=organization, actor=actor)
    if project.organization_id != organization.id or project.deleted_at is not None:
        raise PermissionDenied("The project does not belong to this organization.")
    if parent and (
        parent.organization_id != organization.id or parent.project_id != project.id
    ):
        raise PermissionDenied("The parent WBS node does not belong to this project.")
    node = WBSNode(
        organization=organization,
        project=project,
        code=code,
        title=title,
        parent=parent,
        sort_order=sort_order,
        created_by=actor,
        updated_by=actor,
    )
    try:
        node.full_clean()
        _validate_wbs_parent(node)
        node.save()
    except ValueError:
        raise
    except (IntegrityError, ValidationError) as exc:
        raise ValueError(
            "WBS node data is invalid or its code already exists."
        ) from exc
    record_audit_event(
        action=AuditAction.WBS_NODE_CREATED,
        entity_type="wbs_node",
        entity_id=node.pk,
        organization=organization,
        actor=actor,
        metadata={"project_id": str(project.pk), "code": node.code},
    )
    return node


@transaction.atomic
def update_wbs_node(
    *,
    organization: Organization,
    actor: User,
    node: WBSNode,
    code: str,
    title: str,
    parent: WBSNode | None = None,
    sort_order: int = 0,
) -> WBSNode:
    _require_project_management_access(organization=organization, actor=actor)
    locked_node = (
        WBSNode.objects.select_for_update().select_related("project").get(pk=node.pk)
    )
    if locked_node.organization_id != organization.id:
        raise PermissionDenied("The WBS node does not belong to this organization.")
    if locked_node.archived_at:
        raise ValueError("Archived WBS nodes cannot be updated.")
    if parent and (
        parent.organization_id != organization.id
        or parent.project_id != locked_node.project_id
    ):
        raise PermissionDenied("The parent WBS node does not belong to this project.")
    locked_node.code, locked_node.title, locked_node.parent, locked_node.sort_order = (
        code,
        title,
        parent,
        sort_order,
    )
    locked_node.updated_by = actor
    try:
        locked_node.full_clean()
        _validate_wbs_parent(locked_node)
        locked_node.save()
    except ValueError:
        raise
    except (IntegrityError, ValidationError) as exc:
        raise ValueError(
            "WBS node data is invalid or its code already exists."
        ) from exc
    record_audit_event(
        action=AuditAction.WBS_NODE_UPDATED,
        entity_type="wbs_node",
        entity_id=locked_node.pk,
        organization=organization,
        actor=actor,
        metadata={"code": locked_node.code},
    )
    return locked_node


def get_organization_wbs_nodes(
    *, user: User, organization: Organization, project_id: str
) -> QuerySet[WBSNode]:
    project = get_organization_project(
        user=user, organization=organization, project_id=project_id
    )
    return WBSNode.objects.filter(
        organization=organization, project=project, archived_at__isnull=True
    ).select_related("parent")


@transaction.atomic
def archive_wbs_node(
    *, organization: Organization, actor: User, node: WBSNode
) -> WBSNode:
    _require_project_management_access(organization=organization, actor=actor)
    locked_node = WBSNode.objects.select_for_update().get(pk=node.pk)
    if locked_node.organization_id != organization.id:
        raise PermissionDenied("The WBS node does not belong to this organization.")
    if locked_node.archived_at:
        raise ValueError("The WBS node is already archived.")
    if (
        locked_node.children.filter(archived_at__isnull=True).exists()
        or locked_node.activities.filter(archived_at__isnull=True).exists()
    ):
        raise ValueError(
            "A WBS node with active children or activities cannot be archived."
        )
    locked_node.archived_at, locked_node.is_active, locked_node.updated_by = (
        timezone.now(),
        False,
        actor,
    )
    locked_node.save(
        update_fields=["archived_at", "is_active", "updated_by", "updated_at"]
    )
    record_audit_event(
        action=AuditAction.WBS_NODE_ARCHIVED,
        entity_type="wbs_node",
        entity_id=locked_node.pk,
        organization=organization,
        actor=actor,
        metadata={"code": locked_node.code},
    )
    return locked_node


@transaction.atomic
def create_activity(
    *,
    organization: Organization,
    project: Project,
    wbs_node: WBSNode,
    actor: User,
    code: str,
    name: str,
    site: ProjectSite | None = None,
    phase: ProjectPhase | None = None,
    unit_of_measure: object | None = None,
    planned_quantity: Decimal | None = None,
    planned_start_date: date | None = None,
    planned_end_date: date | None = None,
    status: str = ActivityStatus.PLANNING,
) -> Activity:
    _require_project_management_access(organization=organization, actor=actor)
    if project.organization_id != organization.id or project.deleted_at is not None:
        raise PermissionDenied("The project does not belong to this organization.")
    if (
        wbs_node.organization_id != organization.id
        or wbs_node.project_id != project.id
        or wbs_node.archived_at is not None
        or not wbs_node.is_active
    ):
        raise PermissionDenied("The WBS node does not belong to this active project.")
    if status not in ActivityStatus.values:
        raise ValueError("Invalid activity status.")
    activity = Activity(
        organization=organization,
        project=project,
        wbs_node=wbs_node,
        site=site,
        phase=phase,
        unit_of_measure=unit_of_measure,
        code=code,
        name=name,
        planned_quantity=planned_quantity,
        planned_start_date=planned_start_date,
        planned_end_date=planned_end_date,
        status=status,
        created_by=actor,
        updated_by=actor,
    )
    try:
        activity.full_clean()
        activity.save()
    except (IntegrityError, ValidationError) as exc:
        raise ValueError(
            "Activity data is invalid or its code already exists."
        ) from exc
    record_audit_event(
        action=AuditAction.ACTIVITY_CREATED,
        entity_type="activity",
        entity_id=activity.pk,
        organization=organization,
        actor=actor,
        metadata={
            "project_id": str(project.pk),
            "wbs_node_id": str(wbs_node.pk),
            "code": activity.code,
        },
    )
    return activity


def get_organization_activities(
    *, user: User, organization: Organization, project_id: str
) -> QuerySet[Activity]:
    project = get_organization_project(
        user=user, organization=organization, project_id=project_id
    )
    return Activity.objects.filter(
        organization=organization, project=project, archived_at__isnull=True
    ).select_related("wbs_node", "site", "phase", "unit_of_measure")


@transaction.atomic
def transition_activity_status(
    *, organization: Organization, actor: User, activity: Activity, target_status: str
) -> Activity:
    _require_project_management_access(organization=organization, actor=actor)
    locked_activity = Activity.objects.select_for_update().get(pk=activity.pk)
    if locked_activity.organization_id != organization.id:
        raise PermissionDenied("The activity does not belong to this organization.")
    if locked_activity.archived_at:
        raise ValueError("Archived activities cannot change status.")
    if target_status not in ActivityStatus.values:
        raise ValueError("Invalid activity status.")
    if (
        target_status
        not in _ALLOWED_ACTIVITY_STATUS_TRANSITIONS[locked_activity.status]
    ):
        raise ValueError("This activity status transition is not allowed.")
    previous_status = locked_activity.status
    locked_activity.status, locked_activity.updated_by = target_status, actor
    locked_activity.save(update_fields=["status", "updated_by", "updated_at"])
    record_audit_event(
        action=AuditAction.ACTIVITY_STATUS_CHANGED,
        entity_type="activity",
        entity_id=locked_activity.pk,
        organization=organization,
        actor=actor,
        metadata={"previous_status": previous_status, "new_status": target_status},
    )
    return locked_activity


@transaction.atomic
def archive_activity(
    *, organization: Organization, actor: User, activity: Activity
) -> Activity:
    _require_project_management_access(organization=organization, actor=actor)
    locked_activity = Activity.objects.select_for_update().get(pk=activity.pk)
    if locked_activity.organization_id != organization.id:
        raise PermissionDenied("The activity does not belong to this organization.")
    if locked_activity.archived_at:
        raise ValueError("The activity is already archived.")
    (
        locked_activity.archived_at,
        locked_activity.is_active,
        locked_activity.updated_by,
    ) = timezone.now(), False, actor
    locked_activity.save(
        update_fields=["archived_at", "is_active", "updated_by", "updated_at"]
    )
    record_audit_event(
        action=AuditAction.ACTIVITY_ARCHIVED,
        entity_type="activity",
        entity_id=locked_activity.pk,
        organization=organization,
        actor=actor,
        metadata={"code": locked_activity.code},
    )
    return locked_activity
