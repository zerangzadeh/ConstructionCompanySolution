"""Presentation adapters for persisted, domain-owned exact-version witnesses.

These adapters grant no domain authority. Domain services still own registration
and lifecycle; ordinary DMS services own metadata access and secure delivery.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import islice
from typing import TYPE_CHECKING
from uuid import UUID

from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.urls import reverse

from apps.documents.models import DocumentVersion
from apps.documents.services import (
    get_document_version_for_download,
    get_organization_document,
    get_organization_documents,
)
from apps.organizations.authorization import (
    has_business_permission,
    require_business_permission,
)
from apps.organizations.models import BusinessPermissionCode as P
from core.forms import normalize_jalali_digits
from core.product_surface import route_exposed

if TYPE_CHECKING:
    from django.db.models import Model, QuerySet

    from apps.accounts.models import User
    from apps.organizations.models import Organization

DENIED = "شاهد یا سابقه مرتبط در دسترس نیست یا اجازه انجام این عملیات را ندارید."
PAGE_SIZE = 20
# Explicit UI routes only; this is not a new relationship registry.
SOURCE_ROUTES = {
    "safety": ("safety:detail", "حادثه ایمنی"),
    "quality": ("quality:detail", "مسئله کیفیت"),
    "material": ("materials:material_detail", "مصالح"),
    "field_observation": ("daily_reports:field_observation_detail", "مشاهده میدانی"),
    "contractual": ("contracts:contractual_detail", "رکورد قراردادی"),
    "guarantee": ("billing:guarantee_detail", "ضمانت‌نامه"),
    "compliance": ("billing:compliance_evidence_detail", "شاهد انطباق قرارداد"),
    "release": ("billing:retention_release_detail", "آزادسازی کسور تضمین"),
}
REGISTRATION_PERMISSIONS = {
    "safety": P.SAFETY_INCIDENTS_RECORD_SUBMIT,
    "quality": P.QUALITY_ISSUES_RECORD_SUBMIT,
    "field_observation": P.FIELD_OBSERVATIONS_CAPTURE,
    "contractual": P.CONTRACTUAL_RECORDS_PREPARE,
    "material": P.MATERIAL_DOCUMENTS_LINK,
}
COMMERCIAL_PERMISSIONS = {
    "guarantee": P.GUARANTEES_MANAGE,
    "compliance": P.COMPLIANCE_EVIDENCE_MANAGE,
    "release": P.RETENTION_RELEASES_CREATE,
}


@dataclass(frozen=True)
class EvidenceSource:
    kind: str
    target: Model
    label: str
    title: str
    url: str


@dataclass(frozen=True)
class PinnedEvidenceRow:
    version_id: UUID
    title: str
    number: str
    type_label: str
    version: int
    current_version: int
    status: str
    available: bool
    view_url: str
    download_url: str


@dataclass(frozen=True)
class EvidencePanel:
    source: EvidenceSource
    rows: tuple[PinnedEvidenceRow, ...]
    register_url: str = ""
    register_label: str = ""
    context_links: tuple[tuple[str, str, str], ...] = ()


def _record(
    *, user: User, organization: Organization, kind: str, identifier: UUID
) -> Model:
    if kind == "safety":
        from apps.safety.services import get_organization_safety_incident

        return get_organization_safety_incident(
            user=user, organization=organization, incident_id=str(identifier)
        )
    if kind == "quality":
        from apps.quality.services import get_organization_quality_issue

        return get_organization_quality_issue(
            user=user, organization=organization, issue_id=str(identifier)
        )
    if kind == "material":
        from apps.materials.services import get_organization_materials

        records = get_organization_materials(user=user, organization=organization)
    elif kind == "field_observation":
        from apps.daily_reports.field_services import get_field_observation

        return get_field_observation(
            actor=user, organization=organization, observation_id=str(identifier)
        )
    elif kind == "contractual":
        from apps.contracts.contractual_services import get_contractual_records

        records = get_contractual_records(actor=user, organization=organization)
    else:
        from apps.billing.commercial_services import (
            get_compliance_evidence,
            get_guarantees,
            get_retention_releases,
        )

        records = {
            "guarantee": get_guarantees,
            "compliance": get_compliance_evidence,
            "release": get_retention_releases,
        }[kind](actor=user, organization=organization)
    target = records.filter(pk=identifier).first()
    if target is None:
        raise PermissionDenied(DENIED)
    return target


def resolve_evidence_source(
    *, user: User, organization: Organization, kind: str, identifier: UUID | str
) -> EvidenceSource:
    if kind not in SOURCE_ROUTES or not route_exposed(SOURCE_ROUTES[kind][0]):
        raise PermissionDenied(DENIED)
    require_business_permission(
        user=user,
        organization=organization,
        permission=P.DOCUMENTS_VIEW,
        allow_any_scope=True,
        message=DENIED,
    )
    try:
        identifier = UUID(str(identifier))
    except (ValueError, TypeError, AttributeError) as exc:
        raise PermissionDenied(DENIED) from exc
    target = _record(
        user=user, organization=organization, kind=kind, identifier=identifier
    )
    title = (
        getattr(target, "incident_number", "")
        or getattr(target, "issue_number", "")
        or getattr(target, "title", "")
        or getattr(target, "name", "")
        or getattr(target, "instrument_reference", "")
        or getattr(target, "reference", "")
        or getattr(target, "release_number", "")
    )
    return EvidenceSource(
        kind,
        target,
        SOURCE_ROUTES[kind][1],
        str(title),
        reverse(SOURCE_ROUTES[kind][0], args=[target.pk]) + "#document-evidence",
    )


def can_register(
    *, user: User, organization: Organization, source: EvidenceSource
) -> bool:
    permission = REGISTRATION_PERMISSIONS.get(source.kind)
    if permission is None:
        return False
    target = source.target
    if source.kind == "material":
        return all(
            has_business_permission(
                user=user, organization=organization, permission=code
            )
            for code in (P.MATERIAL_DOCUMENTS_LINK, P.DOCUMENTS_UPLOAD)
        )
    state = (
        target.review_status if source.kind in {"safety", "quality"} else target.status
    )
    return state == "draft" and has_business_permission(
        user=user,
        organization=organization,
        permission=permission,
        project=target.project,
        site=getattr(target, "site", None),
    )


def references(source: EvidenceSource) -> list[tuple[UUID, str]]:
    """Return persisted exact identities; callers must authorize each witness."""
    target = source.target
    organization = target.organization
    if source.kind in {"safety", "quality"}:
        result = []
        for revision in target.review_revisions.filter(
            organization=organization
        ).order_by("sequence"):
            label = f"بازبینی {revision.sequence} · {revision.get_state_display()}"
            result.extend(
                (version_id, label)
                for version_id in revision.evidence.filter(
                    organization=organization
                ).values_list("document_version_id", flat=True)
            )
        return result
    if source.kind == "material":
        return [
            (identifier, "نسخه ثبت‌شده مصالح")
            for identifier in target.document_links.filter(
                organization=organization
            ).values_list("document_version_id", flat=True)
        ]
    if source.kind == "field_observation":
        return [
            (identifier, target.get_status_display())
            for identifier in target.evidence_links.filter(
                organization=organization
            ).values_list("document_version_id", flat=True)
        ]
    if source.kind == "contractual":
        # Non-document sources retain their own presentation and authority.
        return [
            (identifier, f"{label} · {target.get_status_display()}")
            for identifier, label in target.evidence_links.filter(
                organization=organization, document_version__isnull=False
            ).values_list("document_version_id", "label")
        ]
    identifier = (
        target.document_version_id
        if source.kind == "compliance"
        else target.evidence_document_version_id
    )
    return [(identifier, target.get_status_display())] if identifier else []


def pinned_row(
    *,
    user: User,
    organization: Organization,
    source: EvidenceSource,
    version_id: UUID,
    status: str,
) -> PinnedEvidenceRow:
    version = (
        DocumentVersion.objects.select_related("document")
        .filter(pk=version_id, organization=organization)
        .first()
    )
    if version is None:
        raise PermissionDenied(DENIED)
    document = get_organization_document(
        user=user, organization=organization, document_id=str(version.document_id)
    )
    download_url = ""
    if route_exposed("documents:version-download"):
        try:
            get_document_version_for_download(
                document=document, version_id=str(version.pk), actor=user
            )
        except PermissionDenied:
            pass
        else:
            download_url = reverse(
                "documents:version-download", args=[document.pk, version.pk]
            )
    return PinnedEvidenceRow(
        version.pk,
        document.title,
        document.document_number,
        document.get_document_type_display(),
        version.version_number,
        document.current_version.version_number,
        status,
        version.is_available,
        reverse(
            "documents:evidence-detail",
            args=[source.kind, source.target.pk, version.pk],
        ),
        download_url,
    )


def evidence_panel(
    *, user: User, organization: Organization, kind: str, identifier: UUID | str
) -> EvidencePanel | None:
    try:
        source = resolve_evidence_source(
            user=user, organization=organization, kind=kind, identifier=identifier
        )
    except PermissionDenied:
        return None
    rows = []
    for version_id, status in references(source):
        try:
            rows.append(
                pinned_row(
                    user=user,
                    organization=organization,
                    source=source,
                    version_id=version_id,
                    status=status,
                )
            )
        except PermissionDenied:
            continue
    context_links = []
    if kind in COMMERCIAL_PERMISSIONS:
        for name, related_kind, label in (
            ("predecessor", kind, "نسخه پیشین"),
            ("corrects", kind, "آزادسازی مرجع"),
            ("clearance_evidence", "compliance", "مفاصاحساب ثبت‌شده"),
        ):
            related_id = getattr(source.target, name + "_id", None)
            if related_id is None:
                continue
            try:
                related = resolve_evidence_source(
                    user=user,
                    organization=organization,
                    kind=related_kind,
                    identifier=related_id,
                )
            except PermissionDenied:
                continue
            version = getattr(related.target, "version", None) or getattr(
                related.target, "revision_number", ""
            )
            context_links.append(
                (label, f"{related.title} · نسخه {version}", related.url)
            )
    permitted = can_register(user=user, organization=organization, source=source)
    return EvidencePanel(
        source,
        tuple(rows),
        reverse("documents:evidence-register", args=[kind, source.target.pk])
        if permitted
        else "",
        "ارسال رکورد همراه شواهد"
        if kind in {"safety", "quality"}
        else "انتخاب نسخه شاهد",
        tuple(context_links),
    )


def picker_source(
    *,
    user: User,
    organization: Organization,
    kind: str,
    identifier: UUID | str | None = None,
) -> EvidenceSource | None:
    if identifier is not None:
        source = resolve_evidence_source(
            user=user, organization=organization, kind=kind, identifier=identifier
        )
        if kind in COMMERCIAL_PERMISSIONS:
            require_business_permission(
                user=user,
                organization=organization,
                permission=COMMERCIAL_PERMISSIONS[kind],
                project=source.target.project,
                message=DENIED,
            )
            # Existing commercial revision services own the final state/action checks.
            return source
        if not can_register(user=user, organization=organization, source=source):
            raise PermissionDenied(DENIED)
        return source
    if kind not in COMMERCIAL_PERMISSIONS or not route_exposed(SOURCE_ROUTES[kind][0]):
        raise PermissionDenied(DENIED)
    for permission in (P.DOCUMENTS_VIEW, COMMERCIAL_PERMISSIONS[kind]):
        require_business_permission(
            user=user,
            organization=organization,
            permission=permission,
            allow_any_scope=True,
            message=DENIED,
        )
    return None


def eligible_versions(
    *,
    user: User,
    organization: Organization,
    kind: str,
    source: EvidenceSource | None,
    query: str = "",
) -> QuerySet[DocumentVersion]:
    ids = []
    documents = get_organization_documents(user=user, organization=organization)
    query = query.strip()
    if query:
        normalized = normalize_jalali_digits(query).replace("ي", "ی").replace("ك", "ک")
        documents = documents.filter(
            Q(title__icontains=query)
            | Q(title__icontains=normalized)
            | Q(document_number__icontains=normalized)
            | Q(reference__icontains=query)
        )
    for identifier in (
        documents.prefetch_related(None)
        .values_list("pk", flat=True)
        .iterator(chunk_size=200)
    ):
        try:
            document = get_organization_document(
                user=user, organization=organization, document_id=str(identifier)
            )
            if kind == "material":
                from apps.documents.services import _validate_document_context_access

                _validate_document_context_access(
                    document=document, actor=user, permission=P.DOCUMENTS_UPLOAD
                )
        except PermissionDenied:
            continue
        ids.append(identifier)
    versions = (
        DocumentVersion.objects.filter(organization=organization, document_id__in=ids)
        .select_related("document", "document__current_version")
        .prefetch_related("processing_assessments")
    )
    eligible = []
    for version in versions:
        if kind == "material" and (
            source is None
            or version.pk != version.document.current_version_id
            or source.target.document_links.filter(
                organization=organization, document_version=version
            ).exists()
        ):
            continue
        if kind in {"safety", "quality"}:
            if source is None:
                continue
            if kind == "safety":
                from apps.safety.record_review import _valid_evidence_scope
            else:
                from apps.quality.record_review import _valid_evidence_scope
            if not _valid_evidence_scope(version, source.target):
                continue
        elif (
            kind in {*COMMERCIAL_PERMISSIONS, "field_observation"}
            and not version.is_available
        ):
            continue
        eligible.append(version.pk)
    return versions.filter(pk__in=eligible).order_by(
        "document__title", "document_id", "version_number"
    )


def version_label(version: DocumentVersion) -> str:
    state = "آماده دریافت" if version.is_available else "قرنطینه یا ارزیابی‌نشده"
    document = version.document
    reference = document.reference.strip()
    if re.search(
        r"\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b|\b[0-9a-f]{64}\b",
        reference,
        re.IGNORECASE,
    ):
        reference = ""
    business_reference = f" · مرجع {reference}" if reference else ""
    return f"{document.title} · {document.document_number}{business_reference} · {document.get_document_type_display()} · نسخه شاهد {version.version_number} · {state}"


def choice_page(
    versions: QuerySet[DocumentVersion], *, page: int = 1
) -> tuple[list[DocumentVersion], bool]:
    rows = list(
        islice(
            versions.iterator(chunk_size=200),
            (page - 1) * PAGE_SIZE,
            page * PAGE_SIZE + 1,
        )
    )
    return rows[:PAGE_SIZE], len(rows) > PAGE_SIZE
