"""Fail-closed employee access to source-linked DMS documents."""

from dataclasses import dataclass
from zoneinfo import ZoneInfo

from django.core.exceptions import PermissionDenied
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.documents.link_registry import DOCUMENT_LINK_TYPES, typed_links_for_document
from apps.documents.models import (
    Document,
    DocumentRetentionClassification,
    DocumentVersion,
)
from apps.documents.services import _validate_access, _validate_target_access
from apps.organizations.models import BusinessPermissionCode, Organization
from apps.workforce.ess_services import resolve_ess_subject
from apps.workforce.models import Person, WorkRelationship

_DENIED = "سند در این سازمان یافت نشد."
_EMPLOYEE_LINKS = frozenset({"work_relationship", "qualification", "training_record"})


@dataclass(frozen=True)
class EmployeeDocumentAccess:
    document: Document
    versions: tuple[DocumentVersion, ...]
    can_download: bool
    source_links: tuple[tuple[str, str], ...]


def _subject(*, user: User, organization: Organization) -> tuple[Person, set]:
    _validate_access(
        user=user,
        organization=organization,
        permission=BusinessPermissionCode.DOCUMENTS_VIEW,
    )
    try:
        subject = resolve_ess_subject(user=user, organization=organization)
    except PermissionDenied as exc:
        raise PermissionDenied(_DENIED) from exc
    return subject.person, {subject.current_relationship.pk}


def _linked_episode(*, link: object, organization: Organization) -> WorkRelationship:
    if link.target_type == "work_relationship":
        return link.work_relationship
    employee_id = link.target.employee_id
    matches = list(
        WorkRelationship.objects.filter(
            organization=organization,
            legacy_employee_id=employee_id,
        ).select_related("person")[:2]
    )
    if len(matches) != 1:
        raise PermissionDenied(_DENIED)
    return matches[0]


def _authorize(
    *,
    document: Document,
    user: User,
    organization: Organization,
    person: Person,
    current_ids: set,
) -> EmployeeDocumentAccess:
    if (
        document.organization_id != organization.pk
        or document.archived_at is not None
        or document.current_version_id is None
        or document.retention_classification
        == DocumentRetentionClassification.SEALED_SUPPLIER_QUOTE_EVIDENCE
        or (document.access_expires_at and document.access_expires_at <= timezone.now())
    ):
        raise PermissionDenied(_DENIED)
    category = document.category
    if (
        category is None
        or category.organization_id != organization.pk
        or category.archived_at
    ):
        raise PermissionDenied(_DENIED)
    links = typed_links_for_document(document)
    if not links:
        raise PermissionDenied(_DENIED)
    legacy_ids = set(document.links.values_list("pk", flat=True))
    typed_legacy_ids = {
        link.pk
        for link in links
        if next(
            item
            for item in DOCUMENT_LINK_TYPES
            if item.target_field == link.target_type
        ).legacy_compatible
    }
    if legacy_ids != typed_legacy_ids:
        raise PermissionDenied(_DENIED)
    has_employee_source = False
    source_links = []
    today = timezone.localdate(timezone=ZoneInfo(organization.settings.timezone))
    for link in links:
        source_links.append((link.target_type, str(link.target.pk)))
        if link.target_type in _EMPLOYEE_LINKS:
            has_employee_source = True
            if link.target.organization_id != organization.pk:
                raise PermissionDenied(_DENIED)
            episode = _linked_episode(link=link, organization=organization)
            if (
                episode.organization_id != organization.pk
                or episode.person_id != person.pk
            ):
                raise PermissionDenied(_DENIED)
            if episode.effective_start > today or (
                episode.pk not in current_ids and not category.employee_history_visible
            ):
                raise PermissionDenied(_DENIED)
            if link.target_type in {"qualification", "training_record"}:
                _validate_target_access(
                    actor=user, organization=organization, target=link.target
                )
        else:
            _validate_target_access(
                actor=user, organization=organization, target=link.target
            )
    if not has_employee_source:
        raise PermissionDenied(_DENIED)
    versions = tuple(
        version
        for version in document.versions.order_by("version_number")
        if (
            (
                version.pk == document.current_version_id
                and category.employee_current_visible
            )
            or (
                version.pk != document.current_version_id
                and category.employee_history_visible
            )
        )
    )
    if not versions:
        raise PermissionDenied(_DENIED)
    return EmployeeDocumentAccess(
        document=document,
        versions=versions,
        can_download=category.employee_download_allowed,
        source_links=tuple(source_links),
    )


