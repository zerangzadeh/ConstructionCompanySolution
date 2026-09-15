from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.authorization import has_business_permission
from apps.organizations.models import (
    BusinessPermissionCode,
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


def _has_project_permission(
    user: User,
    organization: Organization,
    permission: BusinessPermissionCode,
) -> bool:
    return has_business_permission(
        user=user,
        organization=organization,
        permission=permission,
    )


def _require_project_management_access(
    *,
    organization: Organization,
    actor: User,
    permission: BusinessPermissionCode,
) -> None:
    if not actor.is_authenticated or not actor.is_active:
        raise PermissionDenied("ورود به حساب کاربری الزامی است.")
    if (
        organization.status != OrganizationStatus.ACTIVE
        or organization.deleted_at is not None
    ):
        raise PermissionDenied("سازمان فعال نیست.")
    if not _has_project_permission(actor, organization, permission):
        raise PermissionDenied("اجازه مدیریت کنترل پروژه در این سازمان را ندارید.")


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
        raise PermissionDenied("ورود به حساب کاربری الزامی است.")
    if (
        organization.status != OrganizationStatus.ACTIVE
        or organization.deleted_at is not None
    ):
        raise PermissionDenied("سازمان فعال نیست.")
    if not _has_project_permission(
        actor, organization, BusinessPermissionCode.PROJECTS_CREATE
    ):
        raise PermissionDenied("اجازه ایجاد پروژه در این سازمان را ندارید.")
    if not code.strip() or not name.strip():
        raise ValueError("وارد کردن کد و نام پروژه الزامی است.")
    if status not in ProjectStatus.values:
        raise ValueError("وضعیت پروژه معتبر نیست.")
    if start_date and end_date and end_date < start_date:
        raise ValueError("تاریخ پایان پروژه نمی‌تواند پیش از تاریخ شروع باشد.")
    if budget < Decimal("0.00"):
        raise ValueError("بودجه پروژه نمی‌تواند منفی باشد.")

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
        raise PermissionDenied("ورود به حساب کاربری الزامی است.")
    if (
        organization.status != OrganizationStatus.ACTIVE
        or organization.deleted_at is not None
    ):
        raise PermissionDenied("سازمان فعال نیست.")
    if not _has_project_permission(
        user, organization, BusinessPermissionCode.PROJECTS_VIEW
    ):
        raise PermissionDenied("اجازه مشاهده پروژه‌های این سازمان را ندارید.")
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
        raise PermissionDenied("پروژه در این سازمان یافت نشد.") from exc


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
        raise PermissionDenied("ورود به حساب کاربری الزامی است.")
    if (
        organization.status != OrganizationStatus.ACTIVE
        or organization.deleted_at is not None
    ):
        raise PermissionDenied("سازمان فعال نیست.")
    if not _has_project_permission(
        actor, organization, BusinessPermissionCode.PROJECT_SITES_CREATE
    ):
        raise PermissionDenied("اجازه مدیریت کارگاه‌های این سازمان را ندارید.")
    if project.organization_id != organization.pk or project.deleted_at is not None:
        raise PermissionDenied("پروژه متعلق به این سازمان نیست.")
    if not code.strip() or not name.strip():
        raise ValueError("وارد کردن کد و نام کارگاه الزامی است.")
    normalized_code = canonicalize_upper_identifier(code)
    if ProjectSite.objects.filter(
        organization=organization,
        project=project,
        code=normalized_code,
    ).exists():
        raise ValueError("کارگاهی با این کد از قبل برای پروژه وجود دارد.")

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
    if not _has_project_permission(
        user, organization, BusinessPermissionCode.PROJECT_SITES_VIEW
    ):
        raise PermissionDenied("اجازه مشاهده کارگاه‌های این سازمان را ندارید.")
    return ProjectSite.objects.filter(
        organization=organization,
        project=project,
    ).select_related("project")


def get_organization_sites(
    *,
    user: User,
    organization: Organization,
) -> QuerySet[ProjectSite]:
    """Return every worksite in the active organization."""

    if not _has_project_permission(
        user, organization, BusinessPermissionCode.PROJECT_SITES_VIEW
    ):
        raise PermissionDenied("اجازه مشاهده کارگاه‌های این سازمان را ندارید.")
    return ProjectSite.objects.filter(organization=organization).select_related(
        "project"
    )


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
        raise PermissionDenied("کارگاه در این پروژه یافت نشد.") from exc


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
        raise PermissionDenied("ورود به حساب کاربری الزامی است.")
    if (
        organization.status != OrganizationStatus.ACTIVE
        or organization.deleted_at is not None
    ):
        raise PermissionDenied("سازمان فعال نیست.")
    if not _has_project_permission(
        actor, organization, BusinessPermissionCode.PROJECT_PHASES_CREATE
    ):
        raise PermissionDenied("اجازه مدیریت فازهای پروژه در این سازمان را ندارید.")
    if (
        site.organization_id != organization.pk
        or site.project.deleted_at is not None
        or not site.is_active
    ):
        raise PermissionDenied("کارگاه متعلق به این سازمان نیست.")
    if not code.strip() or not name.strip():
        raise ValueError("وارد کردن کد و نام فاز پروژه الزامی است.")
    if status not in ProjectPhaseStatus.values:
        raise ValueError("وضعیت فاز پروژه معتبر نیست.")
    if (
        planned_start_date
        and planned_end_date
        and planned_end_date < planned_start_date
    ):
        raise ValueError("تاریخ پایان فاز نمی‌تواند پیش از تاریخ شروع باشد.")
    normalized_code = canonicalize_upper_identifier(code)
    if ProjectPhase.objects.filter(
        organization=organization,
        site=site,
        code=normalized_code,
    ).exists():
        raise ValueError("فازی با این کد از قبل برای کارگاه وجود دارد.")

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
    if not _has_project_permission(
        user, organization, BusinessPermissionCode.PROJECT_PHASES_VIEW
    ):
        raise PermissionDenied("اجازه مشاهده فازهای این سازمان را ندارید.")
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
        raise PermissionDenied("فاز پروژه در این کارگاه یافت نشد.") from exc


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
        raise PermissionDenied("ورود به حساب کاربری الزامی است.")
    if (
        organization.status != OrganizationStatus.ACTIVE
        or organization.deleted_at is not None
    ):
        raise PermissionDenied("سازمان فعال نیست.")
    if not _has_project_permission(
        actor, organization, BusinessPermissionCode.PROJECT_PHASES_TRANSITION
    ):
        raise PermissionDenied("اجازه تغییر فازهای پروژه در این سازمان را ندارید.")
    try:
        site = ProjectSite.objects.select_related("project").get(
            pk=site_id,
            organization=organization,
            project_id=project_id,
        )
    except ProjectSite.DoesNotExist as exc:
        raise PermissionDenied("کارگاه در این پروژه یافت نشد.") from exc
    if not site.is_active or site.project.deleted_at is not None:
        raise PermissionDenied("کارگاه فعال نیست.")
    try:
        phase = (
            ProjectPhase.objects.select_for_update()
            .select_related("site", "site__project")
            .get(pk=phase_id, organization=organization, site=site)
        )
    except ProjectPhase.DoesNotExist as exc:
        raise PermissionDenied("فاز پروژه در این کارگاه یافت نشد.") from exc
    if target_status not in ProjectPhaseStatus.values:
        raise ValueError("وضعیت فاز پروژه معتبر نیست.")
    if target_status not in _ALLOWED_PHASE_STATUS_TRANSITIONS[phase.status]:
        raise ValueError("این تغییر وضعیت برای فاز پروژه مجاز نیست.")

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

    if not _has_project_permission(
        user, organization, BusinessPermissionCode.PROJECTS_ARCHIVE
    ):
        raise PermissionDenied("اجازه بایگانی پروژه‌های این سازمان را ندارید.")
    try:
        project = Project.objects.select_for_update().get(
            pk=project_id,
            organization=organization,
            deleted_at__isnull=True,
        )
    except Project.DoesNotExist as exc:
        raise PermissionDenied("پروژه در این سازمان یافت نشد.") from exc
    if project.warehouses.filter(is_active=True, archived_at__isnull=True).exists():
        raise ValueError("ابتدا انبارهای فعال پروژه را بایگانی کنید.")
    if project.stock_transactions.filter(status="draft").exists():
        raise ValueError("ابتدا تراکنش‌های پیش‌نویس انبار پروژه را ثبت یا حذف کنید.")
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
            raise ValueError("ساختار شکست کار نمی‌تواند شامل چرخه باشد.")
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
    _require_project_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.WBS_NODES_CREATE,
    )
    if project.organization_id != organization.id or project.deleted_at is not None:
        raise PermissionDenied("پروژه متعلق به این سازمان نیست.")
    if parent and (
        parent.organization_id != organization.id or parent.project_id != project.id
    ):
        raise PermissionDenied("گره والد ساختار شکست متعلق به این پروژه نیست.")
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
            "اطلاعات گره ساختار شکست معتبر نیست یا کد آن از قبل وجود دارد."
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
    _require_project_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.WBS_NODES_CHANGE,
    )
    locked_node = (
        WBSNode.objects.select_for_update().select_related("project").get(pk=node.pk)
    )
    if locked_node.organization_id != organization.id:
        raise PermissionDenied("گره ساختار شکست متعلق به این سازمان نیست.")
    if locked_node.archived_at:
        raise ValueError("گره ساختار شکست بایگانی‌شده قابل به‌روزرسانی نیست.")
    if parent and (
        parent.organization_id != organization.id
        or parent.project_id != locked_node.project_id
    ):
        raise PermissionDenied("گره والد ساختار شکست متعلق به این پروژه نیست.")
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
            "اطلاعات گره ساختار شکست معتبر نیست یا کد آن از قبل وجود دارد."
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
    if not _has_project_permission(
        user, organization, BusinessPermissionCode.WBS_NODES_VIEW
    ):
        raise PermissionDenied("اجازه مشاهده ساختار شکست این پروژه را ندارید.")
    return WBSNode.objects.filter(
        organization=organization, project=project, archived_at__isnull=True
    ).select_related("parent")


