from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import dataclass
from datetime import timedelta

from django.apps import apps
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, models, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.documents.models import DocumentVersion
from apps.organizations.authorization import (
    require_business_permission,
    scope_queryset,
)
from apps.organizations.models import BusinessPermissionCode, Organization
from apps.projects.models import Project
from apps.reporting.models import (
    ProjectCloseoutAssessment,
    ProjectCloseoutAssessmentStatus,
    ProjectCloseoutCase,
    ProjectCloseoutCaseStatus,
    ProjectCloseoutEvent,
    ProjectCloseoutEvidenceLink,
    ProjectCloseoutExportManifest,
    ProjectCloseoutItemSnapshot,
    ProjectCloseoutOutcome,
    ProjectCloseoutProfileStatus,
    ProjectCloseoutProfileVersion,
)
from apps.reporting.project_closeout_catalog import (
    PROJECT_CLOSEOUT_FAMILIES,
    PROJECT_CLOSEOUT_PROFILE_CODE,
)

PROJECT_CLOSEOUT_PERMISSION_CATALOGUE = (
    BusinessPermissionCode.REPORTING_PROJECT_CLOSEOUT_PROFILE_VIEW,
    BusinessPermissionCode.REPORTING_PROJECT_CLOSEOUT_PROFILE_PREPARE,
    BusinessPermissionCode.REPORTING_PROJECT_CLOSEOUT_PROFILE_PUBLISH,
    BusinessPermissionCode.REPORTING_PROJECT_CLOSEOUT_CASE_VIEW,
    BusinessPermissionCode.REPORTING_PROJECT_CLOSEOUT_CASE_PREPARE,
    BusinessPermissionCode.REPORTING_PROJECT_CLOSEOUT_CASE_COORDINATE,
    BusinessPermissionCode.REPORTING_PROJECT_CLOSEOUT_CASE_REVIEW,
    BusinessPermissionCode.REPORTING_PROJECT_CLOSEOUT_CASE_ACCEPT,
    BusinessPermissionCode.REPORTING_PROJECT_CLOSEOUT_CASE_REOPEN,
    BusinessPermissionCode.REPORTING_PROJECT_CLOSEOUT_EVIDENCE_LINK,
    BusinessPermissionCode.REPORTING_PROJECT_CLOSEOUT_SENSITIVE_VIEW,
    BusinessPermissionCode.REPORTING_PROJECT_CLOSEOUT_EXPORT_CREATE,
    BusinessPermissionCode.REPORTING_PROJECT_CLOSEOUT_EXPORT_DOWNLOAD,
    BusinessPermissionCode.REPORTING_PROJECT_CLOSEOUT_AUDIT_VIEW,
)


def _hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
            ensure_ascii=False,
        ).encode()
    ).hexdigest()


def _advisory_lock(*parts: object) -> None:
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode()).digest()
    lock_id = int.from_bytes(digest[:8], byteorder="big", signed=True)
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [lock_id])


def _field_names(model: type[models.Model]) -> set[str]:
    return {field.name for field in model._meta.get_fields()}


@dataclass(frozen=True, slots=True)
class FamilySnapshot:
    outcome: str
    summary: dict[str, object]
    manifest: dict[str, object]
    source_hash: str


def _family_queryset(
    *, model_label: str, project_lookup: str, organization: Organization, project: Project
):
    model = apps.get_model(model_label)
    fields = _field_names(model)
    queryset = model.objects.all()
    if model_label == "knowledge.KnowledgeSourcePin":
        # Knowledge pins point to typed source objects rather than directly to a
        # project. Resolve only source types whose project and permission are
        # already covered by the closeout profile; never associate by UUID alone.
        source_models = {
            "field_observation": "daily_reports.FieldObservation",
            "inspection": "compliance.Inspection",
            "inspection_finding": "compliance.InspectionFinding",
            "nonconformance": "compliance.Nonconformance",
            "capa_action": "compliance.CapaAction",
        }
        project_sources = models.Q(pk__in=[])
        for source_type, source_model_label in source_models.items():
            source_model = apps.get_model(source_model_label)
            source_ids = source_model.objects.filter(
                organization=organization, project=project
            ).values("pk")
            project_sources |= models.Q(source_type=source_type, source_id__in=source_ids)
        return queryset.filter(
            project_sources,
            source_organization=organization,
            candidate_revision__publication_versions__status__in=(
                "published_current",
                "review_due",
                "superseded",
                "archived",
            ),
        ).distinct()
    if "organization" in fields:
        queryset = queryset.filter(organization=organization)
    if project_lookup == "self":
        queryset = queryset.filter(pk=project.pk)
    else:
        queryset = queryset.filter(**{project_lookup: project})
    return queryset


