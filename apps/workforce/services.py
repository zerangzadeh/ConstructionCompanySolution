from collections.abc import Mapping
from datetime import date

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.documents.link_registry import create_typed_link
from apps.documents.models import Document
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import (
    BusinessPermissionCode,
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationStatus,
)
from apps.projects.models import Project, ProjectSite
from apps.workforce.models import (
    AssignmentStatus,
    Competency,
    Department,
    Employee,
    EmployeePositionAssignment,
    EmployeeProjectAssignment,
    EmployeeQualification,
    EmployeeQualificationLifecycleEvent,
    EmployeeSkillRecord,
    EmployeeStatus,
    EmployeeTrainingRecord,
    LaborRateVersion,
    PerformanceEvaluation,
    Position,
    PositionAssignmentStatus,
    QualificationKind,
    QualificationLifecycleEventKind,
    Skill,
    TrainingOutcome,
    TrainingRequirement,
    WorkTeam,
)

from .identity_integrity import identity_write_lock

_EMPLOYEE_STATUS_TRANSITIONS: dict[str, tuple[str, ...]] = {
    EmployeeStatus.ACTIVE: (EmployeeStatus.INACTIVE, EmployeeStatus.TERMINATED),
    EmployeeStatus.INACTIVE: (EmployeeStatus.ACTIVE, EmployeeStatus.TERMINATED),
    EmployeeStatus.TERMINATED: (),
}
_ASSIGNMENT_STATUS_TRANSITIONS: dict[str, tuple[str, ...]] = {
    AssignmentStatus.ACTIVE: (
        AssignmentStatus.COMPLETED,
        AssignmentStatus.CANCELLED,
    ),
    AssignmentStatus.COMPLETED: (),
    AssignmentStatus.CANCELLED: (),
}
CHIEF_EXECUTIVE_POSITION_CODE = "CEO"


def _require_active_access(
    *,
    organization: Organization,
    user: User,
    permission: BusinessPermissionCode,
) -> None:
    if not user.is_authenticated or not user.is_active:
        raise PermissionDenied("ورود به حساب کاربری الزامی است.")
    if (
        organization.status != OrganizationStatus.ACTIVE
        or organization.deleted_at is not None
    ):
        raise PermissionDenied("سازمان فعال نیست.")
    require_business_permission(
        user=user,
        organization=organization,
        permission=permission,
        message="اجازه مشاهده اطلاعات نیروی انسانی این شرکت را ندارید.",
    )


def _require_management_access(
    *,
    organization: Organization,
    actor: User,
    permission: BusinessPermissionCode,
) -> None:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        message="اجازه مدیریت نیروی انسانی این شرکت را ندارید.",
    )


def _save_validated(instance: object, error_message: str) -> None:
    try:
        instance.full_clean()
        instance.save()
    except (IntegrityError, ValidationError) as exc:
        raise ValueError(error_message) from exc


def _require_active_master(
    record: Department | Position | WorkTeam, label: str
) -> None:
    if record.archived_at is not None or not record.is_active:
        raise ValueError(f"{label} انتخاب‌شده فعال نیست.")


def _require_same_organization(
    organization: Organization,
    **records: Department
    | Position
    | WorkTeam
    | Employee
    | Project
    | ProjectSite
    | None,
) -> None:
    if any(
        record is not None and record.organization_id != organization.pk
        for record in records.values()
    ):
        raise PermissionDenied("رکورد مرتبط نیروی انسانی متعلق به سازمان دیگری است.")


@transaction.atomic
def create_department(
    *,
    organization: Organization,
    actor: User,
    code: str,
    name: str,
    parent: Department | None = None,
    description: str = "",
) -> Department:
    _require_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.DEPARTMENTS_CREATE,
    )
    _require_same_organization(organization, parent=parent)
    if parent is not None:
        _require_active_master(parent, "parent department")
    department = Department(
        organization=organization,
        parent=parent,
        code=code,
        name=name,
        description=description.strip(),
        created_by=actor,
        updated_by=actor,
    )
    _save_validated(department, "اطلاعات واحد سازمانی معتبر نیست یا کد آن تکراری است.")
    record_audit_event(
        action=AuditAction.DEPARTMENT_CREATED,
        entity_type="department",
        entity_id=department.pk,
        organization=organization,
        actor=actor,
        metadata={"code": department.code},
    )
    return department


@transaction.atomic
def update_department(
    *,
    organization: Organization,
    actor: User,
    department: Department,
    code: str,
    name: str,
    parent: Department | None = None,
    description: str = "",
) -> Department:
    _require_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.DEPARTMENTS_CHANGE,
    )
    _require_same_organization(organization, department=department, parent=parent)
    locked = Department.objects.select_for_update().get(pk=department.pk)
    if locked.archived_at is not None:
        raise ValueError("واحد سازمانی بایگانی‌شده قابل ویرایش نیست.")
    locked_parent = None
    if parent is not None:
        locked_parent = Department.objects.select_for_update().get(pk=parent.pk)
        _require_same_organization(organization, parent=locked_parent)
        _require_active_master(locked_parent, "parent department")

    previous_code = locked.code
    locked.code = code
    locked.name = name
    locked.parent = locked_parent
    locked.description = description.strip()
    locked.updated_by = actor
    _save_validated(locked, "اطلاعات واحد سازمانی معتبر نیست یا کد آن تکراری است.")
    record_audit_event(
        action=AuditAction.DEPARTMENT_UPDATED,
        entity_type="department",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"previous_code": previous_code, "code": locked.code},
    )
    return locked


@transaction.atomic
def create_position(
    *,
    organization: Organization,
    actor: User,
    code: str,
    title: str,
    department: Department | None = None,
    parent_position: Position | None = None,
    description: str = "",
    is_single_holder: bool = False,
) -> Position:
    _require_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.POSITIONS_CREATE,
    )
    _require_same_organization(
        organization, department=department, parent_position=parent_position
    )
    if department is not None:
        _require_active_master(department, "department")
    locked_parent = None
    if parent_position is not None:
        locked_parent = Position.objects.select_for_update().get(pk=parent_position.pk)
        _require_same_organization(organization, parent_position=locked_parent)
        _require_active_master(locked_parent, "parent position")
    position = Position(
        organization=organization,
        department=department,
        parent_position=locked_parent,
        code=code,
        title=title,
        description=description.strip(),
        is_single_holder=is_single_holder,
        created_by=actor,
        updated_by=actor,
    )
    _save_validated(position, "اطلاعات سمت شغلی معتبر نیست یا کد آن تکراری است.")
    record_audit_event(
        action=AuditAction.POSITION_CREATED,
        entity_type="position",
        entity_id=position.pk,
        organization=organization,
        actor=actor,
        metadata={"code": position.code},
    )
    return position


