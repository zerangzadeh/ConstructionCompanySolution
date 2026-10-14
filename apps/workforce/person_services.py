"""Bounded Person and employment-episode foundation for CEP-010."""

from datetime import date

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q

from apps.accounts.models import User
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import BusinessPermissionCode, Organization
from apps.workforce.models import (
    Employee,
    Person,
    WorkRelationship,
    WorkRelationshipRevision,
)
from core.identifiers import canonicalize_upper_identifier


def _require_access(
    *, organization: Organization, actor: User, permission: BusinessPermissionCode
) -> None:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        message="Workforce permission is required.",
    )


def _reject_overlap(
    *,
    organization: Organization,
    person: Person,
    employee_number: str,
    effective_start: date,
    effective_end: date | None,
    exclude_id: object = None,
) -> None:
    overlap = (
        WorkRelationship.objects.filter(organization=organization)
        .filter(Q(person=person) | Q(employee_number=employee_number))
        .filter(Q(effective_end__isnull=True) | Q(effective_end__gte=effective_start))
    )
    if effective_end is not None:
        overlap = overlap.filter(effective_start__lte=effective_end)
    if exclude_id is not None:
        overlap = overlap.exclude(pk=exclude_id)
    if overlap.exists():
        raise ValidationError(
            "Employment episodes cannot overlap for the same person or number."
        )


@transaction.atomic
def create_person(
    *,
    organization: Organization,
    actor: User,
    first_name: str,
    last_name: str,
    user: User | None = None,
) -> Person:
    _require_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.EMPLOYEES_CREATE,
    )
    person = Person(
        organization=organization, first_name=first_name, last_name=last_name, user=user
    )
    person.save()
    return person


@transaction.atomic
def create_work_relationship(
    *,
    organization: Organization,
    actor: User,
    person: Person,
    employee_number: str,
    effective_start: date,
    effective_end: date | None = None,
    legacy_employee: Employee | None = None,
) -> WorkRelationship:
    _require_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.EMPLOYEES_CREATE,
    )
    if person.organization_id != organization.pk or (
        legacy_employee is not None
        and legacy_employee.organization_id != organization.pk
    ):
        raise PermissionDenied(
            "Related Workforce identity belongs to another organization."
        )
    # Serialize employee-number allocation across people in this tenant.
    Organization.objects.select_for_update().get(pk=organization.pk)
    Person.objects.select_for_update().get(pk=person.pk, organization=organization)
    number = canonicalize_upper_identifier(employee_number)
    _reject_overlap(
        organization=organization,
        person=person,
        employee_number=number,
        effective_start=effective_start,
        effective_end=effective_end,
    )
    relationship = WorkRelationship(
        organization=organization,
        person=person,
        employee_number=number,
        effective_start=effective_start,
        effective_end=effective_end,
        legacy_employee=legacy_employee,
    )
    relationship.save()
    WorkRelationshipRevision.objects.create(
        organization=organization,
        relationship=relationship,
        version=1,
        effective_start=effective_start,
        effective_end=effective_end,
        recorded_by=actor,
    )
    return relationship


@transaction.atomic
def end_work_relationship(
    *,
    organization: Organization,
    actor: User,
    relationship: WorkRelationship,
    effective_end: date,
) -> WorkRelationship:
    _require_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.EMPLOYEES_CHANGE_STATUS,
    )
    if relationship.organization_id != organization.pk:
        raise PermissionDenied("WorkRelationship belongs to another organization.")
    locked = WorkRelationship.objects.select_for_update().get(
        pk=relationship.pk, organization=organization
    )
    if locked.effective_end is not None or effective_end < locked.effective_start:
        raise ValidationError(
            "Relationship is already ended or the end date is invalid."
        )
    WorkRelationship.objects.filter(pk=locked.pk).update(effective_end=effective_end)
    locked.effective_end = effective_end
    WorkRelationshipRevision.objects.create(
        organization=organization,
        relationship=locked,
        version=2,
        effective_start=locked.effective_start,
        effective_end=effective_end,
        recorded_by=actor,
    )
    return locked


def resolve_legacy_employee(
    *,
    organization: Organization,
    actor: User,
    employee: Employee,
) -> tuple[Employee, WorkRelationship | None]:
    """Keep the Employee source addressable without fabricating target rows."""

    _require_access(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.EMPLOYEES_VIEW,
    )
    if employee.organization_id != organization.pk:
        raise PermissionDenied("Employee belongs to another organization.")
    matches = list(
        WorkRelationship.objects.filter(
            organization=organization, legacy_employee=employee
        )[:2]
    )
    if len(matches) > 1:
        raise ValidationError(
            "Legacy Employee maps to multiple episodes; resolve explicitly."
        )
    return employee, matches[0] if matches else None
