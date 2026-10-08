"""Reusable photo capability backed exclusively by the governed DMS."""

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q

from apps.accounts.models import User
from apps.daily_reports.models import DailyReportDocumentLink
from apps.documents.models import Document, DocumentType, PhotoMetadata, PhotoSource
from apps.documents.services import (
    add_document_link,
    create_document,
    get_organization_documents,
)
from apps.organizations.models import Organization
from apps.projects.models import (
    Project,
    ProjectDocumentLink,
    ProjectSite,
    ProjectSiteDocumentLink,
)

if TYPE_CHECKING:
    from django.core.files.uploadedfile import UploadedFile
    from django.db.models import Model, QuerySet


@dataclass(frozen=True, slots=True)
class ProjectPhoto:
    document: Document
    site: ProjectSite | None
    source: str
    captured_at: datetime | None


def _validate_photo_context(
    *,
    organization: Organization,
    project: Project,
    site: ProjectSite | None,
    target: "Model",
) -> None:
    if project.organization_id != organization.pk or project.deleted_at is not None:
        raise PermissionDenied("پروژه فعال متعلق به این سازمان نیست.")
    if site is not None and (
        site.organization_id != organization.pk or site.project_id != project.pk
    ):
        raise PermissionDenied("کارگاه باید متعلق به همین پروژه و سازمان باشد.")
    if getattr(target, "organization_id", None) != organization.pk:
        raise PermissionDenied("موجودیت هدف تصویر متعلق به این سازمان نیست.")
    target_project = (
        target if isinstance(target, Project) else getattr(target, "project", None)
    )
    if target_project is not None and target_project.pk != project.pk:
        raise PermissionDenied("موجودیت هدف باید متعلق به همین پروژه باشد.")
    target_site = (
        target if isinstance(target, ProjectSite) else getattr(target, "site", None)
    )
    if site is not None and target_site is not None and target_site.pk != site.pk:
        raise PermissionDenied("موجودیت هدف باید متعلق به همین کارگاه باشد.")


@transaction.atomic
def create_photo(
    *,
    organization: Organization,
    actor: User,
    project: Project,
    upload: "UploadedFile",
    source: str,
    title: str = "",
    description: str = "",
    site: ProjectSite | None = None,
    target: "Model | None" = None,
    captured_at: datetime | None = None,
) -> Document:
    """Create one canonical PHOTO document and attach governed business context."""

    if source not in PhotoSource.values:
        raise ValueError("منبع تصویر معتبر نیست.")
    target = target or project
    _validate_photo_context(
        organization=organization,
        project=project,
        site=site,
        target=target,
    )
    resolved_title = title.strip() or Path(upload.name).stem.strip() or "تصویر پروژه"
    document = create_document(
        organization=organization,
        actor=actor,
        document_type=DocumentType.PHOTO,
        title=resolved_title,
        description=description,
        upload=upload,
        target=target,
        audit_metadata={
            "photo_source": source,
            "project_id": str(project.pk),
            "site_id": str(site.pk) if site else None,
        },
    )
    if target != project:
        add_document_link(document=document, actor=actor, target=project)
    if site is not None and target != site:
        add_document_link(document=document, actor=actor, target=site)
    PhotoMetadata.objects.create(
        organization=organization,
        document=document,
        source=source,
        captured_at=captured_at,
    )
    return document


def get_project_photos(
    *,
    organization: Organization,
    project: Project,
    actor: User,
    site: ProjectSite | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[ProjectPhoto]:
    """Return authorized project photos, including compatible Daily Report links."""

    direct_ids = ProjectDocumentLink.objects.filter(
        organization=organization,
        project=project,
    ).values("document_id")
    daily_ids = DailyReportDocumentLink.objects.filter(
        organization=organization,
        daily_report__project=project,
    ).values("document_id")
    documents: QuerySet[Document] = (
        get_organization_documents(
            user=actor,
            organization=organization,
        )
        .filter(
            document_type=DocumentType.PHOTO,
        )
        .filter(Q(pk__in=direct_ids) | Q(pk__in=daily_ids))
    )
    if date_from is not None:
        documents = documents.filter(created_at__date__gte=date_from)
    if date_to is not None:
        documents = documents.filter(created_at__date__lte=date_to)

    document_list = list(documents.select_related("created_by"))
    document_ids = [document.pk for document in document_list]
    explicit_sites = {
        link.document_id: link.project_site
        for link in ProjectSiteDocumentLink.objects.filter(
            organization=organization,
            document_id__in=document_ids,
        ).select_related("project_site")
    }
    report_sites = {
        link.document_id: link.daily_report.site
        for link in DailyReportDocumentLink.objects.filter(
            organization=organization,
            document_id__in=document_ids,
            daily_report__project=project,
        ).select_related("daily_report__site")
    }
    metadata = {
        item.document_id: item
        for item in PhotoMetadata.objects.filter(
            organization=organization,
            document_id__in=document_ids,
        )
    }
    photos = [
        ProjectPhoto(
            document=document,
            site=explicit_sites.get(document.pk) or report_sites.get(document.pk),
            source=(metadata[document.pk].source if document.pk in metadata else ""),
            captured_at=(
                metadata[document.pk].captured_at if document.pk in metadata else None
            ),
        )
        for document in document_list
    ]
    if site is not None:
        photos = [photo for photo in photos if photo.site and photo.site.pk == site.pk]
    return photos