@transaction.atomic
def update_position(
    *,
    organization: Organization,
    actor: User,
    position: Position,
    code: str,
    title: str,
    department: Department | None = None,
    parent_position: Position | None = None,
    description: str = "",
    is_single_holder: bool = False,
) -> Position:
    _require_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.POSITIONS_CHANGE,
    )
    _require_same_organization(
        organization,
        position=position,
        department=department,
        parent_position=parent_position,
    )
    locked = Position.objects.select_for_update().get(pk=position.pk)
    if locked.archived_at is not None:
        raise ValueError("سمت شغلی بایگانی‌شده قابل ویرایش نیست.")
    if department is not None:
        _require_active_master(department, "department")
    locked_parent = None
    if parent_position is not None:
        locked_parent = Position.objects.select_for_update().get(pk=parent_position.pk)
        _require_same_organization(organization, parent_position=locked_parent)
        _require_active_master(locked_parent, "parent position")

    active_assignments = EmployeePositionAssignment.objects.filter(
        organization=organization,
        position=locked,
        status=PositionAssignmentStatus.ACTIVE,
    )
    if is_single_holder and active_assignments.count() > 1:
        raise ValueError("سمتی که بیش از یک متصدی فعال دارد نمی‌تواند تک‌متصدی شود.")
    if (
        department is not None
        and active_assignments.filter(is_primary=True)
        .exclude(employee__department=department)
        .exists()
    ):
        raise ValueError(
            "واحد سازمانی سمت باید با واحد کارمند دارای سمت اصلی سازگار باشد."
        )

    previous_code = locked.code
    locked.code = code
    locked.title = title
    locked.department = department
    locked.parent_position = locked_parent
    locked.description = description.strip()
    locked.is_single_holder = is_single_holder
    locked.updated_by = actor
    _save_validated(locked, "اطلاعات سمت شغلی معتبر نیست یا کد آن تکراری است.")
    record_audit_event(
        action=AuditAction.POSITION_UPDATED,
        entity_type="position",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"previous_code": previous_code, "code": locked.code},
    )
    return locked


@transaction.atomic
def create_work_team(
    *,
    organization: Organization,
    actor: User,
    code: str,
    name: str,
    department: Department | None = None,
    lead: Employee | None = None,
    description: str = "",
) -> WorkTeam:
    _require_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.WORK_TEAMS_CREATE,
    )
    _require_same_organization(organization, department=department, lead=lead)
    if department is not None:
        _require_active_master(department, "department")
    if lead is not None and (
        lead.archived_at is not None or lead.status != EmployeeStatus.ACTIVE
    ):
        raise ValueError("فقط کارمند فعال می‌تواند سرپرست گروه کاری باشد.")
    team = WorkTeam(
        organization=organization,
        department=department,
        lead=lead,
        code=code,
        name=name,
        description=description.strip(),
        created_by=actor,
        updated_by=actor,
    )
    _save_validated(team, "اطلاعات گروه کاری معتبر نیست یا کد آن تکراری است.")
    record_audit_event(
        action=AuditAction.WORK_TEAM_CREATED,
        entity_type="work_team",
        entity_id=team.pk,
        organization=organization,
        actor=actor,
        metadata={"code": team.code},
    )
    return team


def _assign_employee_position_locked(
    *,
    organization: Organization,
    actor: User,
    employee: Employee,
    position: Position,
    start_date: date,
    is_primary: bool,
    notes: str = "",
) -> EmployeePositionAssignment:
    """Create an assignment after the employee and position rows are locked."""

    _require_same_organization(organization, employee=employee, position=position)
    _require_active_master(position, "position")
    if employee.archived_at is not None or employee.status != EmployeeStatus.ACTIVE:
        raise ValueError("فقط کارمند فعال می‌تواند سمت فعال دریافت کند.")

    active_assignments = EmployeePositionAssignment.objects.filter(
        organization=organization,
        employee=employee,
        status=PositionAssignmentStatus.ACTIVE,
    )
    if active_assignments.filter(position=position).exists():
        raise ValueError("این سمت از قبل به‌صورت فعال به کارمند تخصیص یافته است.")
    if (
        position.is_single_holder
        and EmployeePositionAssignment.objects.filter(
            organization=organization,
            position=position,
            status=PositionAssignmentStatus.ACTIVE,
        ).exists()
    ):
        raise ValueError("این سمت تک‌متصدی در حال حاضر متصدی فعال دارد.")

    make_primary = is_primary or not active_assignments.exists()
    if (
        make_primary
        and employee.department_id
        and position.department_id
        and employee.department_id != position.department_id
    ):
        raise ValueError("سمت اصلی باید متعلق به واحد سازمانی کارمند باشد.")
    if make_primary:
        active_assignments.filter(is_primary=True).update(
            is_primary=False,
            updated_by=actor,
            updated_at=timezone.now(),
        )

    assignment = EmployeePositionAssignment(
        organization=organization,
        employee=employee,
        position=position,
        start_date=start_date,
        is_primary=make_primary,
        notes=notes.strip(),
        created_by=actor,
        updated_by=actor,
    )
    _save_validated(assignment, "اطلاعات تخصیص سمت معتبر نیست یا تکراری است.")

    if make_primary:
        employee.position = position
        if employee.department_id is None and position.department_id is not None:
            employee.department = position.department
        employee.updated_by = actor
        employee.save(
            update_fields=["position", "department", "updated_by", "updated_at"]
        )

    record_audit_event(
        action=AuditAction.EMPLOYEE_POSITION_ASSIGNED,
        entity_type="employee_position_assignment",
        entity_id=assignment.pk,
        organization=organization,
        actor=actor,
        metadata={
            "employee_number": employee.employee_number,
            "position_code": position.code,
            "is_primary": make_primary,
        },
    )
    return assignment


@transaction.atomic
def assign_employee_position(
    *,
    organization: Organization,
    actor: User,
    employee: Employee,
    position: Position,
    start_date: date,
    is_primary: bool = False,
    notes: str = "",
) -> EmployeePositionAssignment:
    _require_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.EMPLOYEE_POSITIONS_ASSIGN,
    )
    locked_position = Position.objects.select_for_update().get(pk=position.pk)
    locked_employee = (
        Employee.objects.select_for_update(of=("self",))
        .select_related("department")
        .get(pk=employee.pk)
    )
    return _assign_employee_position_locked(
        organization=organization,
        actor=actor,
        employee=locked_employee,
        position=locked_position,
        start_date=start_date,
        is_primary=is_primary,
        notes=notes,
    )


