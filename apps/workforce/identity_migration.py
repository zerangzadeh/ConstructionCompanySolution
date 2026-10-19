"""CEP-029: source-evidenced Employee conversion, preserving existing authority.

Each legacy row supplies only its recorded episode. Rehire across separate
legacy rows may share an explicitly selected existing Person. Ambiguous prior
episodes, inactive rows without dated end evidence and conflicts are reported;
names, emails, employee numbers and User similarity never select a Person.
"""

import hashlib
import json
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import BusinessPermissionCode as P
from apps.organizations.models import Organization

from .identity_migration_models import EmployeeIdentityMigration
from .models import (
    Employee,
    EmployeePositionAssignment,
    EmployeeProjectAssignment,
    EmployeeStatus,
    Person,
    WorkRelationship,
    WorkRelationshipRevision,
)
from .person_services import create_person, create_work_relationship

PROCESS_VERSION = 1


def fingerprint(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()


def _require(organization: Organization, actor: User) -> Organization:
    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    for permission in (P.EMPLOYEES_VIEW, P.EMPLOYEES_CREATE):
        require_business_permission(
            user=actor,
            organization=organization,
            permission=permission,
            message="Explicit tenant Workforce migration authority is required.",
        )
    return organization


def _source_state(organization):
    sources = {
        model._meta.label: list(
            model.objects.filter(organization=organization).order_by("pk").values()
        )
        for model in (Employee, EmployeePositionAssignment, EmployeeProjectAssignment)
    }
    sources["audit.employee_status"] = list(
        AuditEvent.objects.filter(
            organization=organization, action=AuditAction.EMPLOYEE_STATUS_CHANGED
        )
        .order_by("pk")
        .values()
    )
    return sources


def _counts(organization):
    return {
        model.__name__: model.objects.filter(organization=organization).count()
        for model in (Employee, Person, WorkRelationship, WorkRelationshipRevision)
    }


def _episode_exception(employee, organization):
    if employee.hire_date is None:
        return "MISSING_EFFECTIVE_HIRE_DATE"
    if employee.status != EmployeeStatus.ACTIVE and employee.termination_date is None:
        return "NONACTIVE_EPISODE_HAS_NO_DATED_END_EVIDENCE"
    if employee.archived_at and employee.termination_date is None:
        return "ARCHIVED_EPISODE_HAS_NO_DATED_END_EVIDENCE"
    if employee.termination_date and employee.termination_date < employee.hire_date:
        return "INVALID_SOURCE_EPISODE_DATES"
    transitions = AuditEvent.objects.filter(
        organization=organization,
        action=AuditAction.EMPLOYEE_STATUS_CHANGED,
        entity_id=str(employee.pk),
    )
    if any(
        event.metadata.get("previous_status") == EmployeeStatus.TERMINATED
        and event.metadata.get("new_status") == EmployeeStatus.ACTIVE
        for event in transitions
    ):
        return "REHIRE_HISTORY_REQUIRES_SEPARATE_DATED_SOURCE_EPISODES"
    return None


def _target_fingerprint(relationship):
    return fingerprint(
        {
            "relationship": WorkRelationship.objects.filter(pk=relationship.pk)
            .values()
            .get(),
            "person": Person.objects.filter(pk=relationship.person_id).values().get(),
            "revisions": list(relationship.revisions.order_by("version").values()),
        }
    )


def _map_employee(organization, actor, employee, explicit_person_id):
    error = _episode_exception(employee, organization)
    if error:
        return {"employee_id": str(employee.pk), "status": "EXCEPTION", "code": error}
    relationships = list(
        WorkRelationship.objects.filter(
            organization=organization, legacy_employee=employee
        )
        .select_related("person")
        .order_by("effective_start")
    )
    people = {row.person_id for row in relationships}
    if explicit_person_id:
        try:
            person = Person.objects.select_for_update().get(
                pk=explicit_person_id, organization=organization
            )
        except (Person.DoesNotExist, ValidationError, ValueError) as exc:
            raise PermissionDenied(
                "Explicit target Person is outside the active tenant."
            ) from exc
        if people and people != {person.pk}:
            return {
                "employee_id": str(employee.pk),
                "status": "EXCEPTION",
                "code": "EXISTING_PERSON_MAPPING_CONFLICT",
            }
    elif len(people) == 1:
        person = relationships[0].person
    elif people:
        return {
            "employee_id": str(employee.pk),
            "status": "EXCEPTION",
            "code": "AMBIGUOUS_EXISTING_PERSON",
        }
    else:
        # A direct User link is evidence that an existing Person needs explicit
        # reconciliation, not permission to guess/merge/link identity.
        if (
            employee.user_id
            and Person.objects.filter(
                organization=organization, user_id=employee.user_id
            ).exists()
        ):
            return {
                "employee_id": str(employee.pk),
                "status": "EXCEPTION",
                "code": "EXISTING_PERSON_REQUIRES_EXPLICIT_MAPPING",
            }
        person = create_person(
            organization=organization,
            actor=actor,
            first_name=employee.first_name,
            last_name=employee.last_name,
        )
    matches = [
        row
        for row in relationships
        if row.effective_start == employee.hire_date
        and row.effective_end == employee.termination_date
        and row.employee_number == employee.employee_number
    ]
    if len(matches) > 1:
        raise ValidationError("Ambiguous matching authoritative episode.")
    if matches:
        relationship = matches[0]
        if relationship.person_id != person.pk or not relationship.revisions.exists():
            raise ValidationError(
                "Existing target has no compatible identity/revision evidence."
            )
        disposition = "EXISTING"
    else:
        if relationships:
            # Do not append a contradictory current episode to a legacy identity
            # whose existing migrated history requires a separate reconciliation.
            raise ValidationError(
                "Existing target episodes differ from the recorded source episode."
            )
        relationship = create_work_relationship(
            organization=organization,
            actor=actor,
            person=person,
            employee_number=employee.employee_number,
            effective_start=employee.hire_date,
            effective_end=employee.termination_date,
            legacy_employee=employee,
        )
        disposition = "CREATED"
    return {
        "employee_id": str(employee.pk),
        "person_id": str(person.pk),
        "relationship_id": str(relationship.pk),
        "status": disposition,
        "effective_start": relationship.effective_start.isoformat(),
        "effective_end": relationship.effective_end.isoformat()
        if relationship.effective_end
        else None,
        "source_reference": f"workforce.Employee:{employee.pk}:hire_date/termination_date",
        "source_fingerprint": fingerprint(
            Employee.objects.filter(pk=employee.pk).values().get()
        ),
        "revision_ids": [
            str(pk)
            for pk in relationship.revisions.order_by("version").values_list(
                "pk", flat=True
            )
        ],
        "legacy_user_id_preserved": str(employee.user_id) if employee.user_id else None,
        "target_user_link_created": False,
        "target_fingerprint": _target_fingerprint(relationship),
    }


def _verify_retry(organization, result):
    for row in result["mapping"]:
        if row["status"] == "EXCEPTION":
            continue
        target = WorkRelationship.objects.filter(
            pk=row["relationship_id"],
            organization=organization,
            person_id=row["person_id"],
            legacy_employee_id=row["employee_id"],
            effective_start=row["effective_start"],
            effective_end=row["effective_end"],
        ).first()
        if target is None:
            raise ValidationError(
                "Migration retry target drift requires explicit reconciliation."
            )
        if _target_fingerprint(target) != row["target_fingerprint"]:
            raise ValidationError(
                "Migration retry target facts changed; preserve and reconcile."
            )
        if set(map(str, target.revisions.values_list("pk", flat=True))) != set(
            row["revision_ids"]
        ):
            raise ValidationError(
                "Migration retry target history changed; preserve it and reconcile."
            )


@transaction.atomic
def migrate_employee_identities(
    *,
    organization: Organization,
    actor: User,
    source_key: str,
    reason: str,
    explicit_person_mapping: dict[str, str] | None = None,
    rehearsal: bool = False,
) -> dict[str, Any]:
    organization = _require(organization, actor)
    if not source_key.strip() or not reason.strip():
        raise ValidationError(
            "A stable migration source key and audit reason are required."
        )
    explicit = {str(k): str(v) for k, v in (explicit_person_mapping or {}).items()}
    employees = list(
        Employee.objects.select_for_update()
        .filter(organization=organization)
        .order_by("hire_date", "pk")
    )
    if set(explicit) - {str(employee.pk) for employee in employees}:
        raise PermissionDenied(
            "Explicit source mapping includes an out-of-tenant Employee."
        )
    # Validate every explicit target before any target mutation, including rows
    # whose source episode would otherwise be an exception.
    for person_id in explicit.values():
        try:
            valid_person = Person.objects.filter(
                pk=person_id, organization=organization
            ).exists()
        except (ValidationError, ValueError) as exc:
            raise PermissionDenied("Invalid explicit Person identity.") from exc
        if not valid_person:
            raise PermissionDenied(
                "Explicit target mapping includes an out-of-tenant Person."
            )
    source_before = _source_state(organization)
    source_hash = fingerprint(source_before)
    input_hash = fingerprint({"process_version": PROCESS_VERSION, "mapping": explicit})
    previous = EmployeeIdentityMigration.objects.filter(
        organization=organization, source_key=source_key
    ).first()
    if previous:
        if (
            previous.source_fingerprint != source_hash
            or previous.input_fingerprint != input_hash
        ):
            raise ValidationError(
                "Migration key source/input changed; use explicit new reconciliation."
            )
        _verify_retry(organization, previous.result)
        return previous.result | {
            "run_id": str(previous.pk),
            "repeated": True,
            "rehearsal": rehearsal,
        }
    before = _counts(organization)
    existing_targets = {
        model._meta.label: list(
            model.objects.filter(organization=organization).order_by("pk").values()
        )
        for model in (Person, WorkRelationship, WorkRelationshipRevision)
    }
    mapping = []
    for employee in employees:
        try:
            with transaction.atomic():
                row = _map_employee(
                    organization, actor, employee, explicit.get(str(employee.pk))
                )
        except ValidationError:
            # Failed source target creation is rolled back before the exception
            # is appended. No orphan Person/episode may escape the savepoint.
            row = {
                "employee_id": str(employee.pk),
                "status": "EXCEPTION",
                "code": "SOURCE_TARGET_IDENTITY_OR_EPISODE_CONFLICT",
            }
        mapping.append(row)
    if fingerprint(_source_state(organization)) != source_hash:
        raise ValidationError(
            "Legacy Employee or assignment sources changed during migration."
        )
    for label, values in existing_targets.items():
        model = {
            m._meta.label: m
            for m in (Person, WorkRelationship, WorkRelationshipRevision)
        }[label]
        if values != list(
            model.objects.filter(pk__in=[v["id"] for v in values])
            .order_by("pk")
            .values()
        ):
            raise ValidationError(
                "Existing authoritative identity/history was rewritten."
            )
    exceptions = [row for row in mapping if row["status"] == "EXCEPTION"]
    result = {
        "process_version": PROCESS_VERSION,
        "organization_id": str(organization.pk),
        "source_fingerprint": source_hash,
        "before": before,
        "after": _counts(organization),
        "mapping": mapping,
        "exceptions": exceptions,
        "source_count": len(employees),
        "mapped_count": len(mapping) - len(exceptions),
        "exception_count": len(exceptions),
        "source_and_assignments_preserved": True,
        "existing_targets_preserved": True,
        "authority_cutover": False,
    }
    if result["source_count"] != result["mapped_count"] + result["exception_count"]:
        raise ValidationError(
            "Migration source/target/exception counts do not reconcile."
        )
    run = EmployeeIdentityMigration.objects.create(
        organization=organization,
        actor=actor,
        source_key=source_key,
        process_version=PROCESS_VERSION,
        source_fingerprint=source_hash,
        input_fingerprint=input_hash,
        result=result,
        reason=reason,
    )
    if rehearsal:
        transaction.set_rollback(True)
    return result | {"run_id": str(run.pk), "repeated": False, "rehearsal": rehearsal}