def _capture_family(
    *,
    family_code: str,
    spec: dict[str, object],
    organization: Organization,
    project: Project,
    cutoff_at,
) -> FamilySnapshot:
    manifests: list[dict[str, object]] = []
    status_counts: dict[str, int] = {}
    total = 0
    blocked = False
    for model_label, project_lookup, terminal_statuses in spec["models"]:
        model = apps.get_model(str(model_label))
        fields = _field_names(model)
        queryset = _family_queryset(
            model_label=str(model_label),
            project_lookup=str(project_lookup),
            organization=organization,
            project=project,
        )
        time_field = "updated_at" if "updated_at" in fields else "created_at"
        if time_field in fields:
            queryset = queryset.filter(**{f"{time_field}__lte": cutoff_at})
        ids = [
            str(value)
            for value in queryset.order_by("pk").values_list("pk", flat=True)
        ]
        model_statuses: dict[str, int] = {}
        if "status" in fields:
            for row in queryset.values("status").annotate(count=models.Count("pk")):
                status = str(row["status"])
                count = int(row["count"])
                model_statuses[status] = count
                status_counts[status] = status_counts.get(status, 0) + count
            if ids and terminal_statuses:
                blocked = blocked or any(
                    status not in terminal_statuses for status in model_statuses
                )
        latest = None
        if time_field in fields:
            latest = queryset.aggregate(latest=models.Max(time_field))["latest"]
        manifests.append(
            {
                "model": str(model_label),
                "ids": ids,
                "statuses": model_statuses,
                "latest": latest.isoformat() if latest else None,
            }
        )
        total += len(ids)
    if total == 0:
        outcome = str(spec.get("empty_outcome", ProjectCloseoutOutcome.UNKNOWN))
    elif blocked:
        outcome = ProjectCloseoutOutcome.BLOCKED
    else:
        outcome = ProjectCloseoutOutcome.SATISFIED
    manifest = {
        "family": family_code,
        "project": str(project.pk),
        "cutoff": cutoff_at.isoformat(),
        "sources": manifests,
    }
    return FamilySnapshot(
        outcome=outcome,
        summary={"record_count": total, "status_counts": status_counts},
        manifest=manifest,
        source_hash=_hash(manifests),
    )


def _require_family_permissions(
    *, actor: User, organization: Organization, project: Project
) -> None:
    for spec in PROJECT_CLOSEOUT_FAMILIES.values():
        for permission in spec["permissions"]:
            require_business_permission(
                user=actor,
                organization=organization,
                permission=str(permission),
                message="مجوز دامنه منبع برای کنترل اختتام وجود ندارد.",
                project=project,
            )


@transaction.atomic
def create_closeout_case(
    *,
    organization: Organization,
    actor: User,
    project: Project,
    operation_key: str,
) -> ProjectCloseoutCase:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.REPORTING_PROJECT_CLOSEOUT_CASE_PREPARE,
        message="اجازه تهیه پرونده اختتام را ندارید.",
        project=project,
    )
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.PROJECTS_VIEW,
        message="اجازه مشاهده پروژه را ندارید.",
        project=project,
    )
    if project.organization_id != organization.pk or project.deleted_at is not None:
        raise PermissionDenied("پروژه در دامنه شرکت فعال نیست.")
    _advisory_lock("project-closeout-case", organization.pk, project.pk, operation_key)
    profile = (
        ProjectCloseoutProfileVersion.objects.select_for_update()
        .select_related("definition")
        .get(
            definition__code=PROJECT_CLOSEOUT_PROFILE_CODE,
            definition__is_active=True,
            status=ProjectCloseoutProfileStatus.PUBLISHED,
        )
    )
    fingerprint = _hash(
        {
            "organization": str(organization.pk),
            "project": str(project.pk),
            "profile": str(profile.pk),
        }
    )
    existing = ProjectCloseoutCase.objects.filter(
        organization=organization, create_operation_key=operation_key
    ).first()
    if existing:
        if existing.request_fingerprint != fingerprint:
            raise ValidationError("کلید تکرار پرونده با درخواست متفاوت استفاده شده است.")
        return existing
    return ProjectCloseoutCase.objects.create(
        organization=organization,
        project=project,
        profile_version=profile,
        status=ProjectCloseoutCaseStatus.ACTIVE,
        created_by=actor,
        create_operation_key=operation_key,
        request_fingerprint=fingerprint,
    )


