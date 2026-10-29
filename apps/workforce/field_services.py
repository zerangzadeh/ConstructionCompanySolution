"""Small operational use cases over existing Workforce authorities."""

from datetime import date

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import BusinessPermissionCode, Organization
from apps.projects.models import Project, ProjectSite

from .field_selectors import FieldContext, employee_person, field_employees
from .identity_integrity import identity_write_lock
from .models import Employee, EmployeeProjectAssignment, Person, WorkTeam
from .person_services import create_person, create_work_relationship
from .services import create_employee


@identity_write_lock()
@transaction.atomic
def save_field_employee(
    *,
    organization: Organization,
    actor: User,
    first_name: str,
    last_name: str,
    national_id: str | None = None,
    employee_number: str = "",
    start_date: date | None = None,
    work_team: WorkTeam | None = None,
    phone_number: str = "",
    employee: Employee | None = None,
) -> Employee:
    # Tenant serialization also protects explicit legacy-link establishment.
    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    permission = (
        BusinessPermissionCode.EMPLOYEES_CHANGE_OPERATIONAL
        if employee
        else BusinessPermissionCode.EMPLOYEES_CREATE
    )
    require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        message="اجازه ثبت یا ویرایش نیروی کار را ندارید.",
    )
    if work_team and (
        work_team.organization_id != organization.pk
        or not WorkTeam.objects.filter(
            pk=work_team.pk, organization=organization, is_active=True, archived_at=None
        ).exists()
    ):
        raise PermissionDenied("گروه کاری انتخاب‌شده در دسترس نیست.")
    is_new = employee is None
    if is_new:
        if not start_date:
            raise ValidationError("تاریخ آغاز همکاری را وارد کنید.")
        employee = create_employee(
            organization=organization,
            actor=actor,
            employee_number=employee_number,
            first_name=first_name,
            last_name=last_name,
            hire_date=start_date,
            work_team=work_team,
            phone_number=phone_number,
        )
    else:
        if employee.organization_id != organization.pk:
            raise PermissionDenied("نیروی کار در دسترس نیست.")
        employee = Employee.objects.select_for_update().get(
            pk=employee.pk, organization=organization, archived_at=None
        )
        if employee.status == "terminated":
            raise ValidationError("اطلاعات همکاری خاتمه‌یافته قابل ویرایش نیست.")
    person = employee_person(employee)
    if person is None and (is_new or national_id):
        if not start_date:
            raise ValidationError("برای ثبت هویت، تاریخ آغاز همکاری را وارد کنید.")
        if employee.hire_date and start_date != employee.hire_date:
            raise ValidationError("تاریخ آغاز همکاری باید با سابقه ثبت‌شده سازگار باشد.")
        if (
            employee.user_id
            and Person.objects.filter(
                organization=organization, user_id=employee.user_id
            ).exists()
        ):
            raise ValidationError(
                "این حساب هویت ثبت‌شده دارد؛ اتصال باید توسط مسئول مجاز بررسی شود."
            )
        # No User link is inferred from a legacy Employee link.
        person = create_person(
            organization=organization,
            actor=actor,
            first_name=first_name,
            last_name=last_name,
        )
        create_work_relationship(
            organization=organization,
            actor=actor,
            person=person,
            employee_number=employee.employee_number,
            effective_start=start_date,
            legacy_employee=employee,
        )
    if person is not None:
        person = Person.objects.select_for_update().get(
            pk=person.pk, organization=organization
        )
        person.first_name = first_name
        person.last_name = last_name
        person.national_id = national_id
        person.save()
    if not is_new:
        employee.first_name = first_name
        employee.last_name = last_name
        employee.work_team = work_team
        employee.phone_number = phone_number
        employee.updated_by = actor
        employee.save(
            update_fields=[
                "first_name",
                "last_name",
                "work_team",
                "phone_number",
                "updated_by",
                "updated_at",
            ]
        )
    record_audit_event(
        action=AuditAction.EMPLOYEE_OPERATIONAL_UPDATED,
        entity_type="employee",
        entity_id=employee.pk,
        organization=organization,
        actor=actor,
        # National IDs and personal data never enter evidence or logs.
        metadata={"person_id": str(person.pk) if person else None, "created": is_new},
    )
    return employee


@transaction.atomic
def assign_field_employee(
    *,
    organization: Organization,
    actor: User,
    employee: Employee,
    project: Project,
    site: ProjectSite | None,
    start_date: date,
    role_title: str = "",
    notes: str = "",
    planned_end_date: date | None = None,
) -> EmployeeProjectAssignment:
    from .services import assign_employee_to_project

    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.PROJECT_ASSIGNMENTS_CREATE,
        project=project,
        site=site,
        message="اجازه تخصیص نیرو به این پروژه یا کارگاه را ندارید.",
    )
    if (
        not field_employees(
            organization=organization, user=actor, context=FieldContext()
        )
        .filter(pk=employee.pk)
        .exists()
    ):
        raise PermissionDenied("نیروی کار در دسترس نیست.")
    employee = Employee.objects.select_for_update().get(
        pk=employee.pk, organization=organization
    )
    return assign_employee_to_project(
        organization=organization,
        actor=actor,
        employee=employee,
        project=project,
        site=site,
        start_date=start_date,
        role_title=role_title,
        notes=notes,
        planned_end_date=planned_end_date,
    )
