from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.equipment.models import (
    Equipment,
    EquipmentAssignment,
    EquipmentAssignmentStatus,
    EquipmentOwnershipType,
    EquipmentStatus,
    MaintenanceRecord,
    MaintenanceStatus,
)
from apps.organizations.authorization import (
    get_active_membership,
    require_business_permission,
    scope_queryset,
)
from apps.organizations.models import BusinessPermissionCode, Organization
from apps.parties.models import BusinessParty
from apps.projects.models import Project, ProjectSite

_MANUAL_EQUIPMENT_STATUS_TRANSITIONS: dict[str, tuple[str, ...]] = {
    EquipmentStatus.AVAILABLE: (EquipmentStatus.INACTIVE, EquipmentStatus.RETIRED),
    EquipmentStatus.ASSIGNED: (),
    EquipmentStatus.MAINTENANCE: (),
    EquipmentStatus.INACTIVE: (EquipmentStatus.AVAILABLE, EquipmentStatus.RETIRED),
    EquipmentStatus.RETIRED: (),
}
_ASSIGNMENT_STATUS_TRANSITIONS: dict[str, tuple[str, ...]] = {
    EquipmentAssignmentStatus.SCHEDULED: (
        EquipmentAssignmentStatus.ACTIVE,
        EquipmentAssignmentStatus.CANCELLED,
    ),
    EquipmentAssignmentStatus.ACTIVE: (
        EquipmentAssignmentStatus.COMPLETED,
        EquipmentAssignmentStatus.CANCELLED,
    ),
    EquipmentAssignmentStatus.COMPLETED: (),
    EquipmentAssignmentStatus.CANCELLED: (),
}
_MAINTENANCE_STATUS_TRANSITIONS: dict[str, tuple[str, ...]] = {
    MaintenanceStatus.SCHEDULED: (
        MaintenanceStatus.IN_PROGRESS,
        MaintenanceStatus.COMPLETED,
        MaintenanceStatus.CANCELLED,
    ),
    MaintenanceStatus.IN_PROGRESS: (
        MaintenanceStatus.COMPLETED,
        MaintenanceStatus.CANCELLED,
    ),
    MaintenanceStatus.COMPLETED: (),
    MaintenanceStatus.CANCELLED: (),
}


def _require_permission(
    *,
    organization: Organization,
    user: User,
    permission: BusinessPermissionCode,
    management: bool = False,
    project: Project | None = None,
    site: ProjectSite | None = None,
    allow_any_scope: bool = False,
) -> None:
    require_business_permission(
        user=user,
        organization=organization,
        permission=permission,
        project=project,
        site=site,
        allow_any_scope=allow_any_scope,
        allow_site_parent=True,
        message=(
            "اجازه مدیریت تجهیزات این شرکت را ندارید."
            if management
            else "اجازه مشاهده تجهیزات این شرکت را ندارید."
        ),
    )


def _require_same_organization(
    organization: Organization,
    **records: Equipment
    | EquipmentAssignment
    | MaintenanceRecord
    | Project
    | ProjectSite
    | BusinessParty
    | None,
) -> None:
    if any(
        record is not None and record.organization_id != organization.pk
        for record in records.values()
    ):
        raise PermissionDenied("رکورد انتخاب‌شده متعلق به این شرکت نیست.")


def _save_validated(instance: object, message: str) -> None:
    try:
        instance.full_clean()
        instance.save()
    except (IntegrityError, ValidationError) as exc:
        raise ValueError(message) from exc


def _synchronize_equipment_status(equipment: Equipment, *, actor: User) -> Equipment:
    if equipment.status in {EquipmentStatus.INACTIVE, EquipmentStatus.RETIRED}:
        return equipment
    if equipment.maintenance_records.filter(
        status=MaintenanceStatus.IN_PROGRESS
    ).exists():
        status = EquipmentStatus.MAINTENANCE
    elif equipment.assignments.filter(status=EquipmentAssignmentStatus.ACTIVE).exists():
        status = EquipmentStatus.ASSIGNED
    else:
        status = EquipmentStatus.AVAILABLE
    if equipment.status != status:
        equipment.status = status
        equipment.updated_by = actor
        equipment.save(update_fields=["status", "updated_by", "updated_at"])
    return equipment