@transaction.atomic
def run_closeout_assessment(
    *,
    case: ProjectCloseoutCase,
    actor: User,
    idempotency_key: str,
    cutoff_at=None,
    expected_revision: int | None = None,
) -> ProjectCloseoutAssessment:
    locked = (
        ProjectCloseoutCase.objects.select_for_update()
        .select_related("project", "profile_version")
        .get(pk=case.pk)
    )
    require_business_permission(
        user=actor,
        organization=locked.organization,
        permission=BusinessPermissionCode.REPORTING_PROJECT_CLOSEOUT_CASE_PREPARE,
        message="اجازه اجرای ارزیابی اختتام را ندارید.",
        project=locked.project,
    )
    _require_family_permissions(
        actor=actor, organization=locked.organization, project=locked.project
    )
    cutoff = cutoff_at or timezone.now()
    _advisory_lock("project-closeout-assessment", locked.pk, idempotency_key)
    fingerprint = _hash(
        {
            "case": str(locked.pk),
            "profile": str(locked.profile_version_id),
            "cutoff": cutoff.isoformat(),
        }
    )
    existing = ProjectCloseoutAssessment.objects.filter(
        organization=locked.organization, idempotency_key=idempotency_key
    ).first()
    if existing:
        if existing.request_fingerprint != fingerprint:
            raise ValidationError("کلید تکرار ارزیابی با درخواست متفاوت استفاده شده است.")
        if existing.status == ProjectCloseoutAssessmentStatus.COMPLETED:
            return existing
        raise ValidationError("اجرای قبلی این کلید نهایی نشده است.")
    if expected_revision is not None and locked.revision != expected_revision:
        raise ValidationError("پرونده تغییر کرده است؛ صفحه را بازخوانی کنید.")
    if locked.status in {
        ProjectCloseoutCaseStatus.ACCEPTED,
        ProjectCloseoutCaseStatus.CANCELLED,
    }:
        raise ValidationError("برای این وضعیت ارزیابی جدید مجاز نیست.")
    assessment = ProjectCloseoutAssessment.objects.create(
        organization=locked.organization,
        case=locked,
        sequence=locked.assessments.count() + 1,
        status=ProjectCloseoutAssessmentStatus.CAPTURING,
        cutoff_at=cutoff,
        requested_by=actor,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
        supersedes=locked.current_assessment,
    )
    snapshots: list[dict[str, object]] = []
    coverage: dict[str, str] = {}
    for family_code, raw_spec in PROJECT_CLOSEOUT_FAMILIES.items():
        spec = dict(raw_spec)
        snapshot = _capture_family(
            family_code=family_code,
            spec=spec,
            organization=locked.organization,
            project=locked.project,
            cutoff_at=cutoff,
        )
        item = ProjectCloseoutItemSnapshot.objects.create(
            organization=locked.organization,
            assessment=assessment,
            family_code=family_code,
            authority_domain=str(spec["authority"]),
            authority_models=[row[0] for row in spec["models"]],
            source_permissions=list(spec["permissions"]),
            outcome=snapshot.outcome,
            summary=snapshot.summary,
            source_manifest=snapshot.manifest,
            source_hash=snapshot.source_hash,
            sensitivity=str(spec["sensitivity"]),
        )
        snapshots.append(
            {"family": family_code, "outcome": item.outcome, "hash": item.source_hash}
        )
        coverage[family_code] = item.outcome
    calculation_hash = _hash(
        {
            "case": str(locked.pk),
            "profile": locked.profile_version.payload_hash,
            "cutoff": cutoff.isoformat(),
            "items": snapshots,
        }
    )
    source_watermark = _hash([row["hash"] for row in snapshots])
    ProjectCloseoutAssessment.objects.filter(pk=assessment.pk).update(
        status=ProjectCloseoutAssessmentStatus.COMPLETED,
        coverage=coverage,
        calculation_hash=calculation_hash,
        source_watermark=source_watermark,
        completed_at=timezone.now(),
    )
    ProjectCloseoutCase.objects.filter(pk=locked.pk).update(
        current_assessment=assessment,
        status=ProjectCloseoutCaseStatus.REVIEW_PENDING,
        revision=models.F("revision") + 1,
    )
    assessment.refresh_from_db()
    record_audit_event(
        action=AuditAction.REPORTING_PROJECT_CLOSEOUT_ASSESSED,
        entity_type="reporting.ProjectCloseoutAssessment",
        entity_id=str(assessment.pk),
        organization=locked.organization,
        actor=actor,
        metadata={
            "project": str(locked.project_id),
            "profile": str(locked.profile_version_id),
            "calculation_hash": calculation_hash,
        },
    )
    return assessment


