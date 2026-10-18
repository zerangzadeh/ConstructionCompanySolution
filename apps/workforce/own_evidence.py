"""Read-only own Workforce/DMS composition; no inferred Worker/Party identity."""

from dataclasses import dataclass
from zoneinfo import ZoneInfo

from django.core.exceptions import PermissionDenied
from django.utils import timezone

from apps.accounts.models import User
from apps.documents.employee_access import get_employee_documents
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import BusinessPermissionCode as P
from apps.organizations.models import Organization

from .ess_services import resolve_ess_subject
from .models import (
    EmployeeProjectAssignment,
    EmployeeQualification,
    EmployeeTrainingRecord,
    WorkRelationship,
)


@dataclass(frozen=True)
class OwnEvidence:
    subject: object
    documents: tuple
    qualifications: tuple
    training: tuple
    assignments: tuple
    document_state: str
    legacy_state: str
    observed_on: object


def build_own_evidence(*, actor: User, organization: Organization) -> OwnEvidence:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=P.ESS_EVIDENCE_VIEW,
        message="اطلاعات مجاز در این شرکت یافت نشد.",
    )
    subject = resolve_ess_subject(user=actor, organization=organization)
    try:
        documents = tuple(get_employee_documents(user=actor, organization=organization))
        document_state = "ready" if documents else "empty"
    except PermissionDenied:
        documents = ()
        document_state = "unavailable"
    employee_ids = tuple(
        WorkRelationship.objects.filter(
            organization=organization,
            person=subject.person,
            legacy_employee_id__isnull=False,
        ).values_list("legacy_employee_id", flat=True)
    )
    qualifications = training = assignments = ()
    legacy_state = "unavailable"
    if employee_ids:
        qualifications = tuple(
            EmployeeQualification.objects.filter(
                organization=organization, employee_id__in=employee_ids
            ).order_by("-issued_on", "title")
        )
        training = tuple(
            EmployeeTrainingRecord.objects.filter(
                organization=organization, employee_id__in=employee_ids
            )
            .select_related("requirement")
            .order_by("-occurred_on")
        )
        assignments = tuple(
            EmployeeProjectAssignment.objects.filter(
                organization=organization, employee_id__in=employee_ids
            )
            .select_related("project", "site")
            .order_by("-start_date")
        )
        legacy_state = "ready" if qualifications or training or assignments else "empty"
    return OwnEvidence(
        subject,
        documents,
        qualifications,
        training,
        assignments,
        document_state,
        legacy_state,
        timezone.localdate(timezone=ZoneInfo(organization.settings.timezone)),
    )