@transaction.atomic
def create_equipment(
    *,
    organization: Organization,
    actor: User,
    code: str,
    name: str,
    category: str,
    ownership_type: str = EquipmentOwnershipType.OWNED,
    manufacturer: str = "",
    model: str = "",
    serial_number: str = "",
    registration_number: str = "",
    acquired_on: date | None = None,
    notes: str = "",
) -> Equipment:
    _require_permission(
        organization=organization,
        user=actor,
        permission=BusinessPermissionCode.EQUIPMENT_CREATE,
        management=True,
    )
    equipment = Equipment(
        organization=organization,
        code=code,
        name=name,
        category=category,
        ownership_type=ownership_type,
        manufacturer=manufacturer,
        model=model,
        serial_number=serial_number,
        registration_number=registration_number,
        acquired_on=acquired_on,
        notes=notes,
        created_by=actor,
        updated_by=actor,
    )
    _save_validated(equipment, "اطلاعات تجهیز معتبر نیست یا کد آن تکراری است.")
    record_audit_event(
        action=AuditAction.EQUIPMENT_CREATED,
        entity_type="equipment",
        entity_id=equipment.pk,
        organization=organization,
        actor=actor,
        metadata={"code": equipment.code, "status": equipment.status},
    )
    return equipment


def get_organization_equipment(
    *, user: User, organization: Organization, include_archived: bool = False
) -> QuerySet[Equipment]:
    _require_permission(
        organization=organization,
        user=user,
        permission=BusinessPermissionCode.EQUIPMENT_VIEW,
    )
    equipment = Equipment.objects.filter(organization=organization)
    if not include_archived:
        equipment = equipment.filter(archived_at__isnull=True)
    return equipment


@transaction.atomic
def transition_equipment_status(
    *,
    organization: Organization,
    actor: User,
    equipment: Equipment,
    target_status: str,
) -> Equipment:
    _require_permission(
        organization=organization,
        user=actor,
        permission=BusinessPermissionCode.EQUIPMENT_CHANGE_STATUS,
        management=True,
    )
    locked = Equipment.objects.select_for_update().get(pk=equipment.pk)
    _require_same_organization(organization, equipment=locked)
    if target_status not in _MANUAL_EQUIPMENT_STATUS_TRANSITIONS.get(locked.status, ()):
        raise ValueError("این تغییر وضعیت تجهیز مجاز نیست.")
    if target_status in {EquipmentStatus.INACTIVE, EquipmentStatus.RETIRED} and (
        locked.assignments.filter(status=EquipmentAssignmentStatus.ACTIVE).exists()
        or locked.maintenance_records.filter(
            status=MaintenanceStatus.IN_PROGRESS
        ).exists()
    ):
        raise ValueError("تجهیز دارای تخصیص یا عملیات نگهداری فعال است.")
    previous_status = locked.status
    locked.status = target_status
    locked.updated_by = actor
    locked.save(update_fields=["status", "updated_by", "updated_at"])
    record_audit_event(
        action=AuditAction.EQUIPMENT_STATUS_CHANGED,
        entity_type="equipment",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"previous_status": previous_status, "new_status": target_status},
    )
    return locked