def _event_fingerprint(
    *,
    case: ProjectCloseoutCase,
    action: str,
    reason: str,
    details: dict[str, object],
    revision: int | None = None,
) -> str:
    return _hash(
        {
            "case": str(case.pk),
            "revision": case.revision if revision is None else revision,
            "action": action,
            "reason": reason.strip(),
            "details": details,
        }
    )


def _existing_event(
    *, case: ProjectCloseoutCase, operation_key: str, fingerprint: str
) -> ProjectCloseoutEvent | None:
    existing = ProjectCloseoutEvent.objects.filter(
        organization=case.organization, operation_key=operation_key
    ).first()
    if existing and existing.request_fingerprint != fingerprint:
        raise ValidationError("کلید تکرار رویداد با درخواست متفاوت استفاده شده است.")
    return existing


@transaction.atomic
def coordinate_closeout_case(
    *,
    case: ProjectCloseoutCase,
    actor: User,
    reason: str,
    operation_key: str,
    assigned_to: User | None = None,
    details: dict[str, object] | None = None,
) -> ProjectCloseoutEvent:
    locked = ProjectCloseoutCase.objects.select_for_update(of=("self",)).select_related(
        "project", "current_assessment"
    ).get(pk=case.pk)
    require_business_permission(
        user=actor,
        organization=locked.organization,
        permission=BusinessPermissionCode.REPORTING_PROJECT_CLOSEOUT_CASE_COORDINATE,
        message="اجازه هماهنگی پرونده اختتام را ندارید.",
        project=locked.project,
    )
    if not reason.strip():
        raise ValidationError("دلیل هماهنگی الزامی است.")
    payload = details or {}
    fingerprint = _event_fingerprint(
        case=locked, action="coordinate", reason=reason, details=payload
    )
    existing = _existing_event(
        case=locked, operation_key=operation_key, fingerprint=fingerprint
    )
    if existing:
        return existing
    event = ProjectCloseoutEvent.objects.create(
        organization=locked.organization,
        case=locked,
        assessment=locked.current_assessment,
        action="coordinate",
        previous_state=locked.status,
        new_state=locked.status,
        reason=reason.strip(),
        details=payload,
        actor=actor,
        assigned_to=assigned_to,
        operation_key=operation_key,
        request_fingerprint=fingerprint,
    )
    _audit_event(event)
    return event


def _audit_event(event: ProjectCloseoutEvent) -> None:
    record_audit_event(
        action=AuditAction.REPORTING_PROJECT_CLOSEOUT_EVENT,
        entity_type="reporting.ProjectCloseoutEvent",
        entity_id=str(event.pk),
        organization=event.organization,
        actor=event.actor,
        metadata={
            "case": str(event.case_id),
            "action": event.action,
            "previous_state": event.previous_state,
            "new_state": event.new_state,
        },
    )