def get_employee_documents(
    *, user: User, organization: Organization
) -> list[EmployeeDocumentAccess]:
    """List only documents that pass the same backend rule as direct access."""
    person, current_ids = _subject(user=user, organization=organization)
    from apps.workforce.models import (
        EmployeeQualificationDocumentLink,
        EmployeeTrainingDocumentLink,
        WorkRelationshipDocumentLink,
    )

    candidate_ids = set(
        WorkRelationshipDocumentLink.objects.filter(
            organization=organization, work_relationship__person=person
        ).values_list("document_id", flat=True)
    )
    mapped_employee_ids = WorkRelationship.objects.filter(
        organization=organization, person=person, legacy_employee__isnull=False
    ).values_list("legacy_employee_id", flat=True)
    candidate_ids.update(
        EmployeeQualificationDocumentLink.objects.filter(
            organization=organization,
            qualification__employee_id__in=mapped_employee_ids,
        ).values_list("document_id", flat=True)
    )
    candidate_ids.update(
        EmployeeTrainingDocumentLink.objects.filter(
            organization=organization,
            training_record__employee_id__in=mapped_employee_ids,
        ).values_list("document_id", flat=True)
    )
    result = []
    for document in (
        Document.objects.filter(organization=organization, pk__in=candidate_ids)
        .select_related("category", "current_version", "organization")
        .prefetch_related("versions")
    ):
        try:
            result.append(
                _authorize(
                    document=document,
                    user=user,
                    organization=organization,
                    person=person,
                    current_ids=current_ids,
                )
            )
        except PermissionDenied:
            continue
    return result


def get_employee_document(
    *,
    user: User,
    organization: Organization,
    document_id: str,
) -> EmployeeDocumentAccess:
    person, current_ids = _subject(user=user, organization=organization)
    document = (
        Document.objects.filter(organization=organization, pk=document_id)
        .select_related("category", "current_version", "organization")
        .first()
    )
    if document is None:
        raise PermissionDenied(_DENIED)
    try:
        return _authorize(
            document=document,
            user=user,
            organization=organization,
            person=person,
            current_ids=current_ids,
        )
    except PermissionDenied as exc:
        raise PermissionDenied(_DENIED) from exc


def get_employee_version_for_download(
    *,
    user: User,
    organization: Organization,
    document_id: str,
    version_id: str,
) -> DocumentVersion:
    access = get_employee_document(
        user=user, organization=organization, document_id=document_id
    )
    _validate_access(
        user=user,
        organization=organization,
        permission=BusinessPermissionCode.DOCUMENTS_DOWNLOAD,
    )
    if not access.can_download:
        raise PermissionDenied(_DENIED)
    version = next(
        (item for item in access.versions if str(item.pk) == str(version_id)), None
    )
    if (
        version is None
        or version.organization_id != organization.pk
        or not version.is_available
    ):
        raise PermissionDenied(_DENIED)
    return version


def record_employee_download(
    *,
    user: User,
    organization: Organization,
    document_id: str,
    version_id: str,
) -> DocumentVersion:
    version = get_employee_version_for_download(
        user=user,
        organization=organization,
        document_id=document_id,
        version_id=version_id,
    )
    record_audit_event(
        action=AuditAction.DOCUMENT_DOWNLOADED,
        entity_type="document",
        entity_id=version.document_id,
        organization=organization,
        actor=user,
        metadata={
            "version_id": str(version.pk),
            "version_number": version.version_number,
        },
    )
    return version