@transaction.atomic
def archive_equipment(
    *, organization: Organization, actor: User, equipment: Equipment
) -> Equipment:
    _require_permission(
        organization=organization,
        user=actor,
        permission=BusinessPermissionCode.EQUIPMENT_ARCHIVE,
        management=True,
    )
    locked = Equipment.objects.select_for_update().get(pk=equipment.pk)
    _require_same_organization(organization, equipment=locked)
    if locked.status != EquipmentStatus.RETIRED:
        raise ValueError("پیش از بایگانی، تجهیز باید از رده خارج شود.")
    if locked.archived_at is not None:
        raise ValueError("تجهیز قبلاً بایگانی شده است.")
    locked.archived_at = timezone.now()
    locked.updated_by = actor
    locked.save(update_fields=["archived_at", "updated_by", "updated_at"])
    record_audit_event(
        action=AuditAction.EQUIPMENT_ARCHIVED,
        entity_type="equipment",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"code": locked.code},
    )
    return locked


@transaction.atomic
def assign_equipment(
    *,
    organization: Organization,
    actor: User,
    equipment: Equipment,
    project: Project,
    start_date: date,
    end_date: date | None = None,
    site: ProjectSite | None = None,
    purpose: str = "",
    notes: str = "",
) -> EquipmentAssignment:
    _require_permission(
        organization=organization,
        user=actor,
        permission=BusinessPermissionCode.EQUIPMENT_ASSIGNMENTS_CREATE,
        management=True,
        project=project,
        site=site,
    )
    locked_equipment = Equipment.objects.select_for_update().get(pk=equipment.pk)
    _require_same_organization(
        organization,
        equipment=locked_equipment,
        project=project,
        site=site,
    )
    if locked_equipment.archived_at or locked_equipment.status in {
        EquipmentStatus.INACTIVE,
        EquipmentStatus.RETIRED,
        EquipmentStatus.MAINTENANCE,
    }:
        raise ValueError("این تجهیز در وضعیت قابل تخصیص نیست.")
    if project.deleted_at is not None:
        raise ValueError("امکان تخصیص تجهیز به پروژه بایگانی‌شده وجود ندارد.")
    if site is not None and (not site.is_active or site.project_id != project.pk):
        raise ValueError("کارگاه انتخاب‌شده برای این پروژه معتبر و فعال نیست.")
    today = timezone.localdate()
    if end_date is not None and end_date < today:
        status = EquipmentAssignmentStatus.COMPLETED
    elif start_date > today:
        status = EquipmentAssignmentStatus.SCHEDULED
    else:
        status = EquipmentAssignmentStatus.ACTIVE
    assignment = EquipmentAssignment(
        organization=organization,
        equipment=locked_equipment,
        project=project,
        site=site,
        start_date=start_date,
        end_date=end_date,
        status=status,
        purpose=purpose,
        notes=notes,
        created_by=actor,
        updated_by=actor,
    )
    _save_validated(
        assignment,
        "بازه تخصیص معتبر نیست یا با تخصیص دیگری از همین تجهیز هم‌پوشانی دارد.",
    )
    _synchronize_equipment_status(locked_equipment, actor=actor)
    record_audit_event(
        action=AuditAction.EQUIPMENT_ASSIGNMENT_CREATED,
        entity_type="equipment_assignment",
        entity_id=assignment.pk,
        organization=organization,
        actor=actor,
        metadata={
            "equipment_code": locked_equipment.code,
            "project_code": project.code,
            "status": status,
        },
    )
    return assignment


def get_organization_equipment_assignments(
    *,
    user: User,
    organization: Organization,
    equipment: Equipment | None = None,
    project: Project | None = None,
) -> QuerySet[EquipmentAssignment]:
    _require_permission(
        organization=organization,
        user=user,
        permission=BusinessPermissionCode.EQUIPMENT_ASSIGNMENTS_VIEW,
        project=project,
        allow_any_scope=project is None,
    )
    _require_same_organization(organization, equipment=equipment, project=project)
    assignments = EquipmentAssignment.objects.filter(organization=organization)
    if equipment is not None:
        assignments = assignments.filter(equipment=equipment)
    if project is not None:
        assignments = assignments.filter(project=project)
    membership = get_active_membership(user=user, organization=organization)
    return scope_queryset(
        assignments,
        membership=membership,
        project_lookup="project_id",
        site_lookup="site_id",
    ).select_related("equipment", "project", "site")