def _assert_current_sources(locked: ProjectCloseoutCase) -> None:
    assessment = locked.current_assessment
    if assessment is None or assessment.status != ProjectCloseoutAssessmentStatus.COMPLETED:
        raise ValidationError("ارزیابی تکمیل‌شده جاری وجود ندارد.")
    for item in assessment.items.all():
        spec = dict(PROJECT_CLOSEOUT_FAMILIES[item.family_code])
        current = _capture_family(
            family_code=item.family_code,
            spec=spec,
            organization=locked.organization,
            project=locked.project,
            cutoff_at=timezone.now(),
        )
        if current.source_hash != item.source_hash:
            raise ValidationError(
                f"منبع {item.family_code} تغییر کرده است؛ ارزیابی جانشین لازم است."
            )


@transaction.atomic
def decide_closeout_case(
    *,
    case: ProjectCloseoutCase,
    actor: User,
    decision: str,
    reason: str,
    operation_key: str,
    expected_revision: int,
) -> ProjectCloseoutEvent:
    locked = (
        ProjectCloseoutCase.objects.select_for_update(of=("self",))
        .select_related("project", "current_assessment")
        .get(pk=case.pk)
    )
    if decision not in {"accept", "reject"}:
        raise ValidationError("تصمیم اختتام معتبر نیست.")
    details = {
        "assessment_hash": getattr(locked.current_assessment, "calculation_hash", "")
    }
    fingerprint = _event_fingerprint(
        case=locked,
        action=decision,
        reason=reason,
        details=details,
        revision=expected_revision,
    )
    existing = _existing_event(
        case=locked, operation_key=operation_key, fingerprint=fingerprint
    )
    if existing:
        return existing
    if locked.revision != expected_revision:
        raise ValidationError("پرونده تغییر کرده است؛ تصمیم با وضعیت قدیمی رد شد.")
    permission = (
        BusinessPermissionCode.REPORTING_PROJECT_CLOSEOUT_CASE_ACCEPT
        if decision == "accept"
        else BusinessPermissionCode.REPORTING_PROJECT_CLOSEOUT_CASE_REVIEW
    )
    require_business_permission(
        user=actor,
        organization=locked.organization,
        permission=permission,
        message="اجازه ثبت این تصمیم اختتام را ندارید.",
        project=locked.project,
    )
    _require_family_permissions(
        actor=actor, organization=locked.organization, project=locked.project
    )
    if not reason.strip():
        raise ValidationError("دلیل تصمیم الزامی است.")
    if locked.status != ProjectCloseoutCaseStatus.REVIEW_PENDING:
        raise ValidationError("پرونده در وضعیت آماده بررسی نیست.")
    assessment = locked.current_assessment
    if assessment is None:
        raise ValidationError("ارزیابی جاری وجود ندارد.")
    if assessment.requested_by_id == actor.pk:
        raise PermissionDenied("تهیه‌کننده نمی‌تواند پرونده خود را بررسی یا بپذیرد.")
    material_last = locked.events.filter(
        action="coordinate", details__material=True
    ).order_by("-created_at").first()
    if decision == "accept" and material_last and material_last.actor_id == actor.pk:
        raise PermissionDenied("آخرین تعیین‌کننده مانع مهم نمی‌تواند تنها پذیرنده باشد.")
    new_state = (
        ProjectCloseoutCaseStatus.ACCEPTED
        if decision == "accept"
        else ProjectCloseoutCaseStatus.REJECTED
    )
    if decision == "accept":
        disallowed = assessment.items.exclude(
            outcome__in=(
                ProjectCloseoutOutcome.SATISFIED,
                ProjectCloseoutOutcome.NOT_APPLICABLE,
            )
        )
        if disallowed.exists():
            raise ValidationError("همه کنترل‌های لازم برای پذیرش برآورده نشده‌اند.")
        _assert_current_sources(locked)
    event = ProjectCloseoutEvent.objects.create(
        organization=locked.organization,
        case=locked,
        assessment=assessment,
        action=decision,
        previous_state=locked.status,
        new_state=new_state,
        reason=reason.strip(),
        details=details,
        actor=actor,
        operation_key=operation_key,
        request_fingerprint=fingerprint,
    )
    ProjectCloseoutCase.objects.filter(pk=locked.pk).update(
        status=new_state, revision=models.F("revision") + 1
    )
    _audit_event(event)
    return event