@transaction.atomic
def create_employee(
    *,
    organization: Organization,
    actor: User,
    employee_number: str,
    first_name: str,
    last_name: str,
    user: User | None = None,
    department: Department | None = None,
    position: Position | None = None,
    work_team: WorkTeam | None = None,
    email: str = "",
    phone_number: str = "",
    hire_date: date | None = None,
) -> Employee:
    _require_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.EMPLOYEES_CREATE,
    )
    if user is not None:
        _require_management_access(
            organization=organization,
            actor=actor,
            permission=BusinessPermissionCode.EMPLOYEES_LINK_ACCOUNT,
        )
        if (
            not user.is_active
            or not OrganizationMembership.objects.filter(
                organization=organization,
                user=user,
                status=MembershipStatus.ACTIVE,
            ).exists()
        ):
            raise PermissionDenied("حساب انتخاب‌شده عضو فعال این شرکت نیست.")
        if Employee.objects.filter(organization=organization, user=user).exists():
            raise ValueError("این حساب قبلاً به کارمند دیگری متصل شده است.")
    _require_same_organization(
        organization,
        department=department,
        position=position,
        work_team=work_team,
    )
    for record, label in (
        (department, "department"),
        (position, "position"),
        (work_team, "work team"),
    ):
        if record is not None:
            _require_active_master(record, label)
    employee = Employee(
        organization=organization,
        user=user,
        department=department,
        position=position,
        work_team=work_team,
        employee_number=employee_number,
        first_name=first_name,
        last_name=last_name,
        email=email.strip(),
        phone_number=phone_number.strip(),
        hire_date=hire_date,
        created_by=actor,
        updated_by=actor,
    )
    _save_validated(employee, "اطلاعات کارمند معتبر نیست یا از قبل وجود دارد.")
    record_audit_event(
        action=AuditAction.EMPLOYEE_CREATED,
        entity_type="employee",
        entity_id=employee.pk,
        organization=organization,
        actor=actor,
        metadata={"employee_number": employee.employee_number},
    )
    if user is not None:
        record_audit_event(
            action=AuditAction.EMPLOYEE_ACCOUNT_LINKED,
            entity_type="employee",
            entity_id=employee.pk,
            organization=organization,
            actor=actor,
            metadata={"target_user_id": str(user.pk), "target_username": user.username},
        )
    if position is not None:
        locked_position = Position.objects.select_for_update().get(pk=position.pk)
        _assign_employee_position_locked(
            organization=organization,
            actor=actor,
            employee=employee,
            position=locked_position,
            start_date=hire_date or timezone.localdate(),
            is_primary=True,
        )
    return employee


@identity_write_lock()
@transaction.atomic
def create_employee_from_member(
    *,
    organization: Organization,
    actor: User,
    employee_number: str,
    user: User,
    department: Department | None = None,
    position: Position | None = None,
    work_team: WorkTeam | None = None,
    hire_date: date | None = None,
) -> Employee:
    """Create personnel data from an account provisioned to this tenant."""

    _require_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.EMPLOYEES_CREATE,
    )
    _require_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.EMPLOYEES_LINK_ACCOUNT,
    )
    locked_user = (
        User.objects.select_for_update().filter(pk=user.pk, is_active=True).first()
    )
    if (
        locked_user is None
        or not OrganizationMembership.objects.select_for_update()
        .filter(
            organization=organization,
            user=locked_user,
            status=MembershipStatus.ACTIVE,
        )
        .exists()
    ):
        raise PermissionDenied("حساب انتخاب‌شده عضو فعال این شرکت نیست.")
    if Employee.objects.filter(organization=organization, user=locked_user).exists():
        raise ValueError("برای این حساب قبلاً پرونده کارمند ثبت شده است.")
    first_name = locked_user.first_name.strip()
    last_name = locked_user.last_name.strip()
    if not first_name or not last_name:
        raise ValueError(
            "نام و نام خانوادگی کاربر کامل نیست؛ ابتدا ادمین مشخصات حساب را تکمیل کند."
        )
    return create_employee(
        organization=organization,
        actor=actor,
        employee_number=employee_number,
        first_name=first_name,
        last_name=last_name,
        user=locked_user,
        department=department,
        position=position,
        work_team=work_team,
        email=locked_user.email,
        phone_number=locked_user.phone_number,
        hire_date=hire_date,
    )


@identity_write_lock()
@transaction.atomic
def link_employee_account(
    *, organization: Organization, actor: User, employee: Employee, user: User
) -> Employee:
    """Link one active tenant member to one employee with tenant authorization."""

    _require_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.EMPLOYEES_LINK_ACCOUNT,
    )
    locked_employee = Employee.objects.select_for_update().get(pk=employee.pk)
    _require_same_organization(organization, employee=locked_employee)
    if locked_employee.user_id is not None:
        raise ValueError("این کارمند از قبل حساب کاربری دارد.")
    if not OrganizationMembership.objects.filter(
        organization=organization,
        user=user,
        status=MembershipStatus.ACTIVE,
    ).exists():
        raise PermissionDenied("حساب انتخاب‌شده عضو فعال این شرکت نیست.")
    if Employee.objects.filter(organization=organization, user=user).exists():
        raise ValueError("این حساب قبلاً به کارمند دیگری متصل شده است.")
    locked_employee.user = user
    locked_employee.updated_by = actor
    _save_validated(locked_employee, "اتصال حساب کاربری معتبر نیست.")
    record_audit_event(
        action=AuditAction.EMPLOYEE_ACCOUNT_LINKED,
        entity_type="employee",
        entity_id=locked_employee.pk,
        organization=organization,
        actor=actor,
        metadata={"target_user_id": str(user.pk), "target_username": user.username},
    )
    return locked_employee


@identity_write_lock()
@transaction.atomic
def unlink_employee_account(
    *, organization: Organization, actor: User, employee: Employee
) -> Employee:
    """Detach authentication identity without deleting either business record."""

    _require_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.EMPLOYEES_LINK_ACCOUNT,
    )
    locked_employee = Employee.objects.select_for_update().get(pk=employee.pk)
    _require_same_organization(organization, employee=locked_employee)
    if locked_employee.user_id is None:
        raise ValueError("این کارمند حساب متصل‌شده‌ای ندارد.")
    previous_user = locked_employee.user
    locked_employee.user = None
    locked_employee.updated_by = actor
    locked_employee.save(update_fields=["user", "updated_by", "updated_at"])
    record_audit_event(
        action=AuditAction.EMPLOYEE_ACCOUNT_UNLINKED,
        entity_type="employee",
        entity_id=locked_employee.pk,
        organization=organization,
        actor=actor,
        metadata={
            "target_user_id": str(previous_user.pk),
            "target_username": previous_user.username,
        },
    )
    return locked_employee