@transaction.atomic
def transition_equipment_assignment_status(
    *,
    organization: Organization,
    actor: User,
    assignment: EquipmentAssignment,
    target_status: str,
    effective_date: date,
) -> EquipmentAssignment:
    locked = (
        EquipmentAssignment.objects.select_for_update()
        .select_related("equipment")
        .get(pk=assignment.pk)
    )
    _require_permission(
        organization=organization,
        user=actor,
        permission=BusinessPermissionCode.EQUIPMENT_ASSIGNMENTS_TRANSITION,
        management=True,
        project=locked.project,
        site=locked.site,
    )
    _require_same_organization(organization, assignment=locked)
    if target_status not in _ASSIGNMENT_STATUS_TRANSITIONS.get(locked.status, ()):
        raise ValueError("این تغییر وضعیت تخصیص تجهیز مجاز نیست.")
    locked_equipment = Equipment.objects.select_for_update().get(pk=locked.equipment_id)
    if target_status == EquipmentAssignmentStatus.ACTIVE:
        if effective_date < locked.start_date or (
            locked.end_date and effective_date > locked.end_date
        ):
            raise ValueError("تاریخ فعال‌سازی باید در بازه تخصیص باشد.")
        if locked_equipment.status in {
            EquipmentStatus.INACTIVE,
            EquipmentStatus.RETIRED,
            EquipmentStatus.MAINTENANCE,
        }:
            raise ValueError("تجهیز در وضعیت قابل فعال‌سازی نیست.")
    previous_status = locked.status
    locked.status = target_status
    if target_status == EquipmentAssignmentStatus.COMPLETED or (
        target_status == EquipmentAssignmentStatus.CANCELLED
        and previous_status == EquipmentAssignmentStatus.ACTIVE
        and (locked.end_date is None or effective_date < locked.end_date)
    ):
        locked.end_date = effective_date
    locked.updated_by = actor
    _save_validated(locked, "تاریخ یا وضعیت تخصیص تجهیز معتبر نیست.")
    _synchronize_equipment_status(locked_equipment, actor=actor)
    record_audit_event(
        action=AuditAction.EQUIPMENT_ASSIGNMENT_STATUS_CHANGED,
        entity_type="equipment_assignment",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"previous_status": previous_status, "new_status": target_status},
    )
    return locked


@transaction.atomic
def create_maintenance_record(
    *,
    organization: Organization,
    actor: User,
    equipment: Equipment,
    record_number: str,
    maintenance_type: str,
    summary: str,
    scheduled_date: date,
    project: Project | None = None,
    site: ProjectSite | None = None,
    provider: BusinessParty | None = None,
    description: str = "",
    cost: Decimal | None = None,
    notes: str = "",
) -> MaintenanceRecord:
    from apps.workflows.runtime import WorkflowConflict

    from .workflow import start_maintenance_workflow

    _require_permission(
        organization=organization,
        user=actor,
        permission=BusinessPermissionCode.MAINTENANCE_RECORDS_CREATE,
        management=True,
        project=project,
        site=site,
    )
    locked_equipment = Equipment.objects.select_for_update().get(pk=equipment.pk)
    _require_same_organization(
        organization,
        equipment=locked_equipment,
        project=project,
        site=site,
        provider=provider,
    )
    if (
        locked_equipment.archived_at
        or locked_equipment.status == EquipmentStatus.RETIRED
    ):
        raise ValueError(
            "برای تجهیز بایگانی‌شده یا از رده خارج سابقه جدید ایجاد نمی‌شود."
        )
    if site is not None and (project is None or site.project_id != project.pk):
        raise ValueError("کارگاه انتخاب‌شده باید متعلق به پروژه باشد.")
    record = MaintenanceRecord(
        organization=organization,
        equipment=locked_equipment,
        project=project,
        site=site,
        provider=provider,
        record_number=record_number,
        maintenance_type=maintenance_type,
        summary=summary,
        description=description,
        scheduled_date=scheduled_date,
        cost=cost,
        notes=notes,
        created_by=actor,
        updated_by=actor,
    )
    _save_validated(record, "اطلاعات سابقه نگهداری معتبر نیست یا شماره آن تکراری است.")
    record_audit_event(
        action=AuditAction.MAINTENANCE_RECORD_CREATED,
        entity_type="maintenance_record",
        entity_id=record.pk,
        organization=organization,
        actor=actor,
        metadata={
            "equipment_code": locked_equipment.code,
            "maintenance_type": maintenance_type,
        },
    )
    try:
        start_maintenance_workflow(
            organization=organization, record=record, actor=actor
        )
    except (PermissionDenied, WorkflowConflict):
        # An unroutable scheduled record retains the legacy direct path.
        pass
    return record


