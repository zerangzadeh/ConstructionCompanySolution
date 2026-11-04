"""Bounded orchestration of existing DMS association services for five sources."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import islice
from typing import TYPE_CHECKING, Any
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q

from apps.documents.link_registry import registered_link_type
from apps.documents.models import Document, DocumentLink
from apps.documents.presentation import SOURCE_ROUTES, DocumentSource, _source, _sources
from apps.documents.services import (
    _validate_access,
    _validate_document_context_access,
    _validate_target_access,
    add_document_link,
    create_document,
    get_organization_document,
    get_organization_documents,
)
from apps.documents.storage import document_storage
from apps.organizations.models import BusinessPermissionCode as P
from core.forms import normalize_jalali_digits
from core.product_surface import route_exposed

if TYPE_CHECKING:
    from django.db.models import Model, QuerySet

    from apps.accounts.models import User
    from apps.organizations.models import Organization

CONTEXT_DENIED = "اجازه انجام این عملیات را ندارید یا سابقه مرتبط در دسترس نیست."
DOCUMENT_DENIED = "سند انتخاب‌شده قابل پیوند نیست یا قبلاً به این سابقه پیوند خورده است."
CHOICE_PAGE_SIZE = 20


@dataclass(frozen=True)
class AssociationContext:
    target: Model
    source: DocumentSource
    number: str
    project_title: str
    project_number: str
    contract_title: str = ""
    contract_number: str = ""


def require_association_access(*, user: User, organization: Organization) -> None:
    for permission in (P.DOCUMENTS_VIEW, P.DOCUMENTS_UPLOAD):
        _validate_access(user=user, organization=organization, permission=permission)


def resolve_association_context(
    *,
    user: User,
    organization: Organization,
    kind: str,
    identifier: UUID | str,
    lock: bool = False,
) -> AssociationContext:
    """Resolve from domain authority; URL identities never grant access."""
    if kind not in SOURCE_ROUTES or not route_exposed(SOURCE_ROUTES[kind][0]):
        raise PermissionDenied(CONTEXT_DENIED)
    try:
        identifier = UUID(str(identifier))
    except (ValueError, TypeError, AttributeError) as exc:
        raise PermissionDenied(CONTEXT_DENIED) from exc
    require_association_access(user=user, organization=organization)
    records = _sources(kind=kind, user=user, organization=organization)
    target = records.filter(pk=identifier).first()
    if target is None:
        raise PermissionDenied(CONTEXT_DENIED)
    if lock:
        # A no-key lock permits ordinary FK key-share checks. Scope selectors
        # may use DISTINCT, which cannot itself be SELECT FOR UPDATE in PG.
        type(target).objects.select_for_update(no_key=True).get(
            pk=target.pk, organization=organization
        )
        target = (
            _sources(kind=kind, user=user, organization=organization)
            .filter(pk=identifier)
            .first()
        )
        if target is None:
            raise PermissionDenied(CONTEXT_DENIED)
    _validate_target_access(actor=user, organization=organization, target=target)
    source = _source(kind=kind, target=target, user=user, organization=organization)
    project = target if kind == "project" else target.project
    contract = target if kind == "contract" else getattr(target, "contract", None)
    if contract is not None:
        try:
            visible_contract = (
                _sources(kind="contract", user=user, organization=organization)
                .filter(pk=contract.pk)
                .exists()
            )
        except PermissionDenied:
            visible_contract = False
        if not visible_contract:
            contract = None
    return AssociationContext(
        target=target,
        source=source,
        number=getattr(target, "contract_number", "")
        or getattr(target, "estimate_number", "")
        or getattr(target, "code", ""),
        project_title=project.name,
        project_number=project.code,
        contract_title=contract.title if contract else "",
        contract_number=contract.contract_number if contract else "",
    )


def association_candidates(
    *,
    user: User,
    organization: Organization,
    context: AssociationContext,
    query: str = "",
) -> QuerySet[Document]:
    """Canonical list candidates, excluding both direct-link representations."""
    kind = context.source.kind
    typed_ids = (
        registered_link_type(kind)
        .model.objects.filter(organization=organization, **{kind: context.target})
        .values("document_id")
    )
    legacy_ids = DocumentLink.objects.filter(
        organization=organization, **{kind: context.target}
    ).values("document_id")
    documents = (
        get_organization_documents(user=user, organization=organization)
        .exclude(pk__in=typed_ids)
        .exclude(pk__in=legacy_ids)
    )
    query = query.strip()
    if query:
        normalized = normalize_jalali_digits(query).replace("ي", "ی").replace("ك", "ک")
        documents = documents.filter(
            Q(title__icontains=query)
            | Q(reference__icontains=query)
            | Q(title__icontains=normalized)
            | Q(document_number__icontains=normalized)
            | Q(reference__icontains=normalized)
        )
    return documents.order_by("title", "pk")


def authorized_association_document(
    *,
    user: User,
    organization: Organization,
    identifier: UUID | str,
) -> Document:
    document = get_organization_document(
        user=user, organization=organization, document_id=str(identifier)
    )
    _validate_document_context_access(
        document=document, actor=user, permission=P.DOCUMENTS_UPLOAD
    )
    return document


def association_choices(
    *,
    user: User,
    organization: Organization,
    context: AssociationContext,
    query: str = "",
    page: int = 1,
) -> tuple[list[Document], bool]:
    def visible():
        identifiers = (
            association_candidates(
                user=user, organization=organization, context=context, query=query
            )
            .prefetch_related(None)
            .values_list("pk", flat=True)
        )
        for identifier in identifiers.iterator(chunk_size=200):
            try:
                yield authorized_association_document(
                    user=user, organization=organization, identifier=identifier
                )
            except PermissionDenied:
                continue

    # Page over authorized results, not raw rows or an unauthorized total.
    rows = list(
        islice(visible(), (page - 1) * CHOICE_PAGE_SIZE, page * CHOICE_PAGE_SIZE + 1)
    )
    return rows[:CHOICE_PAGE_SIZE], len(rows) > CHOICE_PAGE_SIZE


def document_choice_label(document: Document) -> str:
    return (
        f"{document.title} · {document.document_number} · "
        f"{document.get_document_type_display()} · "
        f"نسخه {document.current_version.version_number}"
    )


def upload_in_context(
    *,
    user: User,
    organization: Organization,
    kind: str,
    identifier: UUID | str,
    values: dict[str, Any],
) -> tuple[AssociationContext, Document]:
    stored_names = []
    try:
        with transaction.atomic():
            context = resolve_association_context(
                user=user,
                organization=organization,
                kind=kind,
                identifier=identifier,
                lock=True,
            )
            document = create_document(
                organization=organization,
                actor=user,
                target=context.target,
                stored_names=stored_names,
                **values,
            )
        return context, document
    except Exception:
        # The canonical service tracks only names it generated for this upload.
        for name in stored_names:
            document_storage.delete(name)
        raise


@transaction.atomic
def link_in_context(
    *,
    user: User,
    organization: Organization,
    kind: str,
    identifier: UUID | str,
    document_id: UUID | str,
) -> tuple[AssociationContext, Document]:
    # Match the canonical association service's document serialization boundary.
    locked = (
        Document.objects.select_for_update()
        .filter(pk=document_id, organization=organization)
        .first()
    )
    if locked is None:
        raise PermissionDenied(DOCUMENT_DENIED)
    context = resolve_association_context(
        user=user,
        organization=organization,
        kind=kind,
        identifier=identifier,
        lock=True,
    )
    document = authorized_association_document(
        user=user, organization=organization, identifier=locked.pk
    )
    link_type = registered_link_type(kind)
    if (
        link_type.model.objects.filter(
            organization=organization, document=document, **{kind: context.target}
        ).exists()
        or document.links.filter(**{kind: context.target}).exists()
    ):
        raise ValidationError(DOCUMENT_DENIED)
    add_document_link(document=document, actor=user, target=context.target)
    return context, document