@transaction.atomic
def update_employee_profile_image(
    *,
    organization: Organization,
    actor: User,
    employee: Employee,
    data: Mapping[str, object],
) -> Employee:
    """Update an employee-owned image without changing the linked user profile."""

    _require_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.EMPLOYEES_CHANGE_PROFILE_IMAGE,
    )
    locked_employee = Employee.objects.select_for_update().get(pk=employee.pk)
    _require_same_organization(organization, employee=locked_employee)
    old_image_name = locked_employee.profile_image.name
    locked_employee.profile_image = data["profile_image"]
    locked_employee.updated_by = actor
    _save_validated(locked_employee, "عکس پرسنلی انتخاب‌شده معتبر نیست.")
    new_image_name = locked_employee.profile_image.name
    if old_image_name and old_image_name != new_image_name:
        storage = locked_employee.profile_image.storage
        transaction.on_commit(lambda: storage.delete(old_image_name))
    record_audit_event(
        action=AuditAction.EMPLOYEE_PROFILE_IMAGE_UPDATED,
        entity_type="employee",
        entity_id=locked_employee.pk,
        organization=organization,
        actor=actor,
        metadata={
            "had_image": bool(old_image_name),
            "has_image": bool(new_image_name),
        },
    )
    return locked_employee


def get_organization_employees(
    *, user: User, organization: Organization, include_archived: bool = False
) -> QuerySet[Employee]:
    _require_active_access(
        organization=organization,
        user=user,
        permission=BusinessPermissionCode.EMPLOYEES_VIEW,
    )
    employees = Employee.objects.filter(organization=organization)
    if not include_archived:
        employees = employees.filter(archived_at__isnull=True)
    return employees.select_related("user", "department", "position", "work_team")


def get_active_chief_executive(
    *, user: User, organization: Organization
) -> Employee | None:
    """Return the current CEO defined by the reserved, single-holder position."""
    _require_active_access(
        organization=organization,
        user=user,
        permission=BusinessPermissionCode.EMPLOYEES_VIEW,
    )
    _require_active_access(
        organization=organization,
        user=user,
        permission=BusinessPermissionCode.POSITIONS_VIEW,
    )
    assignment = (
        EmployeePositionAssignment.objects.filter(
            organization=organization,
            status=PositionAssignmentStatus.ACTIVE,
            is_primary=True,
            position__code=CHIEF_EXECUTIVE_POSITION_CODE,
            position__department__isnull=True,
            position__is_single_holder=True,
            position__is_active=True,
            position__archived_at__isnull=True,
            employee__status=EmployeeStatus.ACTIVE,
            employee__archived_at__isnull=True,
        )
        .select_related("employee", "employee__position", "position")
        .first()
    )
    return assignment.employee if assignment is not None else None


def get_active_department_position_assignments(
    *, user: User, organization: Organization
) -> QuerySet[EmployeePositionAssignment]:
    """Return active position holders for the tenant-scoped organization chart."""
    _require_active_access(
        organization=organization,
        user=user,
        permission=BusinessPermissionCode.EMPLOYEES_VIEW,
    )
    _require_active_access(
        organization=organization,
        user=user,
        permission=BusinessPermissionCode.POSITIONS_VIEW,
    )
    return (
        EmployeePositionAssignment.objects.filter(
            organization=organization,
            status=PositionAssignmentStatus.ACTIVE,
            employee__status=EmployeeStatus.ACTIVE,
            employee__archived_at__isnull=True,
            position__is_active=True,
            position__archived_at__isnull=True,
        )
        .select_related(
            "employee",
            "employee__user",
            "position",
            "position__department",
            "position__parent_position",
        )
        .order_by(
            "position__department__name",
            "employee__last_name",
            "employee__first_name",
            "position__title",
        )
    )


def get_employee_position_assignments(
    *,
    user: User,
    organization: Organization,
    employee: Employee,
) -> QuerySet[EmployeePositionAssignment]:
    _require_active_access(
        organization=organization,
        user=user,
        permission=BusinessPermissionCode.EMPLOYEES_VIEW,
    )
    if employee.organization_id != organization.pk:
        raise PermissionDenied("کارمند متعلق به این سازمان نیست.")
    return EmployeePositionAssignment.objects.filter(
        organization=organization,
        employee=employee,
    ).select_related("position", "position__department")


@transaction.atomic
def end_employee_position(
    *,
    organization: Organization,
    actor: User,
    assignment: EmployeePositionAssignment,
    end_date: date,
) -> EmployeePositionAssignment:
    _require_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.EMPLOYEE_POSITIONS_END,
    )
    locked = (
        EmployeePositionAssignment.objects.select_for_update()
        .select_related("employee", "position")
        .get(pk=assignment.pk)
    )
    if locked.organization_id != organization.pk:
        raise PermissionDenied("تخصیص سمت متعلق به این سازمان نیست.")
    if locked.status != PositionAssignmentStatus.ACTIVE:
        raise ValueError("این تخصیص سمت از قبل پایان یافته است.")

    employee = Employee.objects.select_for_update().get(pk=locked.employee_id)
    locked.status = PositionAssignmentStatus.ENDED
    locked.end_date = end_date
    locked.is_primary = False
    locked.updated_by = actor
    try:
        locked.save(
            update_fields=[
                "status",
                "end_date",
                "is_primary",
                "updated_by",
                "updated_at",
            ]
        )
    except ValidationError as exc:
        raise ValueError("تاریخ پایان تخصیص سمت معتبر نیست.") from exc

    replacement = (
        EmployeePositionAssignment.objects.filter(
            organization=organization,
            employee=employee,
            status=PositionAssignmentStatus.ACTIVE,
        )
        .select_related("position")
        .order_by("-start_date", "created_at")
        .first()
    )
    if employee.position_id == locked.position_id:
        employee.position = replacement.position if replacement is not None else None
        if replacement is not None and replacement.position.department_id is not None:
            employee.department = replacement.position.department
        employee.updated_by = actor
        employee.save(
            update_fields=["position", "department", "updated_by", "updated_at"]
        )
        if replacement is not None:
            replacement.is_primary = True
            replacement.updated_by = actor
            replacement.save(update_fields=["is_primary", "updated_by", "updated_at"])

    record_audit_event(
        action=AuditAction.EMPLOYEE_POSITION_ENDED,
        entity_type="employee_position_assignment",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={
            "employee_number": employee.employee_number,
            "position_code": locked.position.code,
        },
    )
    return locked


def get_organization_departments(
    *, user: User, organization: Organization
) -> QuerySet[Department]:
    _require_active_access(
        organization=organization,
        user=user,
        permission=BusinessPermissionCode.DEPARTMENTS_VIEW,
    )
    return Department.objects.filter(
        organization=organization, archived_at__isnull=True
    ).select_related("parent")


