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
    OrganizationStatus,
)
from apps.projects.models import Project, ProjectSite
from apps.workforce.models import (
    AssignmentStatus,
    Department,
    Employee,
    EmployeeProjectAssignment,
    EmployeeStatus,
    Position,
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


def _require_active_access(*, organization: Organization, user: User) -> None:
    if not user.is_authenticated or not user.is_active:
        raise PermissionDenied("ورود به حساب کاربری الزامی است.")
    if (
        organization.status != OrganizationStatus.ACTIVE
        or organization.deleted_at is not None
    ):
        raise PermissionDenied("سازمان فعال نیست.")
    if (
        not user.is_superuser
        and not organization.memberships.filter(
            user=user,
            status=MembershipStatus.ACTIVE,
            role_definition__is_active=True,
        ).exists()
    ):
        raise PermissionDenied("به این سازمان دسترسی ندارید.")


def _require_management_access(*, organization: Organization, actor: User) -> None:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.WORKFORCE_MANAGE,
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
    _require_management_access(organization=organization, actor=actor)
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
def create_position(
    *,
    organization: Organization,
    actor: User,
    code: str,
    title: str,
    department: Department | None = None,
    description: str = "",
) -> Position:
    _require_management_access(organization=organization, actor=actor)
    _require_same_organization(organization, department=department)
    if department is not None:
        _require_active_master(department, "department")
    position = Position(
        organization=organization,
        department=department,
        code=code,
        title=title,
        description=description.strip(),
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
    _require_management_access(organization=organization, actor=actor)
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
    _require_management_access(organization=organization, actor=actor)
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
    return employee


def get_organization_employees(
    *, user: User, organization: Organization, include_archived: bool = False
) -> QuerySet[Employee]:
    _require_active_access(organization=organization, user=user)
    employees = Employee.objects.filter(organization=organization)
    if not include_archived:
        employees = employees.filter(archived_at__isnull=True)
    return employees.select_related("user", "department", "position", "work_team")


def get_organization_departments(
    *, user: User, organization: Organization
) -> QuerySet[Department]:
    _require_active_access(organization=organization, user=user)
    return Department.objects.filter(
        organization=organization, archived_at__isnull=True
    ).select_related("parent")


def get_organization_positions(
    *, user: User, organization: Organization
) -> QuerySet[Position]:
    _require_active_access(organization=organization, user=user)
    return Position.objects.filter(
        organization=organization, archived_at__isnull=True
    ).select_related("department")


def get_organization_work_teams(
    *, user: User, organization: Organization
) -> QuerySet[WorkTeam]:
    _require_active_access(organization=organization, user=user)
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
    _require_management_access(organization=organization, actor=actor)
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
    _require_management_access(organization=organization, actor=actor)
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
    _require_active_access(organization=organization, user=user)
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
    _require_management_access(organization=organization, actor=actor)
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
    _require_management_access(organization=organization, actor=actor)
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
) -> Department | Position | WorkTeam:
    _require_management_access(organization=organization, actor=actor)
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
    if (
        isinstance(locked, Position)
        and locked.employees.filter(archived_at__isnull=True).exists()
    ):
        raise ValueError("سمت شغلی تخصیص‌یافته به کارکنان فعال قابل بایگانی نیست.")
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
    )
