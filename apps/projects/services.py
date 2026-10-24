import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from io import StringIO

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Max, QuerySet, Sum
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.authorization import (
    get_active_membership,
    has_business_permission,
    scope_queryset,
)
from apps.organizations.models import (
    BusinessPermissionCode,
    Organization,
    OrganizationSettings,
    OrganizationStatus,
)
from apps.projects.models import (
    Activity,
    ActivityStatus,
    BudgetAllocation,
    BudgetManifestDisposition,
    BudgetManifestLine,
    BudgetSourceManifest,
    BudgetVersion,
    BudgetVersionStatus,
    CBSNode,
    CostCenter,
    CostStructureStatus,
    CostStructureVersion,
    ForecastReviewStatus,
    Project,
    ProjectBudgetControl,
    ProjectChangeProposal,
    ProjectControlItem,
    ProjectControlItemKind,
    ProjectControlItemStatus,
    ProjectControlStatusEvent,
    ProjectCostCoverage,
    ProjectCostCoverageStatus,
    ProjectCostFact,
    ProjectCostFactKind,
    ProjectCostForecast,
    ProjectCostMeasure,
    ProjectCostSourceContract,
    ProjectCostSourceContractStatus,
    ProjectForecastReview,
    ProjectPhase,
    ProjectPhaseStatus,
    ProjectScheduleDependency,
    ProjectScheduleDependencyType,
    ProjectScheduleItem,
    ProjectScheduleRevision,
    ProjectSite,
    ProjectStatus,
    ScheduleRebaselineProposal,
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
    *,
    project: Project | None = None,
    site: ProjectSite | None = None,
    allow_any_scope: bool = False,
    allow_site_parent: bool = False,
) -> bool:
    return has_business_permission(
        user=user,
        organization=organization,
        permission=permission,
        project=project,
        site=site,
        allow_any_scope=allow_any_scope,
        allow_site_parent=allow_site_parent,
    )


def _require_project_management_access(
    *,
    organization: Organization,
    actor: User,
    permission: BusinessPermissionCode,
    project: Project | None = None,
    site: ProjectSite | None = None,
) -> None:
    if not actor.is_authenticated or not actor.is_active:
        raise PermissionDenied("ورود به حساب کاربری الزامی است.")
    if (
        organization.status != OrganizationStatus.ACTIVE
        or organization.deleted_at is not None
    ):
        raise PermissionDenied("سازمان فعال نیست.")
    if not _has_project_permission(
        actor, organization, permission, project=project, site=site
    ):
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
    estimated_budget: Decimal = Decimal("0.00"),
    actual_budget: Decimal = Decimal("0.00"),
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
    if estimated_budget < Decimal("0.00") or actual_budget < Decimal("0.00"):
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
        estimated_budget=estimated_budget,
        actual_budget=actual_budget,
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
        user,
        organization,
        BusinessPermissionCode.PROJECTS_VIEW,
        allow_any_scope=True,
    ):
        raise PermissionDenied("اجازه مشاهده پروژه‌های این سازمان را ندارید.")
    membership = get_active_membership(user=user, organization=organization)
    return (
        scope_queryset(
            Project.objects.filter(
                organization=organization,
                deleted_at__isnull=True,
            ),
            membership=membership,
            project_lookup="pk",
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
        actor,
        organization,
        BusinessPermissionCode.PROJECT_SITES_CREATE,
        project=project,
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

    try:
        project = Project.objects.get(
            pk=project_id, organization=organization, deleted_at__isnull=True
        )
    except Project.DoesNotExist as exc:
        raise PermissionDenied("پروژه در این سازمان یافت نشد.") from exc
    if not _has_project_permission(
        user,
        organization,
        BusinessPermissionCode.PROJECT_SITES_VIEW,
        project=project,
        allow_site_parent=True,
    ):
        raise PermissionDenied("اجازه مشاهده کارگاه‌های این سازمان را ندارید.")
    membership = get_active_membership(user=user, organization=organization)
    return scope_queryset(
        ProjectSite.objects.filter(
            organization=organization,
            project=project,
        ),
        membership=membership,
        project_lookup="project_id",
        site_lookup="pk",
    ).select_related("project")


def get_organization_sites(
    *,
    user: User,
    organization: Organization,
) -> QuerySet[ProjectSite]:
    """Return every worksite in the active organization."""

    if not _has_project_permission(
        user,
        organization,
        BusinessPermissionCode.PROJECT_SITES_VIEW,
        allow_any_scope=True,
    ):
        raise PermissionDenied("اجازه مشاهده کارگاه‌های این سازمان را ندارید.")
    membership = get_active_membership(user=user, organization=organization)
    return scope_queryset(
        ProjectSite.objects.filter(organization=organization),
        membership=membership,
        project_lookup="project_id",
        site_lookup="pk",
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
        actor,
        organization,
        BusinessPermissionCode.PROJECT_PHASES_CREATE,
        project=site.project,
        site=site,
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
        user,
        organization,
        BusinessPermissionCode.PROJECT_PHASES_VIEW,
        project=site.project,
        site=site,
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
    if not _has_project_permission(
        actor,
        organization,
        BusinessPermissionCode.PROJECT_PHASES_TRANSITION,
        project=site.project,
        site=site,
    ):
        raise PermissionDenied("اجازه تغییر فازهای پروژه در این سازمان را ندارید.")
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

    try:
        project = Project.objects.select_for_update().get(
            pk=project_id,
            organization=organization,
            deleted_at__isnull=True,
        )
    except Project.DoesNotExist as exc:
        raise PermissionDenied("پروژه در این سازمان یافت نشد.") from exc
    if not _has_project_permission(
        user,
        organization,
        BusinessPermissionCode.PROJECTS_ARCHIVE,
        project=project,
    ):
        raise PermissionDenied("اجازه بایگانی پروژه‌های این سازمان را ندارید.")
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
        project=project,
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
    locked_node = (
        WBSNode.objects.select_for_update().select_related("project").get(pk=node.pk)
    )
    if locked_node.organization_id != organization.id:
        raise PermissionDenied("گره ساختار شکست متعلق به این سازمان نیست.")
    _require_project_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.WBS_NODES_CHANGE,
        project=locked_node.project,
    )
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
        user,
        organization,
        BusinessPermissionCode.WBS_NODES_VIEW,
        project=project,
    ):
        raise PermissionDenied("اجازه مشاهده ساختار شکست این پروژه را ندارید.")
    return WBSNode.objects.filter(
        organization=organization, project=project, archived_at__isnull=True
    ).select_related("parent")


@transaction.atomic
def archive_wbs_node(
    *, organization: Organization, actor: User, node: WBSNode
) -> WBSNode:
    locked_node = (
        WBSNode.objects.select_for_update().select_related("project").get(pk=node.pk)
    )
    if locked_node.organization_id != organization.id:
        raise PermissionDenied("گره ساختار شکست متعلق به این سازمان نیست.")
    _require_project_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.WBS_NODES_ARCHIVE,
        project=locked_node.project,
    )
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
        project=project,
        site=site,
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
    try:
        project = Project.objects.get(
            pk=project_id, organization=organization, deleted_at__isnull=True
        )
    except Project.DoesNotExist as exc:
        raise PermissionDenied("پروژه در این سازمان یافت نشد.") from exc
    if not _has_project_permission(
        user,
        organization,
        BusinessPermissionCode.ACTIVITIES_VIEW,
        project=project,
        allow_site_parent=True,
    ):
        raise PermissionDenied("اجازه مشاهده فعالیت‌های این پروژه را ندارید.")
    membership = get_active_membership(user=user, organization=organization)
    return scope_queryset(
        Activity.objects.filter(
            organization=organization, project=project, archived_at__isnull=True
        ),
        membership=membership,
        project_lookup="project_id",
        site_lookup="site_id",
    ).select_related("wbs_node", "site", "phase", "unit_of_measure")


@transaction.atomic
def transition_activity_status(
    *, organization: Organization, actor: User, activity: Activity, target_status: str
) -> Activity:
    locked_activity = (
        Activity.objects.select_for_update(of=("self",))
        .select_related("project", "site")
        .get(pk=activity.pk)
    )
    if locked_activity.organization_id != organization.id:
        raise PermissionDenied("فعالیت متعلق به این سازمان نیست.")
    _require_project_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.ACTIVITIES_TRANSITION,
        project=locked_activity.project,
        site=locked_activity.site,
    )
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
    locked_activity = (
        Activity.objects.select_for_update(of=("self",))
        .select_related("project", "site")
        .get(pk=activity.pk)
    )
    if locked_activity.organization_id != organization.id:
        raise PermissionDenied("فعالیت متعلق به این سازمان نیست.")
    _require_project_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.ACTIVITIES_ARCHIVE,
        project=locked_activity.project,
        site=locked_activity.site,
    )
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


@dataclass(frozen=True, slots=True)
class BudgetAllocationInput:
    amount: Decimal
    cbs_node: CBSNode
    wbs_node: WBSNode
    cost_center: CostCenter | None
    allocation_basis_reference: str


@dataclass(frozen=True, slots=True)
class BudgetPlanEvidence:
    budget_id: str
    status: str
    currency: str
    source_total: Decimal
    accepted_total: Decimal
    pending_lines: int
    excluded_lines: int
    is_governing: bool
    source_revision_id: str
    payload_hash: str


@dataclass(frozen=True, slots=True)
class ProjectControlSnapshot:
    schedules: tuple[ProjectScheduleRevision, ...]
    register_items: tuple[ProjectControlItem, ...]
    change_proposals: tuple[ProjectChangeProposal, ...]
    rebaseline_proposals: tuple[ScheduleRebaselineProposal, ...]


@dataclass(frozen=True, slots=True)
class ProjectControlComparisonLine:
    cbs_code: str
    cbs_name: str
    wbs_code: str
    wbs_title: str
    cost_center_code: str
    accepted_budget_amount: Decimal
    approved_or_recorded_expense_amount: Decimal
    remaining_amount: Decimal


@dataclass(frozen=True, slots=True)
class ProjectControlComparison:
    budget_id: str
    currency: str
    lines: tuple[ProjectControlComparisonLine, ...]
    unallocated_expense_count: int
    unallocated_expense_amount: Decimal


@dataclass(frozen=True, slots=True)
class ProjectControlExceptionSnapshot:
    advisory_overruns: tuple[object, ...]
    open_register_items: tuple[ProjectControlItem, ...]


@dataclass(frozen=True, slots=True)
class ProjectCostReconciliationLine:
    cbs_code: str
    cbs_name: str
    wbs_code: str
    wbs_title: str
    cost_center_code: str
    accepted_budget_amount: Decimal | None
    approved_or_recorded_expense_amount: Decimal | None
    inert_project_cost_actual_amount: Decimal | None
    unresolved_difference: Decimal | None
    budget_allocation_count: int
    expense_allocation_count: int
    project_cost_fact_count: int


@dataclass(frozen=True, slots=True)
class ProjectCostReconciliationSource:
    contract_id: str
    producer_key: str
    version: int
    source_model: str
    reconciliation_policy_reference: str
    coverage_status: str
    watermark: str
    fact_count: int
    net_amount: Decimal | None
    cutoff_at: datetime | None = None
    missing_facts: bool = False


@dataclass(frozen=True, slots=True)
class ProjectCostReconciliationExclusion:
    code: str
    disposition: str
    count: int
    amount: Decimal | None
    note: str