def get_organization_positions(
    *, user: User, organization: Organization
) -> QuerySet[Position]:
    _require_active_access(
        organization=organization,
        user=user,
        permission=BusinessPermissionCode.POSITIONS_VIEW,
    )
    return Position.objects.filter(
        organization=organization, archived_at__isnull=True
    ).select_related("department", "parent_position")


def get_organization_work_teams(
    *, user: User, organization: Organization
) -> QuerySet[WorkTeam]:
    _require_active_access(
        organization=organization,
        user=user,
        permission=BusinessPermissionCode.WORK_TEAMS_VIEW,
    )
    return WorkTeam.objects.filter(
        organization=organization, archived_at__isnull=True
    ).select_related("department", "lead")


@transaction.atomic
def transition_employee_status(
    *,
    organization: Organization,
    actor: User,
    employee: Employee,
    target_status: str,
    effective_date: date | None = None,
) -> Employee:
    _require_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.EMPLOYEES_CHANGE_STATUS,
    )
    locked = Employee.objects.select_for_update().get(pk=employee.pk)
    if locked.organization_id != organization.pk:
        raise PermissionDenied("کارمند متعلق به این سازمان نیست.")
    if target_status not in _EMPLOYEE_STATUS_TRANSITIONS.get(locked.status, ()):
        raise ValueError("این تغییر وضعیت کارمند مجاز نیست.")
    if (
        target_status != EmployeeStatus.ACTIVE
        and locked.project_assignments.filter(status=AssignmentStatus.ACTIVE).exists()
    ):
        raise ValueError("پیش از تغییر وضعیت، مأموریت‌های فعال پروژه را خاتمه دهید.")
    previous_status = locked.status
    locked.status = target_status
    locked.termination_date = (
        effective_date or timezone.localdate()
        if target_status == EmployeeStatus.TERMINATED
        else None
    )
    locked.updated_by = actor
    try:
        locked.save(
            update_fields=["status", "termination_date", "updated_by", "updated_at"]
        )
    except ValidationError as exc:
        raise ValueError("اطلاعات وضعیت کارمند معتبر نیست.") from exc
    record_audit_event(
        action=AuditAction.EMPLOYEE_STATUS_CHANGED,
        entity_type="employee",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"previous_status": previous_status, "new_status": target_status},
    )
    return locked


@transaction.atomic
def assign_employee_to_project(
    *,
    organization: Organization,
    actor: User,
    employee: Employee,
    project: Project,
    start_date: date,
    site: ProjectSite | None = None,
    role_title: str = "",
    notes: str = "",
    planned_end_date: date | None = None,
) -> EmployeeProjectAssignment:
    _require_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.PROJECT_ASSIGNMENTS_CREATE,
    )
    _require_same_organization(
        organization,
        employee=employee,
        project=project,
        site=site,
    )
    if employee.status != EmployeeStatus.ACTIVE or employee.archived_at is not None:
        raise ValueError("فقط کارمند فعال قابل تخصیص است.")
    if project.deleted_at is not None:
        raise ValueError("امکان تخصیص نیرو به پروژه بایگانی‌شده وجود ندارد.")
    if site is not None and not site.is_active:
        raise ValueError("امکان تخصیص نیرو به کارگاه غیرفعال وجود ندارد.")
    assignment = EmployeeProjectAssignment(
        organization=organization,
        employee=employee,
        project=project,
        site=site,
        role_title=role_title.strip(),
        start_date=start_date,
        planned_end_date=planned_end_date,
        notes=notes.strip(),
        created_by=actor,
        updated_by=actor,
    )
    _save_validated(assignment, "اطلاعات تخصیص پروژه معتبر نیست یا تکراری است.")
    record_audit_event(
        action=AuditAction.EMPLOYEE_PROJECT_ASSIGNED,
        entity_type="employee_project_assignment",
        entity_id=assignment.pk,
        organization=organization,
        actor=actor,
        metadata={
            "employee_number": employee.employee_number,
            "project_code": project.code,
        },
    )
    return assignment


def get_organization_project_assignments(
    *,
    user: User,
    organization: Organization,
    project: Project | None = None,
) -> QuerySet[EmployeeProjectAssignment]:
    _require_active_access(
        organization=organization,
        user=user,
        permission=BusinessPermissionCode.PROJECT_ASSIGNMENTS_VIEW,
    )
    assignments = EmployeeProjectAssignment.objects.filter(organization=organization)
    if project is not None:
        if project.organization_id != organization.pk:
            raise PermissionDenied("پروژه متعلق به این سازمان نیست.")
        assignments = assignments.filter(project=project)
    return assignments.select_related("employee", "project", "site")


@transaction.atomic
def transition_project_assignment_status(
    *,
    organization: Organization,
    actor: User,
    assignment: EmployeeProjectAssignment,
    target_status: str,
    end_date: date,
) -> EmployeeProjectAssignment:
    _require_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.PROJECT_ASSIGNMENTS_CHANGE_STATUS,
    )
    locked = EmployeeProjectAssignment.objects.select_for_update().get(pk=assignment.pk)
    if locked.organization_id != organization.pk:
        raise PermissionDenied("تخصیص نیرو متعلق به این سازمان نیست.")
    if target_status not in _ASSIGNMENT_STATUS_TRANSITIONS.get(locked.status, ()):
        raise ValueError("این تغییر وضعیت تخصیص نیرو مجاز نیست.")
    previous_status = locked.status
    locked.status = target_status
    locked.end_date = end_date
    locked.updated_by = actor
    try:
        locked.save(update_fields=["status", "end_date", "updated_by", "updated_at"])
    except ValidationError as exc:
        raise ValueError("تاریخ پایان تخصیص معتبر نیست.") from exc
    record_audit_event(
        action=AuditAction.EMPLOYEE_PROJECT_ASSIGNMENT_STATUS_CHANGED,
        entity_type="employee_project_assignment",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"previous_status": previous_status, "new_status": target_status},
    )
    return locked