@transaction.atomic
def archive_wbs_node(
    *, organization: Organization, actor: User, node: WBSNode
) -> WBSNode:
    _require_project_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.WBS_NODES_ARCHIVE,
    )
    locked_node = WBSNode.objects.select_for_update().get(pk=node.pk)
    if locked_node.organization_id != organization.id:
        raise PermissionDenied("گره ساختار شکست متعلق به این سازمان نیست.")
    if locked_node.archived_at:
        raise ValueError("گره ساختار شکست از قبل بایگانی شده است.")
    if (
        locked_node.children.filter(archived_at__isnull=True).exists()
        or locked_node.activities.filter(archived_at__isnull=True).exists()
    ):
        raise ValueError(
            "گره ساختار شکست دارای زیرگره یا فعالیت فعال قابل بایگانی نیست."
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
    _require_project_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.ACTIVITIES_CREATE,
    )
    if project.organization_id != organization.id or project.deleted_at is not None:
        raise PermissionDenied("پروژه متعلق به این سازمان نیست.")
    if (
        wbs_node.organization_id != organization.id
        or wbs_node.project_id != project.id
        or wbs_node.archived_at is not None
        or not wbs_node.is_active
    ):
        raise PermissionDenied("گره ساختار شکست متعلق به این پروژه فعال نیست.")
    if status not in ActivityStatus.values:
        raise ValueError("وضعیت فعالیت معتبر نیست.")
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
            "اطلاعات فعالیت معتبر نیست یا کد آن از قبل وجود دارد."
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
    if not _has_project_permission(
        user, organization, BusinessPermissionCode.ACTIVITIES_VIEW
    ):
        raise PermissionDenied("اجازه مشاهده فعالیت‌های این پروژه را ندارید.")
    return Activity.objects.filter(
        organization=organization, project=project, archived_at__isnull=True
    ).select_related("wbs_node", "site", "phase", "unit_of_measure")