@dataclass(frozen=True, slots=True)
class ProjectCostReconciliation:
    budget_id: str
    budget_payload_hash: str
    currency: str
    lines: tuple[ProjectCostReconciliationLine, ...]
    sources: tuple[ProjectCostReconciliationSource, ...]
    exclusions: tuple[ProjectCostReconciliationExclusion, ...]
    accepted_budget_total: Decimal | None
    approved_or_recorded_expense_total: Decimal | None
    inert_project_cost_actual_total: Decimal | None
    unresolved_total_difference: Decimal | None
    coverage_complete: bool
    source_equivalence_established: bool


def _require_budget_access(
    *,
    organization: Organization,
    actor: User,
    project: Project,
    permission: BusinessPermissionCode,
) -> None:
    _require_project_management_access(
        organization=organization,
        actor=actor,
        permission=permission,
        project=project,
    )
    if project.organization_id != organization.pk or project.deleted_at is not None:
        raise PermissionDenied(
            "The project does not belong to the active organization."
        )


@transaction.atomic
def create_cost_structure_version(
    *,
    organization: Organization,
    actor: User,
    code: str,
    version: int,
    name: str,
    governance_reference: str,
) -> CostStructureVersion:
    _require_project_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.COST_STRUCTURES_MANAGE,
    )
    structure = CostStructureVersion(
        organization=organization,
        code=code,
        version=version,
        name=name,
        governance_reference=governance_reference,
        created_by=actor,
    )
    structure.save()
    return structure


@transaction.atomic
def add_cbs_node(
    *,
    structure: CostStructureVersion,
    actor: User,
    code: str,
    name: str,
    parent: CBSNode | None = None,
    is_leaf: bool = True,
    sort_order: int = 0,
) -> CBSNode:
    structure = CostStructureVersion.objects.select_for_update().get(pk=structure.pk)
    _require_project_management_access(
        organization=structure.organization,
        actor=actor,
        permission=BusinessPermissionCode.COST_STRUCTURES_MANAGE,
    )
    if structure.status != CostStructureStatus.DRAFT:
        raise ValueError("A locked cost structure cannot be changed.")
    if parent and parent.structure_version_id != structure.pk:
        raise PermissionDenied("The CBS parent belongs to another structure version.")
    return CBSNode.objects.create(
        organization=structure.organization,
        structure_version=structure,
        parent=parent,
        code=code,
        name=name,
        is_leaf=is_leaf,
        sort_order=sort_order,
    )


@transaction.atomic
def add_cost_center(
    *, structure: CostStructureVersion, actor: User, code: str, name: str
) -> CostCenter:
    structure = CostStructureVersion.objects.select_for_update().get(pk=structure.pk)
    _require_project_management_access(
        organization=structure.organization,
        actor=actor,
        permission=BusinessPermissionCode.COST_STRUCTURES_MANAGE,
    )
    if structure.status != CostStructureStatus.DRAFT:
        raise ValueError("A locked cost structure cannot be changed.")
    return CostCenter.objects.create(
        organization=structure.organization,
        structure_version=structure,
        code=code,
        name=name,
    )


@transaction.atomic
def lock_cost_structure_version(
    *, structure: CostStructureVersion, actor: User
) -> CostStructureVersion:
    structure = CostStructureVersion.objects.select_for_update().get(pk=structure.pk)
    _require_project_management_access(
        organization=structure.organization,
        actor=actor,
        permission=BusinessPermissionCode.COST_STRUCTURES_MANAGE,
    )
    if structure.status == CostStructureStatus.LOCKED:
        return structure
    if not structure.cbs_nodes.filter(is_leaf=True).exists():
        raise ValueError("A cost structure requires at least one CBS leaf.")
    structure.status = CostStructureStatus.LOCKED
    structure.locked_by = actor
    structure.locked_at = timezone.now()
    structure.save(update_fields=["status", "locked_by", "locked_at", "updated_at"])
    return structure


def _same_budget_request(
    budget: BudgetVersion,
    *,
    source_revision_id: object,
    structure_id: object,
    predecessor_id: object,
    governance_reference: str,
    rounding_policy_reference: str,
    cost_center_required: bool,
    reason: str,
) -> bool:
    return (
        budget.source_manifest.estimate_revision_id == source_revision_id
        and budget.structure_version_id == structure_id
        and budget.predecessor_id == predecessor_id
        and budget.governance_reference == governance_reference.strip()
        and budget.rounding_policy_reference == rounding_policy_reference.strip()
        and budget.cost_center_required is cost_center_required
        and budget.reason == reason.strip()
    )


@transaction.atomic
def create_budget_draft_from_estimate(
    *,
    organization: Organization,
    project: Project,
    actor: User,
    estimate_revision: object,
    structure: CostStructureVersion,
    handoff_id: str,
    submission_version: int,
    governance_reference: str,
    rounding_policy_reference: str,
    cost_center_required: bool,
    reason: str,
    predecessor: BudgetVersion | None = None,
) -> BudgetVersion:
    """Create a complete pending manifest without applying any financial policy."""
    from apps.estimates.models import EstimateRevision, EstimateRevisionStatus

    locked_project = Project.objects.select_for_update().get(pk=project.pk)
    _require_budget_access(
        organization=organization,
        actor=actor,
        project=locked_project,
        permission=BusinessPermissionCode.BUDGETS_PREPARE,
    )
    source = (
        EstimateRevision.objects.select_related(
            "estimate", "estimate__current_revision"
        )
        .prefetch_related("items", "items__unit_of_measure")
        .get(pk=estimate_revision.pk)
    )
    if (
        source.organization_id != organization.pk
        or source.estimate.project_id != locked_project.pk
        or source.status != EstimateRevisionStatus.APPROVED
        or source.estimate.current_revision_id != source.pk
    ):
        raise PermissionDenied(
            "Only the current approved revision for this project is eligible."
        )
    structure = CostStructureVersion.objects.select_for_update().get(pk=structure.pk)
    if structure.organization_id != organization.pk:
        raise PermissionDenied("The cost structure belongs to another organization.")
    if structure.status != CostStructureStatus.LOCKED:
        raise ValueError(
            "P4-G07: the selected cost structure must be explicitly locked."
        )
    try:
        currency = OrganizationSettings.objects.get(organization=organization).currency
    except OrganizationSettings.DoesNotExist as exc:
        raise ValueError(
            "P4-G08: authoritative Tenant currency configuration is required."
        ) from exc
    existing = BudgetVersion.objects.filter(
        organization=organization,
        project=locked_project,
        handoff_id=handoff_id.strip(),
        submission_version=submission_version,
    ).first()
    if existing:
        existing = BudgetVersion.objects.select_related("source_manifest").get(
            pk=existing.pk
        )
        if _same_budget_request(
            existing,
            source_revision_id=source.pk,
            structure_id=structure.pk,
            predecessor_id=getattr(predecessor, "pk", None),
            governance_reference=governance_reference,
            rounding_policy_reference=rounding_policy_reference,
            cost_center_required=cost_center_required,
            reason=reason,
        ):
            return existing
        raise ValueError(
            "The handoff identity already exists with a different payload."
        )
    version_number = (
        BudgetVersion.objects.filter(project=locked_project).aggregate(
            value=Max("version_number")
        )["value"]
        or 0
    ) + 1
    budget = BudgetVersion.objects.create(
        organization=organization,
        project=locked_project,
        version_number=version_number,
        predecessor=predecessor,
        structure_version=structure,
        handoff_id=handoff_id,
        submission_version=submission_version,
        currency=currency,
        rounding_policy_reference=rounding_policy_reference,
        governance_reference=governance_reference,
        cost_center_required=cost_center_required,
        reason=reason,
        created_by=actor,
    )
    manifest = BudgetSourceManifest.objects.create(
        organization=organization,
        budget=budget,
        estimate=source.estimate,
        estimate_revision=source,
        estimate_revision_number=source.revision_number,
        source_reference=f"estimate:{source.estimate_id}:revision:{source.pk}",
    )
    lines = [
        BudgetManifestLine(
            organization=organization,
            manifest=manifest,
            estimate_item=item,
            source_description=item.description,
            source_quantity=item.quantity,
            source_unit=(
                item.unit_of_measure.code if item.unit_of_measure_id else item.unit
            ),
            source_unit_price=item.unit_price,
            source_amount=item.line_total,
        )
        for item in source.items.all()
    ]
    if not lines:
        raise ValueError("The approved estimate revision has no source lines.")
    BudgetManifestLine.objects.bulk_create(lines)
    record_audit_event(
        action=AuditAction.BUDGET_DRAFT_CREATED,
        entity_type="budget_version",
        entity_id=budget.pk,
        organization=organization,
        actor=actor,
        metadata={"project_id": str(project.pk), "source_revision_id": str(source.pk)},
    )
    return budget


@transaction.atomic
def classify_budget_manifest_line(
    *,
    line: BudgetManifestLine,
    actor: User,
    allocations: tuple[BudgetAllocationInput, ...] = (),
    exclusion_reason: str = "",
) -> BudgetManifestLine:
    line = (
        BudgetManifestLine.objects.select_for_update()
        .select_related(
            "manifest__budget__project", "manifest__budget__structure_version"
        )
        .get(pk=line.pk)
    )
    budget = line.manifest.budget
    _require_budget_access(
        organization=budget.organization,
        actor=actor,
        project=budget.project,
        permission=BusinessPermissionCode.BUDGETS_PREPARE,
    )
    if budget.status != BudgetVersionStatus.DRAFT:
        raise ValueError("Only a draft budget manifest can be classified.")
    line.allocations.all().delete()
    if exclusion_reason.strip():
        if allocations:
            raise ValueError("An excluded source line cannot have allocations.")
        line.disposition = BudgetManifestDisposition.EXCLUDED
        line.exclusion_reason = exclusion_reason.strip()
        line.save(update_fields=["disposition", "exclusion_reason", "updated_at"])
        return line
    if not allocations:
        raise ValueError("An included source line requires at least one allocation.")
    if (
        sum((entry.amount for entry in allocations), Decimal("0.00"))
        != line.source_amount
    ):
        raise ValueError("Allocations must exactly conserve the source-line amount.")
    for sequence, entry in enumerate(allocations, start=1):
        if entry.amount <= 0 or not entry.allocation_basis_reference.strip():
            raise ValueError(
                "Each allocation requires a positive amount and explicit basis reference."
            )
        if (
            entry.cbs_node.organization_id != budget.organization_id
            or entry.cbs_node.structure_version_id != budget.structure_version_id
            or not entry.cbs_node.is_leaf
        ):
            raise PermissionDenied("The CBS mapping must use a selected-version leaf.")
        if (
            entry.wbs_node.organization_id != budget.organization_id
            or entry.wbs_node.project_id != budget.project_id
            or not entry.wbs_node.is_active
            or entry.wbs_node.archived_at is not None
        ):
            raise PermissionDenied(
                "The WBS mapping must use an active node in this project."
            )
        if budget.cost_center_required and entry.cost_center is None:
            raise ValueError(
                "P4-G07: this explicitly governed handoff requires a cost center."
            )
        if entry.cost_center and (
            entry.cost_center.organization_id != budget.organization_id
            or entry.cost_center.structure_version_id != budget.structure_version_id
        ):
            raise PermissionDenied(
                "The cost center belongs to another structure version."
            )
        BudgetAllocation.objects.create(
            organization=budget.organization,
            manifest_line=line,
            sequence=sequence,
            amount=entry.amount,
            cbs_node=entry.cbs_node,
            wbs_node=entry.wbs_node,
            cost_center=entry.cost_center,
            allocation_basis_reference=entry.allocation_basis_reference,
        )
    line.disposition = BudgetManifestDisposition.INCLUDED
    line.exclusion_reason = ""
    line.save(update_fields=["disposition", "exclusion_reason", "updated_at"])
    return line