@transaction.atomic
def archive_employee(
    *, organization: Organization, actor: User, employee: Employee
) -> Employee:
    _require_management_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.EMPLOYEES_ARCHIVE,
    )
    locked = Employee.objects.select_for_update().get(pk=employee.pk)
    if locked.organization_id != organization.pk:
        raise PermissionDenied("کارمند متعلق به این سازمان نیست.")
    if locked.archived_at is not None:
        raise ValueError("کارمند از قبل بایگانی شده است.")
    if locked.project_assignments.filter(status=AssignmentStatus.ACTIVE).exists():
        raise ValueError("کارمند دارای تخصیص فعال پروژه قابل بایگانی نیست.")
    if locked.teams_led.filter(archived_at__isnull=True).exists():
        raise ValueError("سرپرست گروه کاری فعال قابل بایگانی نیست.")
    locked.archived_at = timezone.now()
    if locked.status == EmployeeStatus.ACTIVE:
        locked.status = EmployeeStatus.INACTIVE
    locked.updated_by = actor
    locked.save(update_fields=["archived_at", "status", "updated_by", "updated_at"])
    record_audit_event(
        action=AuditAction.EMPLOYEE_ARCHIVED,
        entity_type="employee",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"employee_number": locked.employee_number},
    )
    return locked


def _archive_master(
    *,
    organization: Organization,
    actor: User,
    record: Department | Position | WorkTeam,
    action: str,
    entity_type: str,
    permission: BusinessPermissionCode,
) -> Department | Position | WorkTeam:
    _require_management_access(
        organization=organization,
        actor=actor,
        permission=permission,
    )
    locked = record.__class__.objects.select_for_update().get(pk=record.pk)
    if locked.organization_id != organization.pk:
        raise PermissionDenied("رکورد نیروی انسانی متعلق به این سازمان نیست.")
    if locked.archived_at is not None:
        raise ValueError("رکورد نیروی انسانی از قبل بایگانی شده است.")
    if isinstance(locked, Department) and (
        locked.children.filter(archived_at__isnull=True).exists()
        or locked.positions.filter(archived_at__isnull=True).exists()
        or locked.work_teams.filter(archived_at__isnull=True).exists()
        or locked.employees.filter(archived_at__isnull=True).exists()
    ):
        raise ValueError(
            "واحد سازمانی دارای رکورد فعال نیروی انسانی قابل بایگانی نیست."
        )
    if isinstance(locked, Position) and (
        locked.child_positions.filter(archived_at__isnull=True, is_active=True).exists()
        or locked.employees.filter(archived_at__isnull=True).exists()
        or locked.employee_assignments.filter(
            status=PositionAssignmentStatus.ACTIVE
        ).exists()
    ):
        raise ValueError(
            "سمت شغلی دارای زیرسمت فعال یا تخصیص کارکنان فعال قابل بایگانی نیست."
        )
    if (
        isinstance(locked, WorkTeam)
        and locked.members.filter(archived_at__isnull=True).exists()
    ):
        raise ValueError("گروه کاری دارای اعضای فعال قابل بایگانی نیست.")
    locked.archived_at = timezone.now()
    locked.is_active = False
    locked.updated_by = actor
    locked.save(update_fields=["archived_at", "is_active", "updated_by", "updated_at"])
    record_audit_event(
        action=action,
        entity_type=entity_type,
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"code": locked.code},
    )
    return locked


@transaction.atomic
def archive_department(
    *, organization: Organization, actor: User, department: Department
) -> Department:
    return _archive_master(
        organization=organization,
        actor=actor,
        record=department,
        action=AuditAction.DEPARTMENT_ARCHIVED,
        entity_type="department",
        permission=BusinessPermissionCode.DEPARTMENTS_ARCHIVE,
    )


@transaction.atomic
def archive_position(
    *, organization: Organization, actor: User, position: Position
) -> Position:
    return _archive_master(
        organization=organization,
        actor=actor,
        record=position,
        action=AuditAction.POSITION_ARCHIVED,
        entity_type="position",
        permission=BusinessPermissionCode.POSITIONS_ARCHIVE,
    )


@transaction.atomic
def archive_work_team(
    *, organization: Organization, actor: User, work_team: WorkTeam
) -> WorkTeam:
    return _archive_master(
        organization=organization,
        actor=actor,
        record=work_team,
        action=AuditAction.WORK_TEAM_ARCHIVED,
        entity_type="work_team",
        permission=BusinessPermissionCode.WORK_TEAMS_ARCHIVE,
    )


def _require_workforce_permission(
    *, organization: Organization, actor: User, permission: BusinessPermissionCode, project: Project | None = None
) -> None:
    _require_active_access(organization=organization, user=actor, permission=permission)
    if project is not None:
        require_business_permission(
            user=actor,
            organization=organization,
            permission=permission,
            project=project,
            message="اجازه انجام عملیات نیروی انسانی در این پروژه را ندارید.",
        )


def _record_workforce_audit(
    *, action: AuditAction, entity_type: str, entity_id: object, organization: Organization, actor: User, metadata: Mapping[str, object]
) -> None:
    record_audit_event(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        organization=organization,
        actor=actor,
        metadata=dict(metadata),
    )


@transaction.atomic
def create_skill(*, organization: Organization, actor: User, code: str, name: str, description: str = "") -> Skill:
    _require_workforce_permission(organization=organization, actor=actor, permission=BusinessPermissionCode.WORKFORCE_SKILLS_MANAGE)
    skill = Skill(organization=organization, code=code, name=name, description=description.strip(), created_by=actor)
    _save_validated(skill, "مهارت معتبر نیست یا کد آن تکراری است.")
    _record_workforce_audit(action=AuditAction.WORKFORCE_SKILL_RECORDED, entity_type="workforce_skill", entity_id=skill.pk, organization=organization, actor=actor, metadata={"code": skill.code})
    return skill


@transaction.atomic
def create_competency(*, organization: Organization, actor: User, code: str, name: str, description: str = "") -> Competency:
    _require_workforce_permission(organization=organization, actor=actor, permission=BusinessPermissionCode.WORKFORCE_SKILLS_MANAGE)
    competency = Competency(organization=organization, code=code, name=name, description=description.strip(), created_by=actor)
    _save_validated(competency, "شایستگی معتبر نیست یا کد آن تکراری است.")
    _record_workforce_audit(action=AuditAction.WORKFORCE_COMPETENCY_RECORDED, entity_type="workforce_competency", entity_id=competency.pk, organization=organization, actor=actor, metadata={"code": competency.code})
    return competency


def _require_effective_interval_available(*, queryset: QuerySet, effective_from: date, effective_to: date | None, message: str) -> None:
    interval_end = effective_to or date.max
    if queryset.select_for_update().filter(effective_from__lte=interval_end).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=effective_from)).exists():
        raise ValueError(message)


