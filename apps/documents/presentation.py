"""Read-only projections of existing DMS links for five business Detail pages.

The DMS and source-domain read services remain the authorization authorities.
Return context is an allowlisted source identity, never a client-supplied URL.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urlencode
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse

from apps.documents.link_registry import registered_link_type
from apps.documents.services import (
    _validate_target_access,
    get_document_version_for_download,
    get_organization_document,
    get_organization_documents,
)
from apps.organizations.authorization import has_business_permission
from apps.organizations.models import BusinessPermissionCode
from core.jalali import format_jalali
from core.product_surface import route_exposed

if TYPE_CHECKING:
    from django.db.models import Model, QuerySet
    from django.http import HttpRequest

    from apps.accounts.models import User
    from apps.documents.models import Document
    from apps.organizations.models import Organization


# These are existing source routes and relationships, not a new link registry.
SOURCE_ROUTES = {
    "project": ("projects:detail", "project_id", "پروژه"),
    "contract": ("contracts:detail", "contract_id", "قرارداد"),
    "estimate": ("estimates:detail", "estimate_id", "برآورد"),
    "expense": ("expenses:detail", "expense_id", "هزینه"),
    "daily_report": ("daily_reports:detail", "report_id", "گزارش روزانه"),
}


@dataclass(frozen=True)
class DocumentSource:
    kind: str
    identifier: UUID
    label: str
    title: str
    url: str

    @property
    def query(self) -> str:
        return urlencode({"related_to": self.kind, "related_id": self.identifier})


@dataclass(frozen=True)
class RelatedDocumentRow:
    title: str
    type_label: str
    version_number: int
    available: bool
    detail_url: str
    download_url: str


@dataclass(frozen=True)
class RelatedDocuments:
    rows: tuple[RelatedDocumentRow, ...]
    upload_url: str = ""
    link_url: str = ""

    @property
    def count(self) -> int:
        return len(self.rows)

    @property
    def first_rows(self) -> tuple[RelatedDocumentRow, ...]:
        return self.rows[:5]

    @property
    def remaining_rows(self) -> tuple[RelatedDocumentRow, ...]:
        return self.rows[5:]


def _sources(*, kind: str, user: "User", organization: "Organization") -> "QuerySet":
    from apps.contracts.services import get_organization_contracts
    from apps.daily_reports.services import get_organization_daily_reports
    from apps.estimates.services import get_organization_estimates
    from apps.expenses.services import get_organization_expenses
    from apps.projects.services import get_organization_projects

    return {
        "project": get_organization_projects,
        "contract": get_organization_contracts,
        "estimate": get_organization_estimates,
        "expense": get_organization_expenses,
        "daily_report": get_organization_daily_reports,
    }[kind](user=user, organization=organization)


def _source(
    *, kind: str, target: "Model", user: "User", organization: "Organization"
) -> DocumentSource:
    route, parameter, label = SOURCE_ROUTES[kind]
    url = reverse(route, kwargs={parameter: target.pk})
    if kind == "estimate":
        # Project-aware Estimate URLs require their own Project read authority.
        try:
            project_visible = (
                _sources(kind="project", user=user, organization=organization)
                .filter(pk=target.project_id)
                .exists()
            )
        except PermissionDenied:
            project_visible = False
        if project_visible:
            url += "?" + urlencode({"project_id": target.project_id})
    if kind == "project":
        title = target.name
    elif kind == "expense":
        title = target.description
    elif kind == "daily_report":
        title = f"{target.site.name} · {format_jalali(target.reporting_date)}"
    else:
        title = target.title
    return DocumentSource(kind, target.pk, label, title, url + "#related-documents")


def related_documents_for(
    *, user: "User", organization: "Organization", target: "Model"
) -> RelatedDocuments | None:
    """Project direct typed links through the existing exact DMS read boundary.

    Compatibility mirrors never add rows. A denied document contributes neither
    metadata nor a count. None means the section itself is not authorized.
    """
    kind = next(
        (
            key
            for key in SOURCE_ROUTES
            if isinstance(
                target,
                registered_link_type(key).model._meta.get_field(key).remote_field.model,
            )
        ),
        None,
    )
    if (
        kind is None
        or organization is None
        or getattr(target, "organization_id", None) != organization.pk
        or not route_exposed("documents:detail")
        or not route_exposed(SOURCE_ROUTES[kind][0])
    ):
        return None
    try:
        authorized_target = (
            _sources(kind=kind, user=user, organization=organization)
            .filter(pk=target.pk)
            .first()
        )
        if authorized_target is None:
            return None
        source = _source(
            kind=kind, target=authorized_target, user=user, organization=organization
        )
        links = registered_link_type(kind).model.objects.filter(
            organization=organization, **{kind: authorized_target}
        )
        candidates = get_organization_documents(
            user=user, organization=organization
        ).filter(pk__in=links.values("document_id"))
        identifiers = list(candidates.values_list("pk", flat=True))
    except PermissionDenied:
        return None

    rows = []
    for identifier in identifiers:
        try:
            # The list service alone does not check compatibility parity or all
            # deleted-source conditions. Use the very same read as DMS Detail.
            document = get_organization_document(
                user=user, organization=organization, document_id=str(identifier)
            )
        except PermissionDenied:
            continue
        version = document.current_version
        available = version.is_available
        download_url = ""
        if available and route_exposed("documents:version-download"):
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
        rows.append(
            RelatedDocumentRow(
                title=document.title,
                type_label=document.get_document_type_display(),
                version_number=version.version_number,
                available=available,
                detail_url=reverse("documents:detail", args=[document.pk])
                + "?"
                + source.query,
                download_url=download_url,
            )
        )
    can_associate = has_business_permission(
        user=user,
        organization=organization,
        permission=BusinessPermissionCode.DOCUMENTS_UPLOAD,
        allow_any_scope=True,
    )
    if can_associate:
        try:
            _validate_target_access(
                actor=user, organization=organization, target=authorized_target
            )
        except PermissionDenied:
            can_associate = False
    return RelatedDocuments(
        tuple(rows),
        upload_url=reverse("documents:contextual-upload", args=[kind, target.pk])
        if can_associate and route_exposed("documents:contextual-upload")
        else "",
        link_url=reverse("documents:contextual-link", args=[kind, target.pk])
        if can_associate and route_exposed("documents:contextual-link")
        else "",
    )


def document_sources_for(
    *, user: "User", organization: "Organization", document: "Document"
) -> tuple[DocumentSource, ...]:
    """Return only authorized, exposed, actually persisted supported sources."""
    sources = []
    for kind, (route, _, _) in SOURCE_ROUTES.items():
        if not route_exposed(route):
            continue
        link_type = registered_link_type(kind)
        identifiers = link_type.model.objects.filter(
            organization=organization, document=document
        ).values_list(f"{kind}_id", flat=True)
        try:
            targets = _sources(kind=kind, user=user, organization=organization).filter(
                pk__in=identifiers
            )
            sources.extend(
                _source(kind=kind, target=target, user=user, organization=organization)
                for target in targets
            )
        except PermissionDenied:
            continue
    return tuple(sources)


def document_return_source(
    request: "HttpRequest", sources: tuple[DocumentSource, ...]
) -> DocumentSource | None:
    """Ignore forged/unrelated return context; never follow an arbitrary URL."""
    try:
        identifier = UUID(request.GET.get("related_id", ""))
    except (ValueError, TypeError, ValidationError):
        return None
    return next(
        (
            source
            for source in sources
            if source.kind == request.GET.get("related_to")
            and source.identifier == identifier
        ),
        None,
    )