def _budget_payload_hash(budget: BudgetVersion) -> str:
    rows = list(
        BudgetAllocation.objects.filter(manifest_line__manifest__budget=budget)
        .order_by("manifest_line_id", "sequence")
        .values_list(
            "manifest_line_id",
            "amount",
            "cbs_node_id",
            "wbs_node_id",
            "cost_center_id",
            "allocation_basis_reference",
        )
    )
    manifest = list(
        budget.source_manifest.lines.order_by("estimate_item_id").values_list(
            "estimate_item_id", "source_amount", "disposition", "exclusion_reason"
        )
    )
    payload = {
        "budget": [
            str(budget.pk),
            budget.currency,
            budget.rounding_policy_reference,
            budget.governance_reference,
            budget.cost_center_required,
            str(budget.predecessor_id or ""),
        ],
        "manifest": [[str(value) for value in row] for row in manifest],
        "allocations": [[str(value or "") for value in row] for row in rows],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@transaction.atomic
def submit_budget_version(*, budget: BudgetVersion, actor: User) -> BudgetVersion:
    budget = (
        BudgetVersion.objects.select_for_update(of=("self",))
        .select_related("project", "source_manifest")
        .get(pk=budget.pk)
    )
    _require_budget_access(
        organization=budget.organization,
        actor=actor,
        project=budget.project,
        permission=BusinessPermissionCode.BUDGETS_SUBMIT,
    )
    if budget.status == BudgetVersionStatus.SUBMITTED:
        return budget
    if budget.status != BudgetVersionStatus.DRAFT:
        raise ValueError("Only a draft budget can be submitted.")
    lines = budget.source_manifest.lines.all()
    if lines.filter(disposition=BudgetManifestDisposition.PENDING).exists():
        raise ValueError("Every estimate source line requires an explicit disposition.")
    if not lines.filter(disposition=BudgetManifestDisposition.INCLUDED).exists():
        raise ValueError("A budget requires at least one included source line.")
    for line in lines.filter(disposition=BudgetManifestDisposition.INCLUDED):
        total = line.allocations.aggregate(value=Sum("amount"))["value"] or Decimal(
            "0.00"
        )
        if total != line.source_amount:
            raise ValueError("Budget allocation conservation failed.")
    budget.payload_hash = _budget_payload_hash(budget)
    budget.status = BudgetVersionStatus.SUBMITTED
    budget.submitted_by = actor
    budget.submitted_at = timezone.now()
    budget.save(
        update_fields=[
            "payload_hash",
            "status",
            "submitted_by",
            "submitted_at",
            "updated_at",
        ]
    )
    record_audit_event(
        action=AuditAction.BUDGET_SUBMITTED,
        entity_type="budget_version",
        entity_id=budget.pk,
        organization=budget.organization,
        actor=actor,
        metadata={"payload_hash": budget.payload_hash},
    )
    return budget


@transaction.atomic
def accept_budget_version(
    *, budget: BudgetVersion, actor: User, approval_reason: str
) -> BudgetVersion:
    budget = (
        BudgetVersion.objects.select_for_update()
        .select_related("project")
        .get(pk=budget.pk)
    )
    _require_budget_access(
        organization=budget.organization,
        actor=actor,
        project=budget.project,
        permission=BusinessPermissionCode.BUDGETS_ACCEPT,
    )
    if budget.status == BudgetVersionStatus.ACCEPTED:
        return budget
    if budget.status != BudgetVersionStatus.SUBMITTED:
        raise ValueError("Only a submitted budget can be accepted.")
    if budget.submitted_by_id == actor.pk:
        raise PermissionDenied("Budget self-approval is prohibited.")
    if not approval_reason.strip():
        raise ValueError("An approval reason is required.")
    Project.objects.select_for_update().get(pk=budget.project_id)
    control, _ = ProjectBudgetControl.objects.select_for_update().get_or_create(
        organization=budget.organization, project=budget.project
    )
    if control.governing_budget_id != budget.predecessor_id:
        raise ValueError(
            "The governing budget changed; the submitted predecessor is stale."
        )
    if _budget_payload_hash(budget) != budget.payload_hash:
        raise ValueError("The submitted budget payload changed and cannot be accepted.")
    budget.status = BudgetVersionStatus.ACCEPTED
    budget.accepted_by = actor
    budget.accepted_at = timezone.now()
    budget.save(update_fields=["status", "accepted_by", "accepted_at", "updated_at"])
    control.governing_budget = budget
    control.full_clean()
    control.save(update_fields=["governing_budget", "updated_at"])
    record_audit_event(
        action=AuditAction.BUDGET_ACCEPTED,
        entity_type="budget_version",
        entity_id=budget.pk,
        organization=budget.organization,
        actor=actor,
        metadata={
            "approval_reason": approval_reason.strip(),
            "predecessor_id": str(budget.predecessor_id or ""),
            "payload_hash": budget.payload_hash,
        },
    )
    return budget


def get_budget_plan_evidence(
    *, budget: BudgetVersion, actor: User
) -> BudgetPlanEvidence:
    budget = BudgetVersion.objects.select_related(
        "project", "source_manifest", "project__budget_control"
    ).get(pk=budget.pk)
    _require_budget_access(
        organization=budget.organization,
        actor=actor,
        project=budget.project,
        permission=BusinessPermissionCode.BUDGETS_VIEW,
    )
    lines = budget.source_manifest.lines
    source_total = lines.filter(
        disposition=BudgetManifestDisposition.INCLUDED
    ).aggregate(value=Sum("source_amount"))["value"] or Decimal("0.00")
    accepted_total = BudgetAllocation.objects.filter(
        manifest_line__manifest__budget=budget
    ).aggregate(value=Sum("amount"))["value"] or Decimal("0.00")
    try:
        governing_id = budget.project.budget_control.governing_budget_id
    except ProjectBudgetControl.DoesNotExist:
        governing_id = None
    return BudgetPlanEvidence(
        budget_id=str(budget.pk),
        status=budget.status,
        currency=budget.currency,
        source_total=source_total,
        accepted_total=accepted_total,
        pending_lines=lines.filter(
            disposition=BudgetManifestDisposition.PENDING
        ).count(),
        excluded_lines=lines.filter(
            disposition=BudgetManifestDisposition.EXCLUDED
        ).count(),
        is_governing=governing_id == budget.pk,
        source_revision_id=str(budget.source_manifest.estimate_revision_id),
        payload_hash=budget.payload_hash,
    )


@dataclass(frozen=True, slots=True)
class ProjectCostProjection:
    currency: str
    authorized_commitment: Decimal
    relieved_commitment: Decimal
    open_commitment: Decimal
    accrual: Decimal
    actual_cost: Decimal
    coverage_complete: bool
    coverage: tuple[ProjectCostCoverage, ...]
    facts: tuple[ProjectCostFact, ...]


def _stable_payload_hash(payload: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()


@transaction.atomic
def create_project_cost_source_contract(
    *,
    organization: Organization,
    actor: User,
    producer_key: str,
    version: int,
    measure: str,
    source_model: str,
    event_schema: str,
    classification_policy_reference: str,
    recognition_policy_reference: str,
    reconciliation_policy_reference: str,
    requires_financial_evidence: bool,
) -> ProjectCostSourceContract:
    """Create an inert producer contract; facts remain blocked until independent approval."""
    _require_project_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.PROJECT_COST_SOURCES_MANAGE,
    )
    payload = {
        "producer_key": producer_key.strip().lower(),
        "version": version,
        "measure": measure,
        "source_model": source_model.strip().lower(),
        "event_schema": event_schema.strip(),
        "classification_policy_reference": classification_policy_reference.strip(),
        "recognition_policy_reference": recognition_policy_reference.strip(),
        "reconciliation_policy_reference": reconciliation_policy_reference.strip(),
        "requires_financial_evidence": requires_financial_evidence,
    }
    payload_hash = _stable_payload_hash(payload)
    existing = ProjectCostSourceContract.objects.filter(
        organization=organization,
        producer_key=payload["producer_key"],
        version=version,
    ).first()
    if existing:
        if existing.payload_hash == payload_hash:
            return existing
        raise ValueError("The producer contract identity has a different payload.")
    try:
        with transaction.atomic():
            contract = ProjectCostSourceContract.objects.create(
                organization=organization,
                created_by=actor,
                payload_hash=payload_hash,
                **payload,
            )
    except IntegrityError as exc:
        retry = ProjectCostSourceContract.objects.filter(
            organization=organization,
            producer_key=payload["producer_key"],
            version=version,
        ).first()
        if retry and retry.payload_hash == payload_hash:
            return retry
        raise ValueError(
            "The producer contract identity has a different payload."
        ) from exc
    record_audit_event(
        action=AuditAction.PROJECT_COST_SOURCE_DRAFTED,
        entity_type="project_cost_source_contract",
        entity_id=contract.pk,
        organization=organization,
        actor=actor,
        metadata={"producer_key": contract.producer_key, "version": version},
    )
    return contract


@transaction.atomic
def approve_project_cost_source_contract(
    *, contract: ProjectCostSourceContract, actor: User
) -> ProjectCostSourceContract:
    contract = ProjectCostSourceContract.objects.select_for_update().get(pk=contract.pk)
    _require_project_management_access(
        organization=contract.organization,
        actor=actor,
        permission=BusinessPermissionCode.PROJECT_COST_SOURCES_APPROVE,
    )
    if contract.status == ProjectCostSourceContractStatus.APPROVED:
        return contract
    if contract.created_by_id == actor.pk:
        raise PermissionDenied("The producer-contract maker cannot approve it.")
    contract.status = ProjectCostSourceContractStatus.APPROVED
    contract.approved_by = actor
    contract.approved_at = timezone.now()
    contract.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    record_audit_event(
        action=AuditAction.PROJECT_COST_SOURCE_APPROVED,
        entity_type="project_cost_source_contract",
        entity_id=contract.pk,
        organization=contract.organization,
        actor=actor,
        metadata={"payload_hash": contract.payload_hash},
    )
    return contract


def _expected_measure_for_kind(kind: str) -> str:
    if kind.startswith("commitment_"):
        return ProjectCostMeasure.COMMITMENT
    if kind.startswith("accrual_"):
        return ProjectCostMeasure.ACCRUAL
    if kind.startswith("actual_"):
        return ProjectCostMeasure.ACTUAL
    raise ValueError("Unsupported project-cost fact kind.")


def _validate_cost_dimensions(
    *,
    project: Project,
    budget: BudgetVersion,
    cbs_node: CBSNode,
    wbs_node: WBSNode,
    cost_center: CostCenter | None,
) -> None:
    if budget.project_id != project.pk or budget.status != BudgetVersionStatus.ACCEPTED:
        raise PermissionDenied("Classification requires the governing accepted budget.")
    if (
        cbs_node.organization_id != project.organization_id
        or cbs_node.structure_version_id != budget.structure_version_id
        or not cbs_node.is_leaf
        or wbs_node.organization_id != project.organization_id
        or wbs_node.project_id != project.pk
        or not wbs_node.is_active
        or wbs_node.archived_at is not None
    ):
        raise PermissionDenied(
            "Cost classification is outside the project budget scope."
        )
    if budget.cost_center_required and cost_center is None:
        raise ValueError("The governing budget requires a cost center.")
    if cost_center and (
        cost_center.organization_id != project.organization_id
        or cost_center.structure_version_id != budget.structure_version_id
    ):
        raise PermissionDenied("The cost center is outside the selected structure.")


@transaction.atomic
def record_project_cost_fact(
    *,
    organization: Organization,
    project: Project,
    actor: User,
    contract: ProjectCostSourceContract,
    kind: str,
    source_id: str,
    source_version: str,
    source_line_id: str,
    economic_event_id: str,
    occurrence_id: str,
    recognition_date: date,
    currency: str,
    amount: Decimal,
    cbs_node: CBSNode,
    wbs_node: WBSNode,
    cost_center: CostCenter | None,
    classification_version: str,
    valuation_reference: str,
    financial_evidence_reference: str = "",
    reverses: ProjectCostFact | None = None,
    replaces_accrual: ProjectCostFact | None = None,
) -> ProjectCostFact:
    """Append one idempotent projection fact; never changes its producer or GL."""
    project = Project.objects.select_for_update().get(pk=project.pk)
    _require_budget_access(
        organization=organization,
        actor=actor,
        project=project,
        permission=BusinessPermissionCode.PROJECT_COST_FACTS_RECORD,
    )
    contract = ProjectCostSourceContract.objects.select_for_update().get(pk=contract.pk)
    if (
        contract.organization_id != organization.pk
        or contract.status != ProjectCostSourceContractStatus.APPROVED
        or contract.measure != _expected_measure_for_kind(kind)
    ):
        raise PermissionDenied("No approved producer contract covers this fact kind.")
    control = (
        ProjectBudgetControl.objects.select_for_update(of=("self",))
        .select_related("governing_budget")
        .get(organization=organization, project=project)
    )
    budget = control.governing_budget
    if budget is None:
        raise ValueError("A governing accepted budget is required.")
    _validate_cost_dimensions(
        project=project,
        budget=budget,
        cbs_node=cbs_node,
        wbs_node=wbs_node,
        cost_center=cost_center,
    )
    if canonicalize_upper_identifier(currency) != budget.currency:
        raise ValueError("P4-G08: fact currency must match the governing budget.")
    if amount == 0:
        raise ValueError("A project-cost fact amount cannot be zero.")
    positive_kinds = {
        ProjectCostFactKind.COMMITMENT_AUTHORIZED,
        ProjectCostFactKind.COMMITMENT_RELIEF,
        ProjectCostFactKind.ACCRUAL_RECOGNIZED,
        ProjectCostFactKind.ACTUAL_RECOGNIZED,
    }
    if kind in positive_kinds and amount < 0:
        raise ValueError("Recognition and relief amounts must be positive.")
    if (
        contract.requires_financial_evidence
        and not financial_evidence_reference.strip()
    ):
        raise ValueError("This contract requires explicit financial evidence.")
    reversal_kinds = {
        ProjectCostFactKind.ACCRUAL_REVERSAL,
        ProjectCostFactKind.ACTUAL_REVERSAL,
    }
    if (kind in reversal_kinds) != bool(reverses):
        raise ValueError("Reversal facts require exactly one original fact.")
    related_ids = sorted(
        {
            item.pk
            for item in (reverses, replaces_accrual)
            if item is not None
        },
        key=str,
    )
    locked_related = {
        fact.pk: fact
        for fact in ProjectCostFact.objects.select_for_update()
        .filter(
            organization=organization,
            project=project,
            pk__in=related_ids,
        )
        .order_by("pk")
    }
    if reverses is not None:
        reverses = locked_related.get(reverses.pk)
        if reverses is None:
            raise PermissionDenied("The reversal source is outside this project scope.")
    if replaces_accrual is not None:
        replaces_accrual = locked_related.get(replaces_accrual.pk)
        if replaces_accrual is None:
            raise PermissionDenied("The accrual source is outside this project scope.")
    expected_original_kind = {
        ProjectCostFactKind.ACCRUAL_REVERSAL: ProjectCostFactKind.ACCRUAL_RECOGNIZED,
        ProjectCostFactKind.ACTUAL_REVERSAL: ProjectCostFactKind.ACTUAL_RECOGNIZED,
    }.get(kind)
    if reverses and (
        reverses.contract_id != contract.pk
        or reverses.kind != expected_original_kind
        or reverses.amount != -amount
        or hasattr(reverses, "reversal")
        or reverses.currency != canonicalize_upper_identifier(currency)
        or reverses.cbs_node_id != cbs_node.pk
        or reverses.wbs_node_id != wbs_node.pk
        or reverses.cost_center_id != getattr(cost_center, "pk", None)
        or reverses.economic_event_id != economic_event_id.strip()
    ):
        raise ValueError(
            "The reversal must exactly offset the original kind and coded dimension."
        )
    if replaces_accrual and (
        kind != ProjectCostFactKind.ACTUAL_RECOGNIZED
        or replaces_accrual.kind != ProjectCostFactKind.ACCRUAL_RECOGNIZED
        or not hasattr(replaces_accrual, "reversal")
        or replaces_accrual.currency != canonicalize_upper_identifier(currency)
        or replaces_accrual.cbs_node_id != cbs_node.pk
        or replaces_accrual.wbs_node_id != wbs_node.pk
        or replaces_accrual.cost_center_id != getattr(cost_center, "pk", None)
    ):
        raise ValueError(
            "An actual may replace only an already reversed accrual in the same coded dimension."
        )
    payload = {
        "project": str(project.pk),
        "contract": str(contract.pk),
        "kind": kind,
        "source_id": source_id.strip(),
        "source_version": source_version.strip(),
        "source_line_id": source_line_id.strip(),
        "economic_event_id": economic_event_id.strip(),
        "occurrence_id": occurrence_id.strip(),
        "recognition_date": recognition_date,
        "currency": currency,
        "amount": amount,
        "cbs_node": str(cbs_node.pk),
        "wbs_node": str(wbs_node.pk),
        "cost_center": str(getattr(cost_center, "pk", "")),
        "classification_version": classification_version.strip(),
        "valuation_reference": valuation_reference.strip(),
        "financial_evidence_reference": financial_evidence_reference.strip(),
        "reverses": str(getattr(reverses, "pk", "")),
        "replaces_accrual": str(getattr(replaces_accrual, "pk", "")),
    }
    if not all(
        payload[key]
        for key in (
            "source_id",
            "source_version",
            "source_line_id",
            "economic_event_id",
            "occurrence_id",
            "classification_version",
            "valuation_reference",
        )
    ):
        raise ValueError("Complete source and classification lineage is required.")
    payload_hash = _stable_payload_hash(payload)
    existing = ProjectCostFact.objects.filter(
        organization=organization,
        contract=contract,
        occurrence_id=occurrence_id.strip(),
    ).first()
    if existing:
        if existing.payload_hash == payload_hash:
            return existing
        raise ValueError("The occurrence identity has a different payload.")
    if kind == ProjectCostFactKind.COMMITMENT_RELIEF:
        event_facts = ProjectCostFact.objects.select_for_update().filter(
            organization=organization,
            project=project,
            economic_event_id=economic_event_id.strip(),
            currency=canonicalize_upper_identifier(currency),
            cbs_node=cbs_node,
            wbs_node=wbs_node,
            cost_center=cost_center,
        )
        authorized = sum(
            (
                f.amount
                for f in event_facts
                if f.kind
                in {
                    ProjectCostFactKind.COMMITMENT_AUTHORIZED,
                    ProjectCostFactKind.COMMITMENT_ADJUSTMENT,
                }
            ),
            Decimal("0.00"),
        )
        relieved = sum(
            (f.amount for f in event_facts if f.kind == kind), Decimal("0.00")
        )
        if amount < 0 or relieved + amount > authorized:
            raise ValueError("Commitment relief cannot exceed the authorized amount.")
    if kind == ProjectCostFactKind.COMMITMENT_ADJUSTMENT:
        event_facts = ProjectCostFact.objects.select_for_update().filter(
            organization=organization,
            project=project,
            economic_event_id=economic_event_id.strip(),
            currency=canonicalize_upper_identifier(currency),
            cbs_node=cbs_node,
            wbs_node=wbs_node,
            cost_center=cost_center,
        )
        authorized = sum(
            (
                f.amount
                for f in event_facts
                if f.kind
                in {
                    ProjectCostFactKind.COMMITMENT_AUTHORIZED,
                    ProjectCostFactKind.COMMITMENT_ADJUSTMENT,
                }
            ),
            Decimal("0.00"),
        )
        relieved = sum(
            (
                f.amount
                for f in event_facts
                if f.kind == ProjectCostFactKind.COMMITMENT_RELIEF
            ),
            Decimal("0.00"),
        )
        if authorized + amount < relieved:
            raise ValueError(
                "A commitment adjustment cannot reduce below relieved work."
            )
    fact = ProjectCostFact.objects.create(
        organization=organization,
        project=project,
        contract=contract,
        kind=kind,
        source_id=source_id,
        source_version=source_version,
        source_line_id=source_line_id,
        economic_event_id=economic_event_id,
        occurrence_id=occurrence_id,
        recognition_date=recognition_date,
        currency=currency,
        amount=amount,
        cbs_node=cbs_node,
        wbs_node=wbs_node,
        cost_center=cost_center,
        classification_version=classification_version,
        valuation_reference=valuation_reference,
        financial_evidence_reference=financial_evidence_reference,
        reverses=reverses,
        replaces_accrual=replaces_accrual,
        payload_hash=payload_hash,
        recorded_by=actor,
    )
    record_audit_event(
        action=AuditAction.PROJECT_COST_FACT_RECORDED,
        entity_type="project_cost_fact",
        entity_id=fact.pk,
        organization=organization,
        actor=actor,
        metadata={
            "kind": kind,
            "project_id": str(project.pk),
            "occurrence_id": occurrence_id,
        },
    )
    return fact


@transaction.atomic
def set_project_cost_coverage(
    *,
    organization: Organization,
    project: Project,
    actor: User,
    contract: ProjectCostSourceContract,
    status: str,
    watermark: str = "",
    exception_note: str = "",
) -> ProjectCostCoverage:
    project = Project.objects.select_for_update().get(pk=project.pk)
    _require_budget_access(
        organization=organization,
        actor=actor,
        project=project,
        permission=BusinessPermissionCode.PROJECT_COST_SOURCES_MANAGE,
    )
    contract = ProjectCostSourceContract.objects.select_for_update().get(
        pk=contract.pk
    )
    if (
        contract.organization_id != organization.pk
        or contract.status != ProjectCostSourceContractStatus.APPROVED
    ):
        raise PermissionDenied("Coverage requires an approved Tenant source contract.")
    if status == ProjectCostCoverageStatus.COMPLETE:
        raise ValueError(
            "Complete production coverage is fail-closed until producer activation "
            "and cutoff are approved."
        )
    coverage = (
        ProjectCostCoverage.objects.select_for_update()
        .filter(project=project, contract=contract)
        .first()
    )
    values = {
        "organization": organization,
        "status": status,
        "watermark": watermark.strip(),
        "exception_note": exception_note.strip(),
        "cutoff_at": timezone.now() if watermark.strip() else None,
    }
    if coverage is None:
        coverage = ProjectCostCoverage.objects.create(
            project=project, contract=contract, **values
        )
    else:
        for field, value in values.items():
            setattr(coverage, field, value)
        coverage.save(
            update_fields=[
                "organization",
                "status",
                "watermark",
                "exception_note",
                "cutoff_at",
                "updated_at",
            ]
        )
    record_audit_event(
        action=AuditAction.PROJECT_COST_COVERAGE_CHANGED,
        entity_type="project_cost_coverage",
        entity_id=coverage.pk,
        organization=organization,
        actor=actor,
        metadata={"status": status, "project_id": str(project.pk)},
    )
    return coverage


def get_project_cost_projection(
    *,
    organization: Organization,
    project: Project,
    actor: User,
    cutoff: date | None = None,
) -> ProjectCostProjection:
    _require_budget_access(
        organization=organization,
        actor=actor,
        project=project,
        permission=BusinessPermissionCode.PROJECT_COSTS_VIEW,
    )
    facts_qs = ProjectCostFact.objects.filter(
        organization=organization, project=project
    ).select_related("contract", "cbs_node", "wbs_node", "cost_center")
    if cutoff:
        facts_qs = facts_qs.filter(recognition_date__lte=cutoff)
    facts = tuple(facts_qs.order_by("recognition_date", "created_at", "pk"))
    authorized = sum(
        (
            f.amount
            for f in facts
            if f.kind
            in {
                ProjectCostFactKind.COMMITMENT_AUTHORIZED,
                ProjectCostFactKind.COMMITMENT_ADJUSTMENT,
            }
        ),
        Decimal("0.00"),
    )
    relieved = sum(
        (f.amount for f in facts if f.kind == ProjectCostFactKind.COMMITMENT_RELIEF),
        Decimal("0.00"),
    )
    accrual = sum(
        (
            f.amount
            for f in facts
            if f.kind
            in {
                ProjectCostFactKind.ACCRUAL_RECOGNIZED,
                ProjectCostFactKind.ACCRUAL_REVERSAL,
            }
        ),
        Decimal("0.00"),
    )
    actual = sum(
        (
            f.amount
            for f in facts
            if f.kind
            in {
                ProjectCostFactKind.ACTUAL_RECOGNIZED,
                ProjectCostFactKind.ACTUAL_REVERSAL,
            }
        ),
        Decimal("0.00"),
    )
    coverage = tuple(
        ProjectCostCoverage.objects.filter(organization=organization, project=project)
        .select_related("contract")
        .order_by("contract__producer_key", "contract__version")
    )
    # P4 production coverage/cutoff is not approved. Retained COMPLETE values are
    # not trusted as certification until that separately authorized switch.
    complete = False
    try:
        currency = project.budget_control.governing_budget.currency
    except (ProjectBudgetControl.DoesNotExist, AttributeError):
        currency = ""
    return ProjectCostProjection(
        currency,
        authorized,
        relieved,
        authorized - relieved,
        accrual,
        actual,
        complete,
        coverage,
        facts,
    )


def _reconciliation_dimension_key(row: dict[str, object]) -> tuple[object, object, object]:
    return (row["cbs_node_id"], row["wbs_node_id"], row["cost_center_id"])


def _reconciliation_labels(row: dict[str, object]) -> tuple[str, str, str, str, str]:
    return (
        str(row["cbs_node__code"]),
        str(row["cbs_node__name"]),
        str(row["wbs_node__code"]),
        str(row["wbs_node__title"]),
        str(row["cost_center__code"] or "—"),
    )


def get_project_cost_reconciliation(
    *, organization: Organization, project: Project, actor: User
) -> ProjectCostReconciliation | None:
    """Build a bounded, incomplete reconciliation without selecting source authority.

    The three evidence families remain distinct.  A numeric difference is emitted
    only where both expense and inert actual-fact evidence exist in the same coded
    dimension; it remains unresolved because producer activation, cutoff ownership,
    source equivalence and complete coverage are not approved.
    """

    _require_project_controls_access(
        organization=organization,
        project=project,
        actor=actor,
        permission=BusinessPermissionCode.PROJECT_COST_RECONCILIATIONS_VIEW,
    )
    control = (
        ProjectBudgetControl.objects.filter(
            organization=organization,
            project=project,
            governing_budget__status=BudgetVersionStatus.ACCEPTED,
        )
        .select_related("governing_budget")
        .first()
    )
    if control is None or control.governing_budget is None:
        record_audit_event(
            action=AuditAction.PROJECT_COST_RECONCILIATION_VIEWED,
            entity_type="project_cost_reconciliation",
            entity_id=project.pk,
            organization=organization,
            actor=actor,
            metadata={
                "project_id": str(project.pk),
                "budget_id": "",
                "line_count": 0,
                "source_count": 0,
                "coverage": "incomplete",
                "source_equivalence": "not_established",
                "status": "no_governing_accepted_budget",
            },
        )
        return None
    budget = control.governing_budget
    dimensions = (
        "cbs_node_id",
        "cbs_node__code",
        "cbs_node__name",
        "wbs_node_id",
        "wbs_node__code",
        "wbs_node__title",
        "cost_center_id",
        "cost_center__code",
    )
    budget_rows = tuple(
        BudgetAllocation.objects.filter(
            organization=organization,
            manifest_line__manifest__budget=budget,
        )
        .values(*dimensions)
        .annotate(amount=Sum("amount"), evidence_count=Count("pk"))
        .order_by("cbs_node__code", "wbs_node__code", "cost_center__code")
    )

    from apps.expenses.models import Expense, ExpenseAllocation, ExpenseStatus

    included_statuses = (ExpenseStatus.APPROVED, ExpenseStatus.RECORDED)
    expense_rows = tuple(
        ExpenseAllocation.objects.filter(
            organization=organization,
            project=project,
            governing_budget=budget,
            expense__organization=organization,
            expense__status__in=included_statuses,
        )
        .values(*dimensions)
        .annotate(amount=Sum("amount"), evidence_count=Count("pk"))
        .order_by("cbs_node__code", "wbs_node__code", "cost_center__code")
    )
    unallocated = Expense.objects.filter(
        organization=organization,
        project=project,
        status__in=included_statuses,
        allocations__isnull=True,
    ).aggregate(evidence_count=Count("pk"), amount=Sum("amount"))
    stale_expense = (
        ExpenseAllocation.objects.filter(
            organization=organization,
            project=project,
            expense__organization=organization,
            expense__status__in=included_statuses,
        )
        .exclude(governing_budget=budget)
        .aggregate(evidence_count=Count("pk"), amount=Sum("amount"))
    )

    actual_kinds = (
        ProjectCostFactKind.ACTUAL_RECOGNIZED,
        ProjectCostFactKind.ACTUAL_REVERSAL,
    )
    actual_facts = ProjectCostFact.objects.filter(
        organization=organization,
        project=project,
        kind__in=actual_kinds,
    )
    compatible_actual_facts = actual_facts.filter(currency=budget.currency)
    actual_rows = tuple(
        compatible_actual_facts.values(*dimensions)
        .annotate(amount=Sum("amount"), evidence_count=Count("pk"))
        .order_by("cbs_node__code", "wbs_node__code", "cost_center__code")
    )
    currency_mismatch = actual_facts.exclude(currency=budget.currency).aggregate(
        evidence_count=Count("pk"), amount=Sum("amount")
    )
    excluded_non_actual = (
        ProjectCostFact.objects.filter(organization=organization, project=project)
        .exclude(kind__in=actual_kinds)
        .aggregate(evidence_count=Count("pk"), amount=Sum("amount"))
    )
    actual_without_budget_lineage = compatible_actual_facts.aggregate(
        evidence_count=Count("pk"), amount=Sum("amount")
    )

    grouped: dict[tuple[object, object, object], dict[str, object]] = {}

    def merge(
        row: dict[str, object], amount_field: str, count_field: str
    ) -> None:
        key = _reconciliation_dimension_key(row)
        entry = grouped.setdefault(
            key,
            {
                "labels": _reconciliation_labels(row),
                "budget_amount": None,
                "expense_amount": None,
                "actual_amount": None,
                "budget_count": 0,
                "expense_count": 0,
                "actual_count": 0,
            },
        )
        entry[amount_field] = row["amount"]
        entry[count_field] = row["evidence_count"]

    for row in budget_rows:
        merge(row, "budget_amount", "budget_count")
    for row in expense_rows:
        merge(row, "expense_amount", "expense_count")
    for row in actual_rows:
        merge(row, "actual_amount", "actual_count")

    lines: list[ProjectCostReconciliationLine] = []
    for entry in sorted(grouped.values(), key=lambda item: item["labels"]):
        labels = entry["labels"]
        expense_amount = entry["expense_amount"]
        actual_amount = entry["actual_amount"]
        difference = (
            expense_amount - actual_amount
            if isinstance(expense_amount, Decimal)
            and isinstance(actual_amount, Decimal)
            else None
        )
        lines.append(
            ProjectCostReconciliationLine(
                *labels,
                accepted_budget_amount=entry["budget_amount"],
                approved_or_recorded_expense_amount=expense_amount,
                inert_project_cost_actual_amount=actual_amount,
                unresolved_difference=difference,
                budget_allocation_count=int(entry["budget_count"]),
                expense_allocation_count=int(entry["expense_count"]),
                project_cost_fact_count=int(entry["actual_count"]),
            )
        )

    source_rows = tuple(
        compatible_actual_facts.values(
            "contract_id",
            "contract__producer_key",
            "contract__version",
            "contract__source_model",
            "contract__reconciliation_policy_reference",
        )
        .annotate(fact_count=Count("pk"), net_amount=Sum("amount"))
        .order_by("contract__producer_key", "contract__version", "contract_id")
    )
    source_rows_by_contract = {row["contract_id"]: row for row in source_rows}
    coverage_by_contract = {
        coverage.contract_id: coverage
        for coverage in ProjectCostCoverage.objects.filter(
            organization=organization,
            project=project,
            contract__organization=organization,
            contract__measure=ProjectCostMeasure.ACTUAL,
            contract__status=ProjectCostSourceContractStatus.APPROVED,
        ).select_related("contract")
    }
    # Explicit project coverage establishes an expected source; a tenant-wide
    # producer contract alone does not. Missing facts never imply a zero amount.
    for contract_id, coverage in coverage_by_contract.items():
        contract = coverage.contract
        source_rows_by_contract.setdefault(
            contract_id,
            {
                "contract_id": contract_id,
                "contract__producer_key": contract.producer_key,
                "contract__version": contract.version,
                "contract__source_model": contract.source_model,
                "contract__reconciliation_policy_reference": (
                    contract.reconciliation_policy_reference
                ),
                "fact_count": 0,
                "net_amount": None,
            },
        )
    sources = tuple(
        ProjectCostReconciliationSource(
            contract_id=str(row["contract_id"]),
            producer_key=str(row["contract__producer_key"]),
            version=int(row["contract__version"]),
            source_model=str(row["contract__source_model"]),
            reconciliation_policy_reference=str(
                row["contract__reconciliation_policy_reference"]
            ),
            coverage_status=(
                coverage_by_contract[row["contract_id"]].status
                if row["contract_id"] in coverage_by_contract
                else ProjectCostCoverageStatus.NOT_STARTED
            ),
            watermark=(
                coverage_by_contract[row["contract_id"]].watermark
                if row["contract_id"] in coverage_by_contract
                else ""
            ),
            fact_count=int(row["fact_count"]),
            net_amount=row["net_amount"],
            cutoff_at=(
                coverage_by_contract[row["contract_id"]].cutoff_at
                if row["contract_id"] in coverage_by_contract
                else None
            ),
            missing_facts=row["fact_count"] == 0,
        )
        for row in sorted(
            source_rows_by_contract.values(),
            key=lambda row: (
                row["contract__producer_key"],
                row["contract__version"],
                str(row["contract_id"]),
            ),
        )
    )

    exclusions = (
        ProjectCostReconciliationExclusion(
            code="unallocated_expense",
            disposition="excluded",
            count=int(unallocated["evidence_count"]),
            amount=unallocated["amount"],
            note="Approved/recorded expense evidence has no comparable coded allocation.",
        ),
        ProjectCostReconciliationExclusion(
            code="non_governing_budget_expense",
            disposition="excluded",
            count=int(stale_expense["evidence_count"]),
            amount=stale_expense["amount"],
            note="Expense allocations are pinned to a different accepted budget.",
        ),
        ProjectCostReconciliationExclusion(
            code="non_actual_project_cost_fact",
            disposition="excluded",
            count=int(excluded_non_actual["evidence_count"]),
            amount=excluded_non_actual["amount"],
            note="Commitment/accrual facts are not actual-expense equivalence evidence.",
        ),
        ProjectCostReconciliationExclusion(
            code="currency_mismatch_project_cost_fact",
            disposition="excluded",
            count=int(currency_mismatch["evidence_count"]),
            amount=currency_mismatch["amount"],
            note="Project Cost fact currency does not match the governing budget.",
        ),
        ProjectCostReconciliationExclusion(
            code="actual_fact_without_budget_lineage",
            disposition="uncomparable",
            count=int(actual_without_budget_lineage["evidence_count"]),
            amount=actual_without_budget_lineage["amount"],
            note=(
                "Existing Project Cost facts do not retain a budget-version key; "
                "side-by-side values cannot establish same-budget source equivalence."
            ),
        ),
    )
    budget_total = (
        sum((row["amount"] for row in budget_rows), Decimal("0.00"))
        if budget_rows
        else None
    )
    expense_total = (
        sum((row["amount"] for row in expense_rows), Decimal("0.00"))
        if expense_rows
        else None
    )
    actual_total = (
        sum((row["amount"] for row in actual_rows), Decimal("0.00"))
        if actual_rows
        else None
    )
    unresolved_total = (
        expense_total - actual_total
        if expense_total is not None and actual_total is not None
        else None
    )
    snapshot = ProjectCostReconciliation(
        budget_id=str(budget.pk),
        budget_payload_hash=budget.payload_hash,
        currency=budget.currency,
        lines=tuple(lines),
        sources=sources,
        exclusions=exclusions,
        accepted_budget_total=budget_total,
        approved_or_recorded_expense_total=expense_total,
        inert_project_cost_actual_total=actual_total,
        unresolved_total_difference=unresolved_total,
        coverage_complete=False,
        source_equivalence_established=False,
    )
    record_audit_event(
        action=AuditAction.PROJECT_COST_RECONCILIATION_VIEWED,
        entity_type="project_cost_reconciliation",
        entity_id=project.pk,
        organization=organization,
        actor=actor,
        metadata={
            "project_id": str(project.pk),
            "budget_id": str(budget.pk),
            "line_count": len(snapshot.lines),
            "source_count": len(snapshot.sources),
            "coverage": "incomplete",
            "source_equivalence": "not_established",
        },
    )
    return snapshot


def export_project_cost_reconciliation(
    *, organization: Organization, project: Project, actor: User
) -> bytes:
    """Export only the bounded reconciliation and retain an append-only manifest."""

    _require_project_controls_access(
        organization=organization,
        project=project,
        actor=actor,
        permission=BusinessPermissionCode.PROJECT_COST_RECONCILIATIONS_EXPORT,
    )
    snapshot = get_project_cost_reconciliation(
        organization=organization, project=project, actor=actor
    )
    stream = StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(("coverage", "incomplete"))
    writer.writerow(("source_equivalence", "not_established"))
    if snapshot is None:
        writer.writerow(("status", "no_governing_accepted_budget"))
    else:
        writer.writerow(("governing_budget", snapshot.budget_id))
        writer.writerow(("currency", snapshot.currency))
        writer.writerow(
            (
                "section",
                "cbs",
                "wbs",
                "cost_center",
                "accepted_budget",
                "approved_or_recorded_expense",
                "inert_project_cost_actual",
                "unresolved_difference",
                "note",
            )
        )
        for line in snapshot.lines:
            writer.writerow(
                (
                    "coded_evidence",
                    line.cbs_code,
                    line.wbs_code,
                    line.cost_center_code,
                    ""
                    if line.accepted_budget_amount is None
                    else line.accepted_budget_amount,
                    ""
                    if line.approved_or_recorded_expense_amount is None
                    else line.approved_or_recorded_expense_amount,
                    ""
                    if line.inert_project_cost_actual_amount is None
                    else line.inert_project_cost_actual_amount,
                    ""
                    if line.unresolved_difference is None
                    else line.unresolved_difference,
                    "incomplete evidence; no source authority inferred",
                )
            )
        for source in snapshot.sources:
            writer.writerow(
                (
                    "project_cost_source_provenance",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "" if source.net_amount is None else source.net_amount,
                    "",
                    (
                        f"{source.producer_key}:v{source.version};"
                        f"model={source.source_model};coverage={source.coverage_status};"
                        f"policy={source.reconciliation_policy_reference};"
                        f"watermark={source.watermark or 'none'};"
                        f"cutoff_at={source.cutoff_at.isoformat() if source.cutoff_at else 'none'};"
                        f"facts={'missing' if source.missing_facts else 'present'}"
                    ),
                )
            )
        for exclusion in snapshot.exclusions:
            writer.writerow(
                (
                    f"{exclusion.disposition}:{exclusion.code}",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "" if exclusion.amount is None else exclusion.amount,
                    "",
                    f"count={exclusion.count};{exclusion.note}",
                )
            )
    payload = stream.getvalue().encode("utf-8-sig")
    record_audit_event(
        action=AuditAction.PROJECT_COST_RECONCILIATION_EXPORTED,
        entity_type="project_cost_reconciliation_export",
        entity_id=project.pk,
        organization=organization,
        actor=actor,
        metadata={
            "project_id": str(project.pk),
            "budget_id": snapshot.budget_id if snapshot else "",
            "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload),
            "coverage": "incomplete",
            "source_equivalence": "not_established",
        },
    )
    return payload


@transaction.atomic
def create_project_cost_forecast_draft(
    *,
    organization: Organization,
    project: Project,
    actor: User,
    cutoff_date: date,
    uncommitted_etc: Decimal,
    assumptions: str,
) -> ProjectCostForecast:
    project = Project.objects.select_for_update().get(pk=project.pk)
    _require_budget_access(
        organization=organization,
        actor=actor,
        project=project,
        permission=BusinessPermissionCode.PROJECT_FORECASTS_PREPARE,
    )
    control = ProjectBudgetControl.objects.select_related("governing_budget").get(
        project=project
    )
    if control.governing_budget is None:
        raise ValueError("A governing accepted budget is required.")
    if uncommitted_etc < 0 or not assumptions.strip():
        raise ValueError(
            "Forecast assumptions and non-negative uncommitted ETC are required."
        )
    projection = get_project_cost_projection(
        organization=organization, project=project, actor=actor, cutoff=cutoff_date
    )
    version = (
        ProjectCostForecast.objects.filter(project=project).aggregate(
            value=Max("version_number")
        )["value"]
        or 0
    ) + 1
    remaining_committed = projection.open_commitment
    eac = projection.actual_cost + remaining_committed + uncommitted_etc
    watermark = (
        "|".join(
            f"{c.contract.producer_key}:{c.watermark or 'missing'}"
            for c in projection.coverage
        )
        or "no-producer-coverage"
    )
    forecast = ProjectCostForecast.objects.create(
        organization=organization,
        project=project,
        budget=control.governing_budget,
        version_number=version,
        cutoff_date=cutoff_date,
        currency=projection.currency,
        actual_cost=projection.actual_cost,
        open_commitment=projection.open_commitment,
        remaining_committed_etc=remaining_committed,
        uncommitted_etc=uncommitted_etc,
        eac=eac,
        assumptions=assumptions.strip(),
        source_watermark=watermark,
        coverage_complete=projection.coverage_complete,
        created_by=actor,
    )
    predecessor = ProjectForecastReview.objects.filter(
        organization=organization,
        project=project,
        status=ForecastReviewStatus.APPROVED,
    ).first()
    ProjectForecastReview.objects.create(
        organization=organization,
        project=project,
        forecast=forecast,
        predecessor=predecessor,
    )
    record_audit_event(
        action=AuditAction.PROJECT_COST_FORECAST_DRAFTED,
        entity_type="project_cost_forecast",
        entity_id=forecast.pk,
        organization=organization,
        actor=actor,
        metadata={
            "project_id": str(project.pk),
            "coverage_complete": projection.coverage_complete,
        },
    )
    return forecast


@transaction.atomic
def create_project_schedule_revision(
    *,
    organization: Organization,
    project: Project,
    actor: User,
    occurrence_id: str,
    data_date: date,
    planned_start: date,
    planned_finish: date,
    calendar_reference: str,
    assumptions: str,
    predecessor: ProjectScheduleRevision | None = None,
) -> ProjectScheduleRevision:
    project = Project.objects.select_for_update().get(pk=project.pk)
    _require_budget_access(
        organization=organization,
        actor=actor,
        project=project,
        permission=BusinessPermissionCode.PROJECT_SCHEDULES_PREPARE,
    )
    occurrence_id = occurrence_id.strip()
    payload = {
        "project": str(project.pk),
        "data_date": data_date,
        "planned_start": planned_start,
        "planned_finish": planned_finish,
        "calendar_reference": calendar_reference.strip(),
        "assumptions": assumptions.strip(),
        "predecessor": str(predecessor.pk) if predecessor else None,
    }
    payload_hash = _stable_payload_hash(payload)
    existing = ProjectScheduleRevision.objects.filter(
        organization=organization, occurrence_id=occurrence_id
    ).first()
    if existing:
        if existing.payload_hash != payload_hash:
            raise ValueError(
                "Schedule occurrence was retried with a different payload."
            )
        return existing
    if predecessor and (
        predecessor.organization_id != organization.pk
        or predecessor.project_id != project.pk
    ):
        raise PermissionDenied("Schedule predecessor is outside the active project.")
    version = (
        ProjectScheduleRevision.objects.filter(project=project).aggregate(
            value=Max("version_number")
        )["value"]
        or 0
    ) + 1
    revision = ProjectScheduleRevision.objects.create(
        organization=organization,
        project=project,
        version_number=version,
        occurrence_id=occurrence_id,
        data_date=data_date,
        planned_start=planned_start,
        planned_finish=planned_finish,
        calendar_reference=calendar_reference.strip(),
        assumptions=assumptions.strip(),
        predecessor=predecessor,
        payload_hash=payload_hash,
        created_by=actor,
    )
    record_audit_event(
        action=AuditAction.PROJECT_SCHEDULE_DRAFTED,
        entity_type="project_schedule_revision",
        entity_id=revision.pk,
        organization=organization,
        actor=actor,
        metadata={"project_id": str(project.pk), "version": version},
    )
    return revision


@transaction.atomic
def add_project_schedule_item(
    *,
    schedule: ProjectScheduleRevision,
    actor: User,
    code: str,
    name: str,
    planned_start: date,
    planned_finish: date,
    source_reference: str,
    is_milestone: bool = False,
    wbs_node: WBSNode | None = None,
) -> ProjectScheduleItem:
    schedule = (
        ProjectScheduleRevision.objects.select_for_update()
        .select_related("organization", "project")
        .get(pk=schedule.pk)
    )
    _require_budget_access(
        organization=schedule.organization,
        actor=actor,
        project=schedule.project,
        permission=BusinessPermissionCode.PROJECT_SCHEDULES_PREPARE,
    )
    code = canonicalize_upper_identifier(code)
    existing = ProjectScheduleItem.objects.filter(schedule=schedule, code=code).first()
    expected = (
        name.strip(),
        planned_start,
        planned_finish,
        source_reference.strip(),
        is_milestone,
        wbs_node.pk if wbs_node else None,
    )
    if existing:
        actual = (
            existing.name,
            existing.planned_start,
            existing.planned_finish,
            existing.source_reference,
            existing.is_milestone,
            existing.wbs_node_id,
        )
        if actual != expected:
            raise ValueError("Schedule item code was retried with different evidence.")
        return existing
    item = ProjectScheduleItem.objects.create(
        organization=schedule.organization,
        project=schedule.project,
        schedule=schedule,
        wbs_node=wbs_node,
        code=code,
        name=name.strip(),
        is_milestone=is_milestone,
        planned_start=planned_start,
        planned_finish=planned_finish,
        source_reference=source_reference.strip(),
    )
    record_audit_event(
        action=AuditAction.PROJECT_SCHEDULE_ITEM_ADDED,
        entity_type="project_schedule_item",
        entity_id=item.pk,
        organization=schedule.organization,
        actor=actor,
        metadata={"project_id": str(schedule.project_id), "code": code},
    )
    return item


def _dependency_would_cycle(
    *, schedule: ProjectScheduleRevision, predecessor_id: object, successor_id: object
) -> bool:
    adjacency: dict[object, set[object]] = {}
    for source, target in ProjectScheduleDependency.objects.filter(
        schedule=schedule
    ).values_list("predecessor_item_id", "successor_item_id"):
        adjacency.setdefault(source, set()).add(target)
    pending = [successor_id]
    seen: set[object] = set()
    while pending:
        current = pending.pop()
        if current == predecessor_id:
            return True
        if current not in seen:
            seen.add(current)
            pending.extend(adjacency.get(current, ()))
    return False


@transaction.atomic
def add_project_schedule_dependency(
    *,
    schedule: ProjectScheduleRevision,
    actor: User,
    predecessor_item: ProjectScheduleItem,
    successor_item: ProjectScheduleItem,
    dependency_type: str,
    lag_days: int,
    rationale: str,
) -> ProjectScheduleDependency:
    schedule = (
        ProjectScheduleRevision.objects.select_for_update()
        .select_related("organization", "project")
        .get(pk=schedule.pk)
    )
    _require_budget_access(
        organization=schedule.organization,
        actor=actor,
        project=schedule.project,
        permission=BusinessPermissionCode.PROJECT_SCHEDULES_PREPARE,
    )
    if dependency_type not in ProjectScheduleDependencyType.values:
        raise ValueError("Unsupported dependency type.")
    existing = ProjectScheduleDependency.objects.filter(
        schedule=schedule,
        predecessor_item=predecessor_item,
        successor_item=successor_item,
        dependency_type=dependency_type,
    ).first()
    if existing:
        if existing.lag_days != lag_days or existing.rationale != rationale.strip():
            raise ValueError("Dependency was retried with different evidence.")
        return existing
    if _dependency_would_cycle(
        schedule=schedule,
        predecessor_id=predecessor_item.pk,
        successor_id=successor_item.pk,
    ):
        raise ValueError("Schedule dependency would create a cycle.")
    dependency = ProjectScheduleDependency.objects.create(
        organization=schedule.organization,
        project=schedule.project,
        schedule=schedule,
        predecessor_item=predecessor_item,
        successor_item=successor_item,
        dependency_type=dependency_type,
        lag_days=lag_days,
        rationale=rationale.strip(),
    )
    record_audit_event(
        action=AuditAction.PROJECT_SCHEDULE_DEPENDENCY_ADDED,
        entity_type="project_schedule_dependency",
        entity_id=dependency.pk,
        organization=schedule.organization,
        actor=actor,
        metadata={"project_id": str(schedule.project_id)},
    )
    return dependency


@transaction.atomic
def record_project_control_item(
    *,
    organization: Organization,
    project: Project,
    actor: User,
    kind: str,
    occurrence_id: str,
    title: str,
    description: str,
    identified_on: date,
    owner_reference: str,
    evidence_reference: str,
    schedule_impact_description: str = "",
    observed_from: date | None = None,
    observed_to: date | None = None,
    schedule_item: ProjectScheduleItem | None = None,
) -> ProjectControlItem:
    project = Project.objects.select_for_update().get(pk=project.pk)
    _require_budget_access(
        organization=organization,
        actor=actor,
        project=project,
        permission=BusinessPermissionCode.PROJECT_CONTROL_REGISTERS_MANAGE,
    )
    if kind not in ProjectControlItemKind.values:
        raise ValueError("Unsupported project-control register kind.")
    occurrence_id = occurrence_id.strip()
    payload = {
        "project": str(project.pk),
        "kind": kind,
        "title": title.strip(),
        "description": description.strip(),
        "identified_on": identified_on,
        "owner_reference": owner_reference.strip(),
        "evidence_reference": evidence_reference.strip(),
        "schedule_impact_description": schedule_impact_description.strip(),
        "observed_from": observed_from,
        "observed_to": observed_to,
        "schedule_item": str(schedule_item.pk) if schedule_item else None,
    }
    payload_hash = _stable_payload_hash(payload)
    existing = ProjectControlItem.objects.filter(
        organization=organization, project=project, occurrence_id=occurrence_id
    ).first()
    if existing:
        if existing.payload_hash != payload_hash:
            raise ValueError("Control occurrence was retried with a different payload.")
        return existing
    item = ProjectControlItem.objects.create(
        organization=organization,
        project=project,
        schedule_item=schedule_item,
        kind=kind,
        occurrence_id=occurrence_id,
        title=title.strip(),
        description=description.strip(),
        identified_on=identified_on,
        observed_from=observed_from,
        observed_to=observed_to,
        owner_reference=owner_reference.strip(),
        evidence_reference=evidence_reference.strip(),
        schedule_impact_description=schedule_impact_description.strip(),
        payload_hash=payload_hash,
        created_by=actor,
    )
    ProjectControlStatusEvent.objects.create(
        organization=organization,
        item=item,
        sequence=1,
        occurrence_id=f"{occurrence_id}:open",
        to_status=ProjectControlItemStatus.OPEN,
        reason="Initial registration",
        actor=actor,
    )
    record_audit_event(
        action=AuditAction.PROJECT_CONTROL_ITEM_RECORDED,
        entity_type="project_control_item",
        entity_id=item.pk,
        organization=organization,
        actor=actor,
        metadata={"project_id": str(project.pk), "kind": kind},
    )
    return item


@transaction.atomic
def transition_project_control_item(
    *,
    item: ProjectControlItem,
    actor: User,
    occurrence_id: str,
    to_status: str,
    reason: str,
) -> ProjectControlStatusEvent:
    item = (
        ProjectControlItem.objects.select_for_update()
        .select_related("organization", "project")
        .get(pk=item.pk)
    )
    _require_budget_access(
        organization=item.organization,
        actor=actor,
        project=item.project,
        permission=BusinessPermissionCode.PROJECT_CONTROL_REGISTERS_MANAGE,
    )
    occurrence_id = occurrence_id.strip()
    existing = ProjectControlStatusEvent.objects.filter(
        item=item, occurrence_id=occurrence_id
    ).first()
    if existing:
        if existing.to_status != to_status or existing.reason != reason.strip():
            raise ValueError("Status occurrence was retried with different evidence.")
        return existing
    latest = item.status_events.select_for_update().order_by("-sequence").first()
    if latest is None:
        raise ValueError("Control item has no initial status evidence.")
    allowed = {
        ProjectControlItemStatus.OPEN: ProjectControlItemStatus.CLOSED,
        ProjectControlItemStatus.CLOSED: ProjectControlItemStatus.OPEN,
    }
    if to_status != allowed[latest.to_status] or not reason.strip():
        raise ValueError("Invalid control status transition or missing reason.")
    event = ProjectControlStatusEvent.objects.create(
        organization=item.organization,
        item=item,
        sequence=latest.sequence + 1,
        occurrence_id=occurrence_id,
        from_status=latest.to_status,
        to_status=to_status,
        reason=reason.strip(),
        actor=actor,
    )
    record_audit_event(
        action=AuditAction.PROJECT_CONTROL_STATUS_RECORDED,
        entity_type="project_control_status_event",
        entity_id=event.pk,
        organization=item.organization,
        actor=actor,
        metadata={"item_id": str(item.pk), "to_status": to_status},
    )
    return event


@transaction.atomic
def propose_project_change(
    *,
    organization: Organization,
    project: Project,
    actor: User,
    occurrence_id: str,
    title: str,
    reason: str,
    evidence_reference: str,
    schedule_impact_description: str,
    cost_impact_description: str = "",
) -> ProjectChangeProposal:
    project = Project.objects.select_for_update().get(pk=project.pk)
    _require_budget_access(
        organization=organization,
        actor=actor,
        project=project,
        permission=BusinessPermissionCode.PROJECT_CHANGES_PROPOSE,
    )
    occurrence_id = occurrence_id.strip()
    payload = {
        "project": str(project.pk),
        "title": title.strip(),
        "reason": reason.strip(),
        "evidence_reference": evidence_reference.strip(),
        "schedule_impact_description": schedule_impact_description.strip(),
        "cost_impact_description": cost_impact_description.strip(),
    }
    payload_hash = _stable_payload_hash(payload)
    existing = ProjectChangeProposal.objects.filter(
        organization=organization, project=project, occurrence_id=occurrence_id
    ).first()
    if existing:
        if existing.payload_hash != payload_hash:
            raise ValueError("Change occurrence was retried with a different payload.")
        return existing
    proposal = ProjectChangeProposal.objects.create(
        organization=organization,
        project=project,
        occurrence_id=occurrence_id,
        title=title.strip(),
        reason=reason.strip(),
        evidence_reference=evidence_reference.strip(),
        schedule_impact_description=schedule_impact_description.strip(),
        cost_impact_description=cost_impact_description.strip(),
        payload_hash=payload_hash,
        proposed_by=actor,
    )
    record_audit_event(
        action=AuditAction.PROJECT_CHANGE_PROPOSED,
        entity_type="project_change_proposal",
        entity_id=proposal.pk,
        organization=organization,
        actor=actor,
        metadata={"project_id": str(project.pk)},
    )
    return proposal


@transaction.atomic
def propose_schedule_rebaseline(
    *,
    organization: Organization,
    project: Project,
    actor: User,
    occurrence_id: str,
    current_baseline: ProjectScheduleRevision,
    candidate_revision: ProjectScheduleRevision,
    reason: str,
    evidence_reference: str,
    change_proposal: ProjectChangeProposal | None = None,
) -> ScheduleRebaselineProposal:
    project = Project.objects.select_for_update().get(pk=project.pk)
    _require_budget_access(
        organization=organization,
        actor=actor,
        project=project,
        permission=BusinessPermissionCode.PROJECT_REBASELINES_PROPOSE,
    )
    occurrence_id = occurrence_id.strip()
    payload = {
        "project": str(project.pk),
        "current_baseline": str(current_baseline.pk),
        "candidate_revision": str(candidate_revision.pk),
        "change_proposal": str(change_proposal.pk) if change_proposal else None,
        "reason": reason.strip(),
        "evidence_reference": evidence_reference.strip(),
    }
    payload_hash = _stable_payload_hash(payload)
    existing = ScheduleRebaselineProposal.objects.filter(
        organization=organization, project=project, occurrence_id=occurrence_id
    ).first()
    if existing:
        if existing.payload_hash != payload_hash:
            raise ValueError(
                "Rebaseline occurrence was retried with different evidence."
            )
        return existing
    proposal = ScheduleRebaselineProposal.objects.create(
        organization=organization,
        project=project,
        occurrence_id=occurrence_id,
        current_baseline=current_baseline,
        candidate_revision=candidate_revision,
        change_proposal=change_proposal,
        reason=reason.strip(),
        evidence_reference=evidence_reference.strip(),
        payload_hash=payload_hash,
        proposed_by=actor,
    )
    record_audit_event(
        action=AuditAction.PROJECT_REBASELINE_PROPOSED,
        entity_type="schedule_rebaseline_proposal",
        entity_id=proposal.pk,
        organization=organization,
        actor=actor,
        metadata={"project_id": str(project.pk)},
    )
    return proposal


def accept_project_schedule_baseline(
    *, schedule: ProjectScheduleRevision, actor: User
) -> None:
    _require_budget_access(
        organization=schedule.organization,
        actor=actor,
        project=schedule.project,
        permission=BusinessPermissionCode.PROJECT_SCHEDULE_BASELINES_ACCEPT,
    )
    raise PermissionDenied(
        "Schedule-baseline authority and acceptance policy are not approved."
    )


def approve_project_change(*, proposal: ProjectChangeProposal, actor: User) -> None:
    _require_budget_access(
        organization=proposal.organization,
        actor=actor,
        project=proposal.project,
        permission=BusinessPermissionCode.PROJECT_CHANGES_APPROVE,
    )
    raise PermissionDenied(
        "Project-change approval and contractual/financial impact policy are not approved."
    )


def accept_schedule_rebaseline(
    *, proposal: ScheduleRebaselineProposal, actor: User
) -> None:
    _require_budget_access(
        organization=proposal.organization,
        actor=actor,
        project=proposal.project,
        permission=BusinessPermissionCode.PROJECT_REBASELINES_ACCEPT,
    )
    raise PermissionDenied("Rebaseline acceptance authority is not approved.")


def get_project_control_snapshot(
    *, organization: Organization, project: Project, actor: User
) -> ProjectControlSnapshot:
    _require_budget_access(
        organization=organization,
        actor=actor,
        project=project,
        permission=BusinessPermissionCode.PROJECT_SCHEDULES_VIEW,
    )
    schedules = tuple(
        ProjectScheduleRevision.objects.filter(
            organization=organization, project=project
        )
        .prefetch_related("items", "dependencies")
        .order_by("version_number")
    )
    register_items = ()
    if _has_project_permission(
        actor,
        organization,
        BusinessPermissionCode.PROJECT_CONTROL_REGISTERS_VIEW,
        project=project,
    ):
        register_items = tuple(
            ProjectControlItem.objects.filter(
                organization=organization, project=project
            )
            .prefetch_related("status_events")
            .order_by("identified_on", "created_at", "pk")
        )
    changes = ()
    if _has_project_permission(
        actor,
        organization,
        BusinessPermissionCode.PROJECT_CHANGES_VIEW,
        project=project,
    ):
        changes = tuple(
            ProjectChangeProposal.objects.filter(
                organization=organization, project=project
            ).order_by("created_at", "pk")
        )
    rebaselines = ()
    if _has_project_permission(
        actor,
        organization,
        BusinessPermissionCode.PROJECT_REBASELINES_VIEW,
        project=project,
    ):
        rebaselines = tuple(
            ScheduleRebaselineProposal.objects.filter(
                organization=organization, project=project
            )
            .select_related("current_baseline", "candidate_revision", "change_proposal")
            .order_by("created_at", "pk")
        )
    return ProjectControlSnapshot(schedules, register_items, changes, rebaselines)


def _require_project_controls_access(
    *,
    organization: Organization,
    project: Project,
    actor: User,
    permission: BusinessPermissionCode,
) -> None:
    _require_project_management_access(
        organization=organization,
        actor=actor,
        permission=permission,
        project=project,
    )
    if project.organization_id != organization.pk or project.deleted_at is not None:
        raise PermissionDenied("The project does not belong to the active organization.")


def get_project_control_comparison(
    *, organization: Organization, project: Project, actor: User
) -> ProjectControlComparison | None:
    """Return a read-only, same-budget comparison of bounded expense evidence.

    This intentionally excludes Project Cost, forecast, cash, posting and all
    unclassified evidence.  It is an observation, not an overrun policy.
    """
    _require_project_controls_access(
        organization=organization,
        project=project,
        actor=actor,
        permission=BusinessPermissionCode.PROJECT_CONTROLS_COMPARE,
    )
    try:
        budget = ProjectBudgetControl.objects.select_related("governing_budget").get(
            organization=organization, project=project
        ).governing_budget
    except ProjectBudgetControl.DoesNotExist:
        budget = None
    if budget is None or budget.status != BudgetVersionStatus.ACCEPTED:
        return None

    allocations = tuple(
        BudgetAllocation.objects.filter(manifest_line__manifest__budget=budget)
        .select_related("cbs_node", "wbs_node", "cost_center")
        .order_by("cbs_node__code", "wbs_node__code", "cost_center__code", "pk")
    )
    amounts: dict[tuple[object, object, object], Decimal] = {}
    labels: dict[tuple[object, object, object], tuple[str, str, str, str, str]] = {}
    for allocation in allocations:
        key = (allocation.cbs_node_id, allocation.wbs_node_id, allocation.cost_center_id)
        amounts[key] = amounts.get(key, Decimal("0.00")) + allocation.amount
        labels[key] = (
            allocation.cbs_node.code,
            allocation.cbs_node.name,
            allocation.wbs_node.code,
            allocation.wbs_node.title,
            allocation.cost_center.code if allocation.cost_center_id else "—",
        )

    # Imported lazily to preserve Expenses -> Projects service dependency direction.
    from apps.expenses.models import Expense, ExpenseAllocation, ExpenseStatus

    evidence = ExpenseAllocation.objects.filter(
        organization=organization,
        project=project,
        governing_budget=budget,
        expense__organization=organization,
        expense__status__in=(ExpenseStatus.APPROVED, ExpenseStatus.RECORDED),
    ).select_related("cbs_node", "wbs_node", "cost_center")
    spent: dict[tuple[object, object, object], Decimal] = {}
    for allocation in evidence:
        key = (allocation.cbs_node_id, allocation.wbs_node_id, allocation.cost_center_id)
        spent[key] = spent.get(key, Decimal("0.00")) + allocation.amount
        if key not in labels:
            labels[key] = (
                allocation.cbs_node.code,
                allocation.cbs_node.name,
                allocation.wbs_node.code,
                allocation.wbs_node.title,
                allocation.cost_center.code if allocation.cost_center_id else "—",
            )
    lines = tuple(
        ProjectControlComparisonLine(
            *labels[key],
            accepted_budget_amount=amounts.get(key, Decimal("0.00")),
            approved_or_recorded_expense_amount=spent.get(key, Decimal("0.00")),
            remaining_amount=amounts.get(key, Decimal("0.00"))
            - spent.get(key, Decimal("0.00")),
        )
        for key in sorted(labels, key=lambda item: labels[item])
    )
    unallocated = Expense.objects.filter(
        organization=organization,
        project=project,
        status__in=(ExpenseStatus.APPROVED, ExpenseStatus.RECORDED),
        allocations__isnull=True,
    )
    return ProjectControlComparison(
        budget_id=str(budget.pk),
        currency=budget.currency,
        lines=lines,
        unallocated_expense_count=unallocated.count(),
        unallocated_expense_amount=unallocated.aggregate(value=Sum("amount"))["value"]
        or Decimal("0.00"),
    )


def get_project_control_exceptions(
    *, organization: Organization, project: Project, actor: User
) -> ProjectControlExceptionSnapshot:
    """Return bounded evidence only; no scoring, warning or state transition."""
    _require_project_controls_access(
        organization=organization,
        project=project,
        actor=actor,
        permission=BusinessPermissionCode.PROJECT_CONTROLS_EXCEPTIONS_VIEW,
    )
    from apps.expenses.models import ExpenseBudgetAssessment, ExpenseStatus

    overruns = tuple(
        ExpenseBudgetAssessment.objects.filter(
            organization=organization,
            allocation__project=project,
            expense__status__in=(ExpenseStatus.APPROVED, ExpenseStatus.RECORDED),
            control_mode="advisory_only",
            is_overrun=True,
        )
        .select_related("expense", "allocation", "governing_budget")
        .order_by("-assessed_at", "pk")
    )
    registers: tuple[ProjectControlItem, ...] = ()
    if _has_project_permission(
        actor,
        organization,
        BusinessPermissionCode.PROJECT_CONTROL_REGISTERS_VIEW,
        project=project,
    ):
        register_candidates = ProjectControlItem.objects.filter(
            organization=organization, project=project
        ).prefetch_related("status_events").order_by("identified_on", "created_at", "pk")
        registers = tuple(
            item
            for item in register_candidates
            if max(item.status_events.all(), key=lambda event: event.sequence).to_status
            == ProjectControlItemStatus.OPEN
        )
    return ProjectControlExceptionSnapshot(overruns, registers)


def export_project_control_snapshot(
    *, organization: Organization, project: Project, actor: User
) -> bytes:
    """Build the approved bounded CSV and retain an immutable audit manifest."""
    _require_project_controls_access(
        organization=organization,
        project=project,
        actor=actor,
        permission=BusinessPermissionCode.PROJECT_CONTROLS_EXPORT,
    )
    comparison = get_project_control_comparison(
        organization=organization, project=project, actor=actor
    )
    exceptions = get_project_control_exceptions(
        organization=organization, project=project, actor=actor
    )
    stream = StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(("section", "cbs", "wbs", "cost_center", "budget", "expense", "remaining", "note"))
    if comparison:
        for line in comparison.lines:
            writer.writerow(("accepted_budget_vs_expense", line.cbs_code, line.wbs_code, line.cost_center_code, line.accepted_budget_amount, line.approved_or_recorded_expense_amount, line.remaining_amount, "advisory evidence only"))
        writer.writerow(("excluded_unallocated_expense", "", "", "", "", comparison.unallocated_expense_amount, "", f"{comparison.unallocated_expense_count} records"))
    for assessment in exceptions.advisory_overruns:
        writer.writerow(("advisory_overrun_evidence", "", "", "", assessment.accepted_budget_amount, assessment.proposed_amount, assessment.remaining_after_proposal, f"expense:{assessment.expense_id}"))
    for item in exceptions.open_register_items:
        writer.writerow(("open_control_observation", "", "", "", "", "", "", f"{item.kind}:{item.pk}"))
    payload = stream.getvalue().encode("utf-8-sig")
    record_audit_event(
        action=AuditAction.PROJECT_CONTROLS_EXPORTED,
        entity_type="project_control_export",
        entity_id=project.pk,
        organization=organization,
        actor=actor,
        metadata={
            "project_id": str(project.pk),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload),
            "comparison_budget_id": comparison.budget_id if comparison else "",
            "advisory_overrun_count": len(exceptions.advisory_overruns),
            "open_register_count": len(exceptions.open_register_items),
        },
    )
    return payload