@transaction.atomic
def record_employee_skill(
    *, organization: Organization, actor: User, employee: Employee, skill: Skill, competency: Competency | None,
    proficiency_level: int, effective_from: date, effective_to: date | None = None, notes: str = "",
) -> EmployeeSkillRecord:
    _require_workforce_permission(organization=organization, actor=actor, permission=BusinessPermissionCode.WORKFORCE_SKILLS_MANAGE)
    _require_same_organization(organization, employee=employee)
    if skill.organization_id != organization.pk or (competency and competency.organization_id != organization.pk):
        raise PermissionDenied("مهارت یا شایستگی متعلق به این سازمان نیست.")
    _require_effective_interval_available(
        queryset=EmployeeSkillRecord.objects.filter(organization=organization, employee=employee, skill=skill),
        effective_from=effective_from, effective_to=effective_to,
        message="برای این مهارت، سابقه مؤثر هم‌پوشان وجود دارد.",
    )
    record = EmployeeSkillRecord(organization=organization, employee=employee, skill=skill, competency=competency, proficiency_level=proficiency_level, effective_from=effective_from, effective_to=effective_to, notes=notes.strip(), recorded_by=actor)
    _save_validated(record, "سابقه مهارت کارمند معتبر نیست.")
    _record_workforce_audit(action=AuditAction.EMPLOYEE_SKILL_RECORDED, entity_type="employee_skill_record", entity_id=record.pk, organization=organization, actor=actor, metadata={"employee_id": str(employee.pk), "skill_id": str(skill.pk), "effective_from": effective_from.isoformat()})
    return record


@transaction.atomic
def record_employee_qualification(
    *, organization: Organization, actor: User, employee: Employee, kind: str, title: str, issuer: str = "", reference_number: str = "", issued_on: date | None = None, valid_until: date | None = None,
) -> EmployeeQualification:
    _require_workforce_permission(organization=organization, actor=actor, permission=BusinessPermissionCode.WORKFORCE_QUALIFICATIONS_MANAGE)
    _require_same_organization(organization, employee=employee)
    if kind not in QualificationKind.values:
        raise ValueError("نوع صلاحیت معتبر نیست.")
    qualification = EmployeeQualification(organization=organization, employee=employee, kind=kind, title=title, issuer=issuer, reference_number=reference_number, issued_on=issued_on, valid_until=valid_until, recorded_by=actor)
    _save_validated(qualification, "صلاحیت کارمند معتبر نیست.")
    _record_workforce_audit(action=AuditAction.EMPLOYEE_QUALIFICATION_RECORDED, entity_type="employee_qualification", entity_id=qualification.pk, organization=organization, actor=actor, metadata={"employee_id": str(employee.pk), "kind": kind, "valid_until": valid_until.isoformat() if valid_until else None})
    return qualification


@transaction.atomic
def revoke_employee_qualification(*, organization: Organization, actor: User, qualification: EmployeeQualification, occurred_on: date, reason: str) -> EmployeeQualificationLifecycleEvent:
    _require_workforce_permission(organization=organization, actor=actor, permission=BusinessPermissionCode.WORKFORCE_QUALIFICATIONS_REVOKE)
    _require_same_organization(organization, employee=qualification.employee)
    locked = EmployeeQualification.objects.select_for_update().get(pk=qualification.pk, organization=organization)
    if locked.lifecycle_events.filter(kind__in=[QualificationLifecycleEventKind.REVOKED, QualificationLifecycleEventKind.SUPERSEDED]).exists():
        raise ValueError("صلاحیت قبلاً ابطال یا جایگزین شده است.")
    event = EmployeeQualificationLifecycleEvent(organization=organization, qualification=locked, kind=QualificationLifecycleEventKind.REVOKED, occurred_on=occurred_on, reason=reason, recorded_by=actor)
    _save_validated(event, "رویداد ابطال صلاحیت معتبر نیست.")
    _record_workforce_audit(action=AuditAction.EMPLOYEE_QUALIFICATION_REVOKED, entity_type="employee_qualification", entity_id=locked.pk, organization=organization, actor=actor, metadata={"event_id": str(event.pk), "occurred_on": occurred_on.isoformat()})
    return event


@transaction.atomic
def create_training_requirement(
    *, organization: Organization, actor: User, code: str, name: str, competency: Competency | None = None, position: Position | None = None, project: Project | None = None, description: str = "",
) -> TrainingRequirement:
    _require_workforce_permission(organization=organization, actor=actor, permission=BusinessPermissionCode.WORKFORCE_QUALIFICATIONS_MANAGE, project=project)
    if (competency and competency.organization_id != organization.pk) or (position and position.organization_id != organization.pk) or (project and project.organization_id != organization.pk):
        raise PermissionDenied("دامنه الزام آموزشی متعلق به این سازمان نیست.")
    requirement = TrainingRequirement(organization=organization, code=code, name=name, description=description.strip(), competency=competency, position=position, project=project, created_by=actor)
    _save_validated(requirement, "الزام آموزشی معتبر نیست یا کد آن تکراری است.")
    _record_workforce_audit(action=AuditAction.TRAINING_REQUIREMENT_RECORDED, entity_type="training_requirement", entity_id=requirement.pk, organization=organization, actor=actor, metadata={"code": requirement.code, "project_id": str(project.pk) if project else None})
    return requirement


@transaction.atomic
def record_employee_training(*, organization: Organization, actor: User, employee: Employee, requirement: TrainingRequirement, occurred_on: date, outcome: str, notes: str = "") -> EmployeeTrainingRecord:
    _require_workforce_permission(organization=organization, actor=actor, permission=BusinessPermissionCode.WORKFORCE_QUALIFICATIONS_MANAGE, project=requirement.project)
    _require_same_organization(organization, employee=employee)
    if requirement.organization_id != organization.pk:
        raise PermissionDenied("الزام آموزشی متعلق به این سازمان نیست.")
    if outcome not in TrainingOutcome.values:
        raise ValueError("نتیجه آموزش معتبر نیست.")
    record = EmployeeTrainingRecord(organization=organization, employee=employee, requirement=requirement, occurred_on=occurred_on, outcome=outcome, notes=notes.strip(), recorded_by=actor)
    _save_validated(record, "سابقه آموزش کارمند معتبر نیست.")
    _record_workforce_audit(action=AuditAction.EMPLOYEE_TRAINING_RECORDED, entity_type="employee_training_record", entity_id=record.pk, organization=organization, actor=actor, metadata={"employee_id": str(employee.pk), "requirement_id": str(requirement.pk), "outcome": outcome})
    return record


@transaction.atomic
def record_performance_evaluation(*, organization: Organization, actor: User, employee: Employee, period_start: date, period_end: date, criteria_snapshot: Mapping[str, object], result_summary: str) -> PerformanceEvaluation:
    _require_workforce_permission(organization=organization, actor=actor, permission=BusinessPermissionCode.WORKFORCE_PERFORMANCE_MANAGE)
    _require_same_organization(organization, employee=employee)
    evaluation = PerformanceEvaluation(organization=organization, employee=employee, period_start=period_start, period_end=period_end, criteria_snapshot=dict(criteria_snapshot), result_summary=result_summary, evaluated_by=actor, recorded_by=actor)
    _save_validated(evaluation, "ارزیابی عملکرد معتبر نیست.")
    _record_workforce_audit(action=AuditAction.PERFORMANCE_EVALUATION_RECORDED, entity_type="performance_evaluation", entity_id=evaluation.pk, organization=organization, actor=actor, metadata={"employee_id": str(employee.pk), "period_start": period_start.isoformat(), "period_end": period_end.isoformat()})
    return evaluation


