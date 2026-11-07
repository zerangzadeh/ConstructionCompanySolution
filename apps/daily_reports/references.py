"""Report-owned HSE references and orchestration of existing DMS services."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from itertools import islice
from typing import Any
from uuid import UUID

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q, QuerySet

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.daily_reports.models import DailyReport, DailyReportRecordReference
from apps.daily_reports.services import create_daily_report
from apps.documents.association import (
    authorized_association_document,
    document_choice_label,
)
from apps.documents.services import (
    add_document_link,
    create_document,
    get_organization_documents,
)
from apps.documents.storage import document_storage
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import BusinessPermissionCode, Organization
from apps.projects.models import ProjectPhase, ProjectPhaseStatus, ProjectSite
from apps.quality.services import get_organization_quality_issues
from apps.safety.services import get_organization_safety_incidents
from core.forms import normalize_jalali_digits

DENIED = "رکورد انتخاب‌شده در دسترس نیست یا با محدوده گزارش هم‌خوان نیست."
KINDS = ("safety", "quality", "documents")


def reference_scope(
    *,
    actor: User,
    organization: Organization,
    project_id: object,
    site_id: object,
    phase_id: object = None,
) -> tuple[ProjectSite, ProjectPhase | None] | None:
    """Resolve only a scope in which this actor can create a daily report."""
    if not project_id or not site_id:
        return None
    try:
        project_id, site_id = UUID(str(project_id)), UUID(str(site_id))
        phase_id = UUID(str(phase_id)) if phase_id else None
    except (ValueError, TypeError, AttributeError) as exc:
        raise PermissionDenied(DENIED) from exc
    site = (
        ProjectSite.objects.select_related("project")
        .filter(
            pk=site_id,
            organization=organization,
            project_id=project_id,
            project__deleted_at__isnull=True,
            is_active=True,
        )
        .first()
    )
    if site is None:
        raise PermissionDenied(DENIED)
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.DAILY_REPORTS_CREATE,
        project=site.project,
        site=site,
        message=DENIED,
    )
    phase = None
    if phase_id:
        phase = ProjectPhase.objects.filter(
            pk=phase_id,
            organization=organization,
            site=site,
            status=ProjectPhaseStatus.ACTIVE,
        ).first()
        if phase is None:
            raise PermissionDenied(DENIED)
    return site, phase


def reference_queryset(
    *,
    actor: User,
    organization: Organization,
    kind: str,
    scope: tuple[ProjectSite, ProjectPhase | None] | None,
    query: str = "",
) -> QuerySet:
    if kind not in KINDS:
        raise PermissionDenied(DENIED)
    if kind == "documents":
        for permission in (
            BusinessPermissionCode.DOCUMENTS_VIEW,
            BusinessPermissionCode.DOCUMENTS_UPLOAD,
        ):
            require_business_permission(
                user=actor,
                organization=organization,
                permission=permission,
                allow_any_scope=True,
                message=DENIED,
            )
        records = get_organization_documents(user=actor, organization=organization)
        fields, ordering = ("title", "document_number", "reference"), ("title", "pk")
    else:
        require_business_permission(
            user=actor,
            organization=organization,
            permission=BusinessPermissionCode.DAILY_REPORTS_LINK_RECORDS,
            allow_any_scope=True,
            message=DENIED,
        )
        selector = (
            get_organization_safety_incidents
            if kind == "safety"
            else get_organization_quality_issues
        )
        records = selector(user=actor, organization=organization)
        number = "incident_number" if kind == "safety" else "issue_number"
        fields, ordering = (number, "description"), (number, "pk")
    if scope is None:
        return records.none()
    site, phase = scope
    if kind != "documents":
        require_business_permission(
            user=actor,
            organization=organization,
            permission=BusinessPermissionCode.DAILY_REPORTS_LINK_RECORDS,
            project=site.project,
            site=site,
            message=DENIED,
        )
        records = records.filter(project=site.project, site=site, phase=phase)
    if query.strip():
        term = normalize_jalali_digits(query.strip())
        condition = Q()
        for field in fields:
            condition |= Q(**{f"{field}__icontains": term})
        records = records.filter(condition)
    return records.order_by(*ordering)


def authorized_options(
    *, actor: User, organization: Organization, kind: str, records: QuerySet
) -> Iterator:
    for record in records.iterator(chunk_size=100):
        if kind == "documents":
            try:
                record = authorized_association_document(
                    user=actor, organization=organization, identifier=record.pk
                )
            except PermissionDenied:
                continue
        yield record


def reference_label(record, kind: str) -> str:
    if kind == "documents":
        return document_choice_label(record)
    number = record.incident_number if kind == "safety" else record.issue_number
    return f"{number} · {record.description[:90]} · {record.get_status_display()}"


def reference_choice_page(
    *,
    actor: User,
    organization: Organization,
    kind: str,
    scope: tuple[ProjectSite, ProjectPhase | None] | None,
    query: str = "",
    page: int = 1,
) -> tuple[list[dict[str, str]], bool]:
    records = reference_queryset(
        actor=actor, organization=organization, kind=kind, scope=scope, query=query
    )
    rows = list(
        islice(
            authorized_options(
                actor=actor, organization=organization, kind=kind, records=records
            ),
            (page - 1) * 20,
            page * 20 + 1,
        )
    )
    return [
        {"value": str(record.pk), "label": reference_label(record, kind)}
        for record in rows[:20]
    ], len(rows) > 20


def create_report_with_references(
    *,
    actor: User,
    organization: Organization,
    report_values: dict[str, Any],
    safety_ids: Sequence[UUID | str] = (),
    quality_ids: Sequence[UUID | str] = (),
    document_ids: Sequence[UUID | str] = (),
    upload_values: dict[str, Any] | None = None,
) -> DailyReport:
    """Create report and every association atomically, cleaning failed uploads."""
    stored_names: list[str] = []
    try:
        with transaction.atomic():
            organization = Organization.objects.select_for_update(no_key=True).get(
                pk=organization.pk
            )
            report = create_daily_report(
                actor=actor, organization=organization, **report_values
            )
            scope = reference_scope(
                actor=actor,
                organization=organization,
                project_id=report.project_id,
                site_id=report.site_id,
                phase_id=report.phase_id,
            )
            for kind, identifiers in (
                ("safety", safety_ids),
                ("quality", quality_ids),
                ("documents", document_ids),
            ):
                try:
                    identifiers = sorted(
                        {UUID(str(identifier)) for identifier in identifiers}
                    )
                except (ValueError, TypeError, AttributeError) as exc:
                    raise PermissionDenied(DENIED) from exc
                if not identifiers:
                    continue
                records = reference_queryset(
                    actor=actor, organization=organization, kind=kind, scope=scope
                ).filter(pk__in=identifiers)
                if set(records.values_list("pk", flat=True)) != set(identifiers):
                    raise PermissionDenied(DENIED)
                # Lock source rows without changing their review, workflow or context.
                list(
                    records.model.objects.filter(
                        pk__in=identifiers, organization=organization
                    )
                    .order_by("pk")
                    .select_for_update(no_key=True)
                )
                records = reference_queryset(
                    actor=actor, organization=organization, kind=kind, scope=scope
                ).filter(pk__in=identifiers)
                if set(records.values_list("pk", flat=True)) != set(identifiers):
                    raise PermissionDenied(DENIED)
                for record in records:
                    if kind == "documents":
                        document = authorized_association_document(
                            user=actor, organization=organization, identifier=record.pk
                        )
                        add_document_link(document=document, actor=actor, target=report)
                    else:
                        reference = DailyReportRecordReference.objects.create(
                            organization=organization,
                            report=report,
                            created_by=actor,
                            **{
                                "safety_incident"
                                if kind == "safety"
                                else "quality_issue": record
                            },
                        )
                        record_audit_event(
                            action=AuditAction.DAILY_REPORT_RECORD_REFERENCED,
                            entity_type="daily_report",
                            entity_id=str(report.pk),
                            organization=organization,
                            actor=actor,
                            metadata={
                                "reference_id": str(reference.pk),
                                "record_type": kind,
                                "record_id": str(record.pk),
                            },
                        )
            if upload_values:
                require_business_permission(
                    user=actor,
                    organization=organization,
                    permission=BusinessPermissionCode.DOCUMENTS_VIEW,
                    project=report.project,
                    site=report.site,
                    message=DENIED,
                )
                create_document(
                    organization=organization,
                    actor=actor,
                    target=report,
                    stored_names=stored_names,
                    **upload_values,
                )
            return report
    except Exception:
        for name in stored_names:
            document_storage.delete(name)
        raise


def report_reference_rows(
    *, actor: User, organization: Organization, report: DailyReport
) -> dict[str, QuerySet]:
    """Intersect both originating and additional references with source read scope."""
    rows = {}
    for kind, selector, field in (
        ("safety", get_organization_safety_incidents, "safety_incident_id"),
        ("quality", get_organization_quality_issues, "quality_issue_id"),
    ):
        try:
            records = selector(user=actor, organization=organization)
        except PermissionDenied:
            continue
        ids = (
            DailyReportRecordReference.objects.filter(
                organization=organization, report=report
            )
            .exclude(**{field: None})
            .values(field)
        )
        rows[kind] = records.filter(Q(daily_report=report) | Q(pk__in=ids)).order_by(
            "pk"
        )
    return rows