@transaction.atomic
def transition_activity_status(
    *, organization: Organization, actor: User, activity: Activity, target_status: str
) -> Activity:
    _require_project_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.ACTIVITIES_TRANSITION,
    )
    locked_activity = Activity.objects.select_for_update().get(pk=activity.pk)
    if locked_activity.organization_id != organization.id:
        raise PermissionDenied("فعالیت متعلق به این سازمان نیست.")
    if locked_activity.archived_at:
        raise ValueError("وضعیت فعالیت بایگانی‌شده قابل تغییر نیست.")
    if target_status not in ActivityStatus.values:
        raise ValueError("وضعیت فعالیت معتبر نیست.")
    if (
        target_status
        not in _ALLOWED_ACTIVITY_STATUS_TRANSITIONS[locked_activity.status]
    ):
        raise ValueError("این تغییر وضعیت برای فعالیت مجاز نیست.")
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
    _require_project_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.ACTIVITIES_ARCHIVE,
    )
    locked_activity = Activity.objects.select_for_update().get(pk=activity.pk)
    if locked_activity.organization_id != organization.id:
        raise PermissionDenied("فعالیت متعلق به این سازمان نیست.")
    if locked_activity.archived_at:
        raise ValueError("فعالیت از قبل بایگانی شده است.")
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