@transaction.atomic
def record_labor_rate_version(*, organization: Organization, actor: User, employee: Employee, component_name: str, unit_label: str, currency_code: str, rate_amount, effective_from: date, effective_to: date | None = None, notes: str = "") -> LaborRateVersion:
    _require_workforce_permission(organization=organization, actor=actor, permission=BusinessPermissionCode.WORKFORCE_LABOR_RATES_MANAGE)
    _require_same_organization(organization, employee=employee)
    _require_effective_interval_available(queryset=LaborRateVersion.objects.filter(organization=organization, employee=employee, component_name=component_name.strip()), effective_from=effective_from, effective_to=effective_to, message="برای این جزء هزینه، نسخه نرخ مؤثر هم‌پوشان وجود دارد.")
    version = LaborRateVersion(organization=organization, employee=employee, component_name=component_name, unit_label=unit_label, currency_code=currency_code, rate_amount=rate_amount, effective_from=effective_from, effective_to=effective_to, notes=notes.strip(), recorded_by=actor)
    _save_validated(version, "نسخه نرخ نیروی کار معتبر نیست.")
    _record_workforce_audit(action=AuditAction.LABOR_RATE_VERSION_RECORDED, entity_type="labor_rate_version", entity_id=version.pk, organization=organization, actor=actor, metadata={"employee_id": str(employee.pk), "component_name": version.component_name, "effective_from": effective_from.isoformat()})
    return version


def get_workforce_skills(*, organization: Organization, actor: User) -> QuerySet[Skill]:
    _require_workforce_permission(organization=organization, actor=actor, permission=BusinessPermissionCode.WORKFORCE_SKILLS_VIEW)
    return Skill.objects.filter(organization=organization, archived_at__isnull=True).order_by("name")


def get_workforce_competencies(*, organization: Organization, actor: User) -> QuerySet[Competency]:
    _require_workforce_permission(organization=organization, actor=actor, permission=BusinessPermissionCode.WORKFORCE_SKILLS_VIEW)
    return Competency.objects.filter(organization=organization, archived_at__isnull=True).order_by("name")


def get_employee_qualifications(*, organization: Organization, actor: User, employee: Employee) -> QuerySet[EmployeeQualification]:
    _require_workforce_permission(organization=organization, actor=actor, permission=BusinessPermissionCode.WORKFORCE_QUALIFICATIONS_VIEW)
    _require_same_organization(organization, employee=employee)
    return EmployeeQualification.objects.filter(organization=organization, employee=employee).prefetch_related("lifecycle_events", "typed_document_links")


def get_employee_training_records(*, organization: Organization, actor: User, employee: Employee) -> QuerySet[EmployeeTrainingRecord]:
    _require_workforce_permission(organization=organization, actor=actor, permission=BusinessPermissionCode.WORKFORCE_QUALIFICATIONS_VIEW)
    _require_same_organization(organization, employee=employee)
    return EmployeeTrainingRecord.objects.filter(organization=organization, employee=employee).select_related("requirement").prefetch_related("typed_document_links")


def get_performance_evaluations(*, organization: Organization, actor: User, employee: Employee) -> QuerySet[PerformanceEvaluation]:
    _require_workforce_permission(organization=organization, actor=actor, permission=BusinessPermissionCode.WORKFORCE_PERFORMANCE_VIEW)
    _require_same_organization(organization, employee=employee)
    return PerformanceEvaluation.objects.filter(organization=organization, employee=employee).prefetch_related("typed_document_links")


def get_labor_rate_versions(*, organization: Organization, actor: User, employee: Employee) -> QuerySet[LaborRateVersion]:
    _require_workforce_permission(organization=organization, actor=actor, permission=BusinessPermissionCode.WORKFORCE_LABOR_RATES_VIEW)
    _require_same_organization(organization, employee=employee)
    return LaborRateVersion.objects.filter(organization=organization, employee=employee)


@transaction.atomic
def link_workforce_evidence(
    *, organization: Organization, actor: User, document: Document,
    target: EmployeeQualification | EmployeeTrainingRecord | PerformanceEvaluation,
) -> object:
    """Append a typed DMS evidence link after both domain and document checks."""

    if isinstance(target, PerformanceEvaluation):
        permission = BusinessPermissionCode.WORKFORCE_PERFORMANCE_MANAGE
        target_type = "performance_evaluation"
        action = AuditAction.PERFORMANCE_EVALUATION_EVIDENCE_LINKED
        entity_type = "performance_evaluation"
    elif isinstance(target, EmployeeTrainingRecord):
        permission = BusinessPermissionCode.WORKFORCE_QUALIFICATIONS_MANAGE
        target_type = "employee_training"
        action = AuditAction.EMPLOYEE_TRAINING_EVIDENCE_LINKED
        entity_type = "employee_training_record"
    elif isinstance(target, EmployeeQualification):
        permission = BusinessPermissionCode.WORKFORCE_QUALIFICATIONS_MANAGE
        target_type = "employee_qualification"
        action = AuditAction.EMPLOYEE_QUALIFICATION_EVIDENCE_LINKED
        entity_type = "employee_qualification"
    else:
        raise TypeError("نوع شاهد نیروی انسانی پشتیبانی نمی‌شود.")
    _require_workforce_permission(organization=organization, actor=actor, permission=permission)
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.DOCUMENTS_VIEW,
        message="اجازه استفاده از سند موجود را ندارید.",
    )
    # The DMS service repeats complete-context authorization for every retained
    # existing link before a Workforce record may reference the document.
    from apps.documents.services import get_organization_document

    document = get_organization_document(
        user=actor, organization=organization, document_id=str(document.pk)
    )
    if document.organization_id != organization.pk or target.organization_id != organization.pk:
        raise PermissionDenied("سند یا رکورد نیروی انسانی متعلق به این سازمان نیست.")
    link = create_typed_link(
        organization=organization,
        document=document,
        created_by=actor,
        target_type=target_type,
        target=target,
    )
    _record_workforce_audit(action=action, entity_type=entity_type, entity_id=target.pk, organization=organization, actor=actor, metadata={"document_id": str(document.pk), "link_id": str(link.pk)})
    return link