@transaction.atomic
def reopen_closeout_case(
    *,
    case: ProjectCloseoutCase,
    actor: User,
    reason: str,
    operation_key: str,
    expected_revision: int,
) -> ProjectCloseoutEvent:
    locked = ProjectCloseoutCase.objects.select_for_update(of=("self",)).select_related(
        "project", "current_assessment"
    ).get(pk=case.pk)
    require_business_permission(
        user=actor,
        organization=locked.organization,
        permission=BusinessPermissionCode.REPORTING_PROJECT_CLOSEOUT_CASE_REOPEN,
        message="اجازه بازگشایی پرونده اختتام را ندارید.",
        project=locked.project,
    )
    details = {"requires_successor_assessment": True}
    fingerprint = _event_fingerprint(
        case=locked,
        action="reopen",
        reason=reason,
        details=details,
        revision=expected_revision,
    )
    existing = _existing_event(
        case=locked, operation_key=operation_key, fingerprint=fingerprint
    )
    if existing:
        return existing
    if locked.revision != expected_revision:
        raise ValidationError("پرونده تغییر کرده است؛ بازگشایی رد شد.")
    if locked.status != ProjectCloseoutCaseStatus.ACCEPTED or not reason.strip():
        raise ValidationError("فقط پرونده پذیرفته‌شده با دلیل قابل بازگشایی است.")
    event = ProjectCloseoutEvent.objects.create(
        organization=locked.organization,
        case=locked,
        assessment=locked.current_assessment,
        action="reopen",
        previous_state=locked.status,
        new_state=ProjectCloseoutCaseStatus.REOPENED,
        reason=reason.strip(),
        details=details,
        actor=actor,
        operation_key=operation_key,
        request_fingerprint=fingerprint,
    )
    ProjectCloseoutCase.objects.filter(pk=locked.pk).update(
        status=ProjectCloseoutCaseStatus.REOPENED,
        revision=models.F("revision") + 1,
    )
    _audit_event(event)
    return event


@transaction.atomic
def link_closeout_evidence(
    *,
    case: ProjectCloseoutCase,
    actor: User,
    document_version: DocumentVersion,
    evidence_role: str,
    item: ProjectCloseoutItemSnapshot | None = None,
    sensitivity: str = "normal",
) -> ProjectCloseoutEvidenceLink:
    locked = ProjectCloseoutCase.objects.select_for_update(of=("self",)).select_related(
        "project"
    ).get(pk=case.pk)
    require_business_permission(
        user=actor,
        organization=locked.organization,
        permission=BusinessPermissionCode.REPORTING_PROJECT_CLOSEOUT_EVIDENCE_LINK,
        message="اجازه پیوند شاهد اختتام را ندارید.",
        project=locked.project,
    )
    require_business_permission(
        user=actor,
        organization=locked.organization,
        permission=BusinessPermissionCode.DOCUMENTS_VIEW,
        message="اجازه مشاهده نسخه سند را ندارید.",
        project=locked.project,
    )
    if document_version.organization_id != locked.organization_id:
        raise PermissionDenied("نسخه سند متعلق به شرکت فعال نیست.")
    if item is not None and item.assessment.case_id != locked.pk:
        raise ValidationError("قلم شاهد متعلق به این پرونده نیست.")
    return ProjectCloseoutEvidenceLink.objects.create(
        organization=locked.organization,
        case=locked,
        item=item,
        document_version=document_version,
        document_hash=document_version.sha256,
        evidence_role=evidence_role.strip(),
        sensitivity=sensitivity,
        linked_by=actor,
    )


def closeout_cases(*, organization: Organization, actor: User):
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.REPORTING_PROJECT_CLOSEOUT_CASE_VIEW,
        message="اجازه مشاهده پرونده‌های اختتام را ندارید.",
        allow_any_scope=True,
    )
    queryset = ProjectCloseoutCase.objects.filter(organization=organization)
    queryset = scope_queryset(
        queryset,
        membership=membership,
        project_lookup="project",
        include_site_parent=True,
    )
    return queryset.select_related(
        "project", "profile_version__definition", "current_assessment"
    ).order_by("-updated_at")