def get_organization_maintenance_records(
    *,
    user: User,
    organization: Organization,
    equipment: Equipment | None = None,
) -> QuerySet[MaintenanceRecord]:
    _require_permission(
        organization=organization,
        user=user,
        permission=BusinessPermissionCode.MAINTENANCE_RECORDS_VIEW,
        allow_any_scope=True,
    )
    _require_same_organization(organization, equipment=equipment)
    records = MaintenanceRecord.objects.filter(organization=organization)
    if equipment is not None:
        records = records.filter(equipment=equipment)
    membership = get_active_membership(user=user, organization=organization)
    return scope_queryset(
        records,
        membership=membership,
        project_lookup="project_id",
        site_lookup="site_id",
    ).select_related("equipment", "project", "site", "provider")


@transaction.atomic
def _transition_maintenance_status_domain(
    *,
    organization: Organization,
    actor: User,
    record: MaintenanceRecord,
    target_status: str,
    effective_date: date,
    cost: Decimal | None = None,
) -> MaintenanceRecord:
    locked = (
        MaintenanceRecord.objects.select_for_update()
        .select_related("equipment")
        .get(pk=record.pk)
    )
    _require_permission(
        organization=organization,
        user=actor,
        permission=BusinessPermissionCode.MAINTENANCE_RECORDS_TRANSITION,
        management=True,
        project=locked.project,
        site=locked.site,
    )
    _require_same_organization(organization, record=locked)
    if target_status not in _MAINTENANCE_STATUS_TRANSITIONS.get(locked.status, ()):
        raise ValueError("این تغییر وضعیت سرویس یا تعمیر مجاز نیست.")
    locked_equipment = Equipment.objects.select_for_update().get(pk=locked.equipment_id)
    previous_status = locked.status
    locked.status = target_status
    if target_status == MaintenanceStatus.IN_PROGRESS:
        locked.started_date = effective_date
    elif target_status == MaintenanceStatus.COMPLETED:
        locked.started_date = locked.started_date or min(
            locked.scheduled_date, effective_date
        )
        locked.completed_date = effective_date
        if cost is not None:
            locked.cost = cost
    locked.updated_by = actor
    _save_validated(locked, "تاریخ یا وضعیت سابقه نگهداری معتبر نیست.")
    _synchronize_equipment_status(locked_equipment, actor=actor)
    record_audit_event(
        action=AuditAction.MAINTENANCE_STATUS_CHANGED,
        entity_type="maintenance_record",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"previous_status": previous_status, "new_status": target_status},
    )
    return locked


def transition_maintenance_status(
    *,
    organization: Organization,
    actor: User,
    record: MaintenanceRecord,
    target_status: str,
    effective_date: date,
    cost: Decimal | None = None,
) -> MaintenanceRecord:
    """Use the shared work runtime when the record has an active instance."""

    from .workflow import perform_maintenance_transition

    return perform_maintenance_transition(
        organization=organization,
        actor=actor,
        record=record,
        target_status=target_status,
        effective_date=effective_date,
        cost=cost,
    )
