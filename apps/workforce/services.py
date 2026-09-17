from collections.abc import Mapping
from datetime import date

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
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
    Department,
    Employee,
    EmployeePositionAssignment,
    EmployeeProjectAssignment,
    EmployeeStatus,
    Position,
    PositionAssignmentStatus,
    WorkTeam,
)

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