def closeout_case_detail(
    *, organization: Organization, actor: User, case_id: str
) -> ProjectCloseoutCase:
    case = (
        ProjectCloseoutCase.objects.filter(organization=organization, pk=case_id)
        .select_related("project", "profile_version__definition", "current_assessment")
        .prefetch_related("current_assessment__items", "events", "evidence_links")
        .first()
    )
    if case is None:
        raise PermissionDenied("پرونده در شرکت فعال یافت نشد.")
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.REPORTING_PROJECT_CLOSEOUT_CASE_VIEW,
        message="اجازه مشاهده پرونده اختتام را ندارید.",
        project=case.project,
    )
    _require_family_permissions(actor=actor, organization=organization, project=case.project)
    return case


@transaction.atomic
def export_closeout_csv(
    *,
    case: ProjectCloseoutCase,
    actor: User,
    idempotency_key: str,
    purpose: str,
) -> tuple[ProjectCloseoutExportManifest, bytes]:
    locked = ProjectCloseoutCase.objects.select_for_update(of=("self",)).select_related(
        "project", "current_assessment"
    ).get(pk=case.pk)
    for permission in (
        BusinessPermissionCode.REPORTING_PROJECT_CLOSEOUT_CASE_VIEW,
        BusinessPermissionCode.REPORTING_PROJECT_CLOSEOUT_EXPORT_CREATE,
        BusinessPermissionCode.REPORTING_PROJECT_CLOSEOUT_EXPORT_DOWNLOAD,
    ):
        require_business_permission(
            user=actor,
            organization=locked.organization,
            permission=permission,
            message="اجازه خروجی اختتام را ندارید.",
            project=locked.project,
        )
    _require_family_permissions(
        actor=actor, organization=locked.organization, project=locked.project
    )
    assessment = locked.current_assessment
    if assessment is None:
        raise ValidationError("ارزیابی جاری برای خروجی وجود ندارد.")
    items = list(assessment.items.order_by("family_code"))
    fingerprint = _hash(
        {
            "case": str(locked.pk),
            "assessment": str(assessment.pk),
            "purpose": purpose.strip(),
            "actor": str(actor.pk),
            "items": [str(item.pk) for item in items],
        }
    )
    existing = ProjectCloseoutExportManifest.objects.filter(
        organization=locked.organization, idempotency_key=idempotency_key
    ).first()
    if existing and existing.request_fingerprint != fingerprint:
        raise ValidationError("کلید تکرار خروجی با درخواست متفاوت استفاده شده است.")
    sensitive_allowed = True
    try:
        require_business_permission(
            user=actor,
            organization=locked.organization,
            permission=BusinessPermissionCode.REPORTING_PROJECT_CLOSEOUT_SENSITIVE_VIEW,
            message="",
            project=locked.project,
        )
    except PermissionDenied:
        sensitive_allowed = False
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        [
            "project",
            "profile_version",
            "assessment",
            "cutoff",
            "family",
            "authority",
            "outcome",
            "record_count",
            "status_counts",
            "source_hash",
        ]
    )
    for item in items:
        masked = item.sensitivity != "normal" and not sensitive_allowed
        writer.writerow(
            [
                locked.project.code,
                locked.profile_version.version,
                assessment.sequence,
                assessment.cutoff_at.isoformat(),
                item.family_code,
                item.authority_domain,
                item.outcome,
                item.summary.get("record_count", "") if not masked else "MASKED",
                json.dumps(item.summary.get("status_counts", {}), ensure_ascii=False)
                if not masked
                else "MASKED",
                item.source_hash if not masked else "MASKED",
            ]
        )
    content = ("\ufeff" + output.getvalue()).encode("utf-8")
    content_hash = hashlib.sha256(content).hexdigest()
    created = existing is None
    manifest = existing or ProjectCloseoutExportManifest.objects.create(
        organization=locked.organization,
        case=locked,
        assessment=assessment,
        created_by=actor,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
        item_ids=[str(item.pk) for item in items],
        content_hash=content_hash,
        purpose=purpose.strip(),
        expires_at=timezone.now() + timedelta(minutes=10),
    )
    if created:
        record_audit_event(
            action=AuditAction.REPORTING_PROJECT_CLOSEOUT_EXPORTED,
            entity_type="reporting.ProjectCloseoutExportManifest",
            entity_id=str(manifest.pk),
            organization=locked.organization,
            actor=actor,
            metadata={"case": str(locked.pk), "content_hash": content_hash},
        )
    return manifest, content
