"""Application services for the accepted P9-S01–S05 Field Operations slice."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping
from datetime import datetime

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.daily_reports.field_models import (
    FieldDownstreamProposal,
    FieldObservation,
    FieldObservationDraftRevision,
    FieldObservationEvidenceLink,
    FieldObservationKind,
    FieldObservationStatus,
    FieldObservationTransition,
    FieldProposalFamily,
    FieldProposalStatus,
    FieldProposalTransition,
)
from apps.documents.models import DocumentVersion
from apps.documents.services import get_organization_document
from apps.organizations.authorization import (
    get_active_membership,
    has_business_permission,
    require_business_permission,
    scope_queryset,
)
from apps.organizations.models import (
    BusinessPermissionCode,
    Organization,
    OrganizationMembership,
)
from apps.projects.models import (
    Activity,
    Project,
    ProjectPhase,
    ProjectPhaseStatus,
    ProjectSite,
)


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _sha(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _validate_project(organization: Organization, project: Project) -> None:
    if project.organization_id != organization.pk or project.deleted_at is not None:
        raise PermissionDenied("پروژه در این سازمان فعال نیست.")


def _validate_context(
    *, organization: Organization, project: Project, site: ProjectSite | None,
    phase: ProjectPhase | None, activity: Activity | None,
) -> None:
    _validate_project(organization, project)
    if site is not None and (
        site.organization_id != organization.pk or site.project_id != project.pk or not site.is_active
    ):
        raise PermissionDenied("کارگاه متعلق به پروژه فعال نیست.")
    if phase is not None and (
        phase.organization_id != organization.pk or not site or phase.site_id != site.pk
        or phase.status != ProjectPhaseStatus.ACTIVE
    ):
        raise PermissionDenied("فاز پروژه برای این کارگاه فعال نیست.")
    if activity is not None and (activity.organization_id != organization.pk or activity.project_id != project.pk):
        raise PermissionDenied("فعالیت متعلق به پروژه نیست.")


def _permission(
    *, actor: User, organization: Organization, code: BusinessPermissionCode,
    project: Project, site: ProjectSite | None,
) -> OrganizationMembership:
    return require_business_permission(
        user=actor, organization=organization, permission=code,
        project=project, site=site,
        message="برای این عملیات مجوز و دامنه پروژه/کارگاه لازم است.",
        allow_site_parent=site is None,
    )


def _client_context(value: Mapping[str, object] | None) -> dict[str, str]:
    if not value:
        return {}
    allowed = {"client_kind", "client_version", "platform"}
    result: dict[str, str] = {}
    for key, raw in value.items():
        if key in allowed and raw is not None:
            text = str(raw).strip()
            if len(text) > 80:
                raise ValidationError("اطلاعات زمینه کاربر بیش از حد مجاز است.")
            result[key] = text
    return result


def _observation_snapshot(observation: FieldObservation, *, include_location: bool = True) -> dict[str, object]:
    snapshot: dict[str, object] = {
        "id": str(observation.pk),
        "organization_id": str(observation.organization_id),
        "project_id": str(observation.project_id),
        "site_id": str(observation.site_id) if observation.site_id else None,
        "phase_id": str(observation.phase_id) if observation.phase_id else None,
        "activity_id": str(observation.activity_id) if observation.activity_id else None,
        "kind": observation.kind,
        "title": observation.title,
        "summary": observation.summary,
        "structured_payload": observation.structured_payload,
        "payload_schema_version": observation.payload_schema_version,
        "manual_context": observation.manual_context,
        "captured_at": observation.captured_at.isoformat() if observation.captured_at else None,
        "captured_timezone_offset_minutes": observation.captured_timezone_offset_minutes,
        "effective_at": observation.effective_at.isoformat() if observation.effective_at else None,
        "location_permission": observation.location_permission,
        "location_mismatch_note": observation.location_mismatch_note,
        "client_context": observation.client_context,
        "replaces": str(observation.replaces_id) if observation.replaces_id else None,
        "correction_reason": observation.correction_reason,
    }
    if include_location:
        snapshot.update(
            {
                "latitude": str(observation.latitude) if observation.latitude is not None else None,
                "longitude": str(observation.longitude) if observation.longitude is not None else None,
                "horizontal_accuracy_meters": str(observation.horizontal_accuracy_meters)
                if observation.horizontal_accuracy_meters is not None else None,
                "location_captured_at": observation.location_captured_at.isoformat()
                if observation.location_captured_at else None,
            }
        )
    return snapshot


def _canonical_observation_hash(observation: FieldObservation) -> str:
    attachments = list(
        observation.evidence_links.order_by("created_at").values_list(
            "document_id", "document_version_id", "sha256"
        )
    )
    snapshot = _observation_snapshot(observation)
    snapshot["evidence"] = [[str(item) for item in row] for row in attachments]
    return _sha(snapshot)


def _transition_audit_action(to_status: str) -> AuditAction:
    return {
        FieldObservationStatus.SUBMITTED: AuditAction.FIELD_OBSERVATION_SUBMITTED,
        FieldObservationStatus.IN_REVIEW: AuditAction.FIELD_OBSERVATION_REVIEW_STARTED,
        FieldObservationStatus.ACCEPTED: AuditAction.FIELD_OBSERVATION_ACCEPTED,
        FieldObservationStatus.REJECTED: AuditAction.FIELD_OBSERVATION_REJECTED,
        FieldObservationStatus.SUPERSEDED: AuditAction.FIELD_OBSERVATION_SUPERSEDED,
    }[to_status]


def _record_observation_transition(
    *, observation: FieldObservation, actor: User, from_status: str, to_status: str,
    reason: str, operation_key: uuid.UUID, payload_hash: str,
) -> FieldObservationTransition:
    existing = FieldObservationTransition.objects.filter(
        organization=observation.organization, actor=actor, to_status=to_status, operation_key=operation_key
    ).first()
    if existing:
        if existing.payload_hash != payload_hash or existing.observation_id != observation.pk:
            raise ValidationError("کلید تکرار با داده متفاوت استفاده شده است.")
        return existing
    transition = FieldObservationTransition.objects.create(
        organization=observation.organization, observation=observation,
        from_status=from_status, to_status=to_status, actor=actor,
        reason=reason.strip(), canonical_hash=observation.canonical_hash,
        operation_key=operation_key, payload_hash=payload_hash,
    )
    record_audit_event(
        action=_transition_audit_action(to_status), entity_type="field_observation",
        entity_id=observation.pk, organization=observation.organization, actor=actor,
        metadata={"from_status": from_status, "to_status": to_status, "reason": reason.strip(), "operation_key": str(operation_key)},
    )
    return transition


@transaction.atomic
def create_field_observation(
    *, organization: Organization, actor: User, project: Project, site: ProjectSite | None,
    kind: str, title: str, summary: str = "", structured_payload: dict[str, object] | None = None,
    phase: ProjectPhase | None = None, activity: Activity | None = None,
    manual_context: str = "", captured_at: datetime | None = None,
    captured_timezone_offset_minutes: int | None = None, effective_at: datetime | None = None,
    location_permission: str = "not_requested", latitude=None, longitude=None,
    horizontal_accuracy_meters=None, location_captured_at: datetime | None = None,
    location_mismatch_note: str = "",
    client_context: Mapping[str, object] | None = None, operation_key: uuid.UUID | None = None,
    replaces: FieldObservation | None = None, correction_reason: str = "",
) -> FieldObservation:
    operation_key = operation_key or uuid.uuid4()
    _permission(actor=actor, organization=organization, code=BusinessPermissionCode.FIELD_OBSERVATIONS_CAPTURE, project=project, site=site)
    _validate_context(organization=organization, project=project, site=site, phase=phase, activity=activity)
    if kind not in FieldObservationKind.values:
        raise ValidationError("نوع مشاهده پشتیبانی نمی‌شود.")
    payload = structured_payload or {}
    payload_hash = _sha(
        {
            "project": str(project.pk),
            "site": str(site.pk) if site else None,
            "phase": str(phase.pk) if phase else None,
            "activity": str(activity.pk) if activity else None,
            "kind": kind,
            "title": title.strip(),
            "summary": summary.strip(),
            "payload": payload,
            "manual_context": manual_context.strip(),
            "captured_at": captured_at.isoformat() if captured_at else None,
            "captured_timezone_offset_minutes": captured_timezone_offset_minutes,
            "effective_at": effective_at.isoformat() if effective_at else None,
            "location_permission": location_permission,
            "latitude": str(latitude) if latitude is not None else None,
            "longitude": str(longitude) if longitude is not None else None,
            "accuracy": str(horizontal_accuracy_meters) if horizontal_accuracy_meters is not None else None,
            "location_captured_at": location_captured_at.isoformat() if location_captured_at else None,
            "location_mismatch_note": location_mismatch_note.strip(),
            "client_context": _client_context(client_context),
            "replaces": str(replaces.pk) if replaces else None,
            "correction_reason": correction_reason.strip(),
        }
    )
    existing = FieldObservation.objects.filter(organization=organization, created_by=actor, create_operation_key=operation_key).first()
    if existing:
        if existing.create_payload_hash != payload_hash:
            raise ValidationError("کلید تکرار با داده متفاوت استفاده شده است.")
        return existing
    observation = FieldObservation.objects.create(
        organization=organization, project=project, site=site, phase=phase, activity=activity,
        kind=kind, title=title.strip(), summary=summary.strip(), structured_payload=payload,
        manual_context=manual_context.strip(), captured_at=captured_at, captured_timezone_offset_minutes=captured_timezone_offset_minutes,
        effective_at=effective_at, location_permission=location_permission, latitude=latitude, longitude=longitude,
        horizontal_accuracy_meters=horizontal_accuracy_meters, location_captured_at=location_captured_at,
        location_mismatch_note=location_mismatch_note.strip(),
        client_context=_client_context(client_context), create_operation_key=operation_key,
        create_payload_hash=payload_hash, created_by=actor, replaces=replaces,
        correction_reason=correction_reason.strip(),
    )
    FieldObservationDraftRevision.objects.create(
        organization=organization, observation=observation, revision=1,
        snapshot=_observation_snapshot(observation), payload_hash=payload_hash,
        actor=actor, operation_key=operation_key,
    )
    record_audit_event(
        action=AuditAction.FIELD_OBSERVATION_CREATED, entity_type="field_observation",
        entity_id=observation.pk, organization=organization, actor=actor,
        metadata={"project_id": str(project.pk), "site_id": str(site.pk) if site else None, "operation_key": str(operation_key)},
    )
    return observation


@transaction.atomic
def update_field_observation(
    *, organization: Organization, actor: User, observation_id: str, expected_revision: int,
    operation_key: uuid.UUID, **changes: object,
) -> FieldObservation:
    observation = _get_locked_observation(organization=organization, actor=actor, observation_id=observation_id, permission=BusinessPermissionCode.FIELD_OBSERVATIONS_CAPTURE)
    allowed = {
        "project", "site", "phase", "activity", "kind", "title", "summary",
        "structured_payload", "manual_context", "captured_at",
        "captured_timezone_offset_minutes", "effective_at", "location_permission", "latitude",
        "longitude", "horizontal_accuracy_meters", "location_captured_at", "location_mismatch_note",
        "client_context",
    }
    if set(changes) - allowed:
        raise ValidationError("فیلد ویرایش‌نشده در درخواست وجود دارد.")
    request_payload_hash = _sha(
        {
            "expected_revision": expected_revision,
            "changes": {
                key: str(value.pk) if hasattr(value, "pk") else value
                for key, value in changes.items()
            },
        }
    )
    existing = FieldObservationDraftRevision.objects.filter(
        organization=organization,
        actor=actor,
        operation_key=operation_key,
    ).first()
    if existing:
        if (
            existing.observation_id != observation.pk
            or existing.snapshot.get("_operation_request_hash") != request_payload_hash
        ):
            raise ValidationError("کلید تکرار با داده متفاوت استفاده شده است.")
        return observation
    if observation.status != FieldObservationStatus.DRAFT:
        raise ValidationError("فقط پیش‌نویس قابل ویرایش است.")
    if observation.revision != expected_revision:
        raise ValidationError("پیش‌نویس قدیمی است؛ ابتدا نسخه جدید را دریافت کنید.")
    project = changes.get("project", observation.project)
    site = changes.get("site", observation.site)
    phase = changes.get("phase", observation.phase)
    activity = changes.get("activity", observation.activity)
    kind = changes.get("kind", observation.kind)
    if not isinstance(project, Project) or (
        site is not None and not isinstance(site, ProjectSite)
    ) or (phase is not None and not isinstance(phase, ProjectPhase)) or (
        activity is not None and not isinstance(activity, Activity)
    ):
        raise ValidationError("زمینه پروژه/کارگاه پیش‌نویس معتبر نیست.")
    if kind not in FieldObservationKind.values:
        raise ValidationError("نوع مشاهده پشتیبانی نمی‌شود.")
    _permission(
        actor=actor,
        organization=organization,
        code=BusinessPermissionCode.FIELD_OBSERVATIONS_CAPTURE,
        project=project,
        site=site,
    )
    _validate_context(
        organization=organization,
        project=project,
        site=site,
        phase=phase,
        activity=activity,
    )
    for key, value in changes.items():
        setattr(observation, key, _client_context(value) if key == "client_context" else value)
    observation.revision += 1
    observation.save()
    payload_hash = _sha(_observation_snapshot(observation))
    snapshot = _observation_snapshot(observation)
    snapshot["_operation_request_hash"] = request_payload_hash
    FieldObservationDraftRevision.objects.create(
        organization=organization, observation=observation, revision=observation.revision,
        snapshot=snapshot, payload_hash=payload_hash,
        actor=actor, operation_key=operation_key,
    )
    record_audit_event(
        action=AuditAction.FIELD_OBSERVATION_SAVED, entity_type="field_observation",
        entity_id=observation.pk, organization=organization, actor=actor,
        metadata={"revision": observation.revision, "operation_key": str(operation_key)},
    )
    return observation


def _get_locked_observation(
    *,
    organization: Organization,
    actor: User,
    observation_id: str,
    permission: BusinessPermissionCode,
    require_active_context: bool = True,
) -> FieldObservation:
    try:
        observation = FieldObservation.objects.select_for_update(of=("self",)).select_related("project", "site", "phase", "activity").get(pk=observation_id, organization=organization)
    except FieldObservation.DoesNotExist as exc:
        raise PermissionDenied("مشاهده میدانی در این سازمان یافت نشد.") from exc
    _permission(actor=actor, organization=organization, code=permission, project=observation.project, site=observation.site)
    if require_active_context:
        _validate_context(
            organization=organization,
            project=observation.project,
            site=observation.site,
            phase=observation.phase,
            activity=observation.activity,
        )
    return observation


def get_field_observation(*, organization: Organization, actor: User, observation_id: str) -> FieldObservation:
    with transaction.atomic():
        return _get_locked_observation(
            organization=organization,
            actor=actor,
            observation_id=observation_id,
            permission=BusinessPermissionCode.FIELD_OBSERVATIONS_VIEW,
            require_active_context=False,
        )


def list_field_observations(*, organization: Organization, actor: User) -> QuerySet[FieldObservation]:
    membership = get_active_membership(user=actor, organization=organization)
    if not has_business_permission(user=actor, organization=organization, permission=BusinessPermissionCode.FIELD_OBSERVATIONS_VIEW, allow_any_scope=True):
        raise PermissionDenied("مشاهده مشاهدات میدانی مجاز نیست.")
    queryset = FieldObservation.objects.filter(organization=organization).select_related("project", "site", "created_by")
    return scope_queryset(queryset, membership=membership, project_lookup="project_id", site_lookup="site_id")


@transaction.atomic
def attach_field_evidence(*, organization: Organization, actor: User, observation_id: str, document_version_id: str, operation_key: uuid.UUID) -> FieldObservationEvidenceLink:
    observation = _get_locked_observation(organization=organization, actor=actor, observation_id=observation_id, permission=BusinessPermissionCode.FIELD_OBSERVATIONS_CAPTURE)
    if observation.status != FieldObservationStatus.DRAFT:
        raise ValidationError("شواهد فقط به پیش‌نویس افزوده می‌شود.")
    version = DocumentVersion.objects.select_related("document").filter(pk=document_version_id, organization=organization).first()
    if version is None or not version.is_available:
        raise PermissionDenied("نسخه DMS در این سازمان یافت نشد یا برای استفاده ایمن آماده نیست.")
    get_organization_document(user=actor, organization=organization, document_id=str(version.document_id))
    existing = FieldObservationEvidenceLink.objects.filter(organization=organization, created_by=actor, operation_key=operation_key).first()
    payload_hash = _sha({"observation": str(observation.pk), "document_version": str(version.pk), "sha256": version.sha256})
    if existing:
        if existing.observation_id != observation.pk or existing.payload_hash != payload_hash:
            raise ValidationError("کلید تکرار با داده متفاوت استفاده شده است.")
        return existing
    return FieldObservationEvidenceLink.objects.create(
        organization=organization, document=version.document, document_version=version,
        field_observation=observation, sha256=version.sha256, created_by=actor,
        operation_key=operation_key, payload_hash=payload_hash,
    )


@transaction.atomic
def submit_field_observation(*, organization: Organization, actor: User, observation_id: str, operation_key: uuid.UUID) -> FieldObservation:
    observation = _get_locked_observation(organization=organization, actor=actor, observation_id=observation_id, permission=BusinessPermissionCode.FIELD_OBSERVATIONS_SUBMIT)
    payload_hash = _sha({"observation": str(observation.pk), "revision": observation.revision, "status": FieldObservationStatus.SUBMITTED})
    existing = FieldObservationTransition.objects.filter(organization=organization, actor=actor, to_status=FieldObservationStatus.SUBMITTED, operation_key=operation_key).first()
    if existing:
        if existing.observation_id != observation.pk or existing.payload_hash != payload_hash:
            raise ValidationError("کلید تکرار با داده متفاوت استفاده شده است.")
        return observation
    if observation.status != FieldObservationStatus.DRAFT:
        raise ValidationError("فقط پیش‌نویس قابل ارسال است.")
    for link in observation.evidence_links.select_related("document_version"):
        if not link.document_version.is_available:
            raise PermissionDenied("همه نسخه‌های DMS پیوست‌شده باید برای استفاده ایمن آماده باشند.")
        if link.sha256 != link.document_version.sha256:
            raise ValidationError("یکپارچگی نسخه DMS پیوست‌شده تأیید نمی‌شود.")
    observation.canonical_hash = _canonical_observation_hash(observation)
    observation.status = FieldObservationStatus.SUBMITTED
    observation.submitted_by = actor
    observation.submitted_membership = get_active_membership(user=actor, organization=organization)
    observation.submitted_at = timezone.now()
    observation.save()
    _record_observation_transition(observation=observation, actor=actor, from_status=FieldObservationStatus.DRAFT, to_status=FieldObservationStatus.SUBMITTED, reason="", operation_key=operation_key, payload_hash=payload_hash)
    return observation


@transaction.atomic
def start_field_observation_review(*, organization: Organization, actor: User, observation_id: str, operation_key: uuid.UUID) -> FieldObservation:
    observation = _get_locked_observation(organization=organization, actor=actor, observation_id=observation_id, permission=BusinessPermissionCode.FIELD_OBSERVATIONS_REVIEW)
    if observation.submitted_by_id == actor.pk:
        raise PermissionDenied("ارسال‌کننده نمی‌تواند بررسی را آغاز کند.")
    payload_hash = _sha({"observation": str(observation.pk), "status": FieldObservationStatus.IN_REVIEW})
    existing = FieldObservationTransition.objects.filter(organization=organization, actor=actor, to_status=FieldObservationStatus.IN_REVIEW, operation_key=operation_key).first()
    if existing:
        if existing.observation_id != observation.pk or existing.payload_hash != payload_hash:
            raise ValidationError("کلید تکرار با داده متفاوت استفاده شده است.")
        return observation
    if observation.status != FieldObservationStatus.SUBMITTED:
        raise ValidationError("فقط مشاهده ارسال‌شده وارد بررسی می‌شود.")
    observation.status = FieldObservationStatus.IN_REVIEW
    observation.review_started_by = actor
    observation.review_started_at = timezone.now()
    observation.save()
    _record_observation_transition(observation=observation, actor=actor, from_status=FieldObservationStatus.SUBMITTED, to_status=FieldObservationStatus.IN_REVIEW, reason="", operation_key=operation_key, payload_hash=payload_hash)
    return observation


@transaction.atomic
def review_field_observation(*, organization: Organization, actor: User, observation_id: str, accepted: bool, reason: str, operation_key: uuid.UUID) -> FieldObservation:
    observation = _get_locked_observation(organization=organization, actor=actor, observation_id=observation_id, permission=BusinessPermissionCode.FIELD_OBSERVATIONS_REVIEW)
    if observation.created_by_id == actor.pk or observation.submitted_by_id == actor.pk:
        raise PermissionDenied("ایجادکننده یا ارسال‌کننده نمی‌تواند مشاهده را نهایی بررسی کند.")
    reason = reason.strip()
    if not accepted and not reason:
        raise ValidationError("دلیل رد مشاهده الزامی است.")
    to_status = FieldObservationStatus.ACCEPTED if accepted else FieldObservationStatus.REJECTED
    payload_hash = _sha({"observation": str(observation.pk), "status": to_status, "reason": reason})
    existing = FieldObservationTransition.objects.filter(organization=organization, actor=actor, to_status=to_status, operation_key=operation_key).first()
    if existing:
        if existing.observation_id != observation.pk or existing.payload_hash != payload_hash:
            raise ValidationError("کلید تکرار با داده متفاوت استفاده شده است.")
        return observation
    if observation.status != FieldObservationStatus.IN_REVIEW:
        raise ValidationError("فقط مشاهده در حال بررسی قابل تصمیم است.")
    observation.status = to_status
    observation.reviewed_by = actor
    observation.reviewed_at = timezone.now()
    observation.review_reason = reason
    observation.save()
    _record_observation_transition(observation=observation, actor=actor, from_status=FieldObservationStatus.IN_REVIEW, to_status=to_status, reason=reason, operation_key=operation_key, payload_hash=payload_hash)
    if accepted and observation.replaces_id:
        predecessor = FieldObservation.objects.select_for_update().get(pk=observation.replaces_id, organization=organization)
        if predecessor.status == FieldObservationStatus.ACCEPTED:
            predecessor.status = FieldObservationStatus.SUPERSEDED
            predecessor.save(update_fields=["status", "updated_at"])
            predecessor_hash = _sha({"observation": str(predecessor.pk), "status": FieldObservationStatus.SUPERSEDED, "successor": str(observation.pk)})
            _record_observation_transition(observation=predecessor, actor=actor, from_status=FieldObservationStatus.ACCEPTED, to_status=FieldObservationStatus.SUPERSEDED, reason=f"جایگزین شد: {observation.pk}", operation_key=operation_key, payload_hash=predecessor_hash)
    return observation


@transaction.atomic
def create_field_correction(*, organization: Organization, actor: User, predecessor_id: str, operation_key: uuid.UUID, **changes: object) -> FieldObservation:
    predecessor = _get_locked_observation(
        organization=organization,
        actor=actor,
        observation_id=predecessor_id,
        permission=BusinessPermissionCode.FIELD_OBSERVATIONS_CAPTURE,
        require_active_context=False,
    )
    if predecessor.status not in (FieldObservationStatus.SUBMITTED, FieldObservationStatus.IN_REVIEW, FieldObservationStatus.ACCEPTED, FieldObservationStatus.REJECTED, FieldObservationStatus.SUPERSEDED):
        raise ValidationError("فقط سابقه ارسال‌شده قابل اصلاح است.")
    if predecessor.replacement_candidates.filter(status=FieldObservationStatus.ACCEPTED).exists():
        raise ValidationError("برای این مشاهده جایگزین پذیرفته‌شده وجود دارد.")
    allowed = {"kind", "title", "summary", "structured_payload", "phase", "activity", "site", "manual_context", "captured_at", "captured_timezone_offset_minutes", "effective_at", "location_permission", "latitude", "longitude", "horizontal_accuracy_meters", "location_captured_at", "location_mismatch_note", "client_context"}
    if not changes.get("correction_reason") or set(changes) - (allowed | {"correction_reason"}):
        raise ValidationError("دلیل اصلاح و داده‌های مجاز الزامی است.")
    data = {key: changes.get(key, getattr(predecessor, key)) for key in allowed}
    prior_correction = FieldObservation.objects.filter(
        organization=organization,
        created_by=actor,
        create_operation_key=operation_key,
    ).exists()
    correction = create_field_observation(
        organization=organization,
        actor=actor,
        project=predecessor.project,
        site=data.pop("site"),
        phase=data.pop("phase"),
        activity=data.pop("activity"),
        operation_key=operation_key,
        replaces=predecessor,
        correction_reason=str(changes["correction_reason"]),
        **data,  # type: ignore[arg-type]
    )
    if not prior_correction:
        record_audit_event(
            action=AuditAction.FIELD_OBSERVATION_CORRECTED,
            entity_type="field_observation",
            entity_id=correction.pk,
            organization=organization,
            actor=actor,
            metadata={
                "predecessor_id": str(predecessor.pk),
                "operation_key": str(operation_key),
            },
        )
    return correction


@transaction.atomic
def create_field_proposal(*, organization: Organization, actor: User, observation_id: str, family: str, lines: list[dict[str, object]], operation_key: uuid.UUID, effective_at: datetime | None = None) -> FieldDownstreamProposal:
    observation = _get_locked_observation(organization=organization, actor=actor, observation_id=observation_id, permission=BusinessPermissionCode.FIELD_PROPOSALS_PREPARE)
    if observation.status != FieldObservationStatus.ACCEPTED:
        raise ValidationError("فقط مشاهده پذیرفته‌شده می‌تواند پیشنهاد بسازد.")
    if family not in FieldProposalFamily.values:
        raise ValidationError("خانواده پیشنهاد پشتیبانی نمی‌شود.")
    if not isinstance(lines, list) or not lines:
        raise ValidationError("حداقل یک سطر پیشنهاد لازم است.")
    payload_hash = _sha({"observation": str(observation.pk), "family": family, "lines": lines, "effective_at": effective_at.isoformat() if effective_at else None})
    existing = FieldDownstreamProposal.objects.filter(organization=organization, created_by=actor, create_operation_key=operation_key).first()
    if existing:
        if existing.create_payload_hash != payload_hash:
            raise ValidationError("کلید تکرار با داده متفاوت استفاده شده است.")
        return existing
    proposal = FieldDownstreamProposal.objects.create(
        organization=organization, observation=observation, family=family, project=observation.project, site=observation.site,
        effective_at=effective_at, lines=lines, source_canonical_hash=observation.canonical_hash,
        create_operation_key=operation_key, create_payload_hash=payload_hash, created_by=actor,
    )
    record_audit_event(action=AuditAction.FIELD_PROPOSAL_CREATED, entity_type="field_proposal", entity_id=proposal.pk, organization=organization, actor=actor, metadata={"family": family, "operation_key": str(operation_key)})
    return proposal


@transaction.atomic
def submit_field_proposal(*, organization: Organization, actor: User, proposal_id: str, operation_key: uuid.UUID) -> FieldDownstreamProposal:
    proposal = _get_locked_proposal(organization=organization, actor=actor, proposal_id=proposal_id, permission=BusinessPermissionCode.FIELD_PROPOSALS_PREPARE)
    payload_hash = _sha({"proposal": str(proposal.pk), "status": FieldProposalStatus.SUBMITTED})
    existing = FieldProposalTransition.objects.filter(organization=organization, actor=actor, to_status=FieldProposalStatus.SUBMITTED, operation_key=operation_key).first()
    if existing:
        if existing.proposal_id != proposal.pk or existing.payload_hash != payload_hash:
            raise ValidationError("کلید تکرار با داده متفاوت استفاده شده است.")
        return proposal
    if proposal.status != FieldProposalStatus.DRAFT:
        raise ValidationError("فقط پیش‌نویس پیشنهاد قابل ارسال است.")
    proposal.status = FieldProposalStatus.SUBMITTED
    proposal.submitted_by = actor
    proposal.submitted_at = timezone.now()
    proposal.proposal_hash = _sha({"proposal": str(proposal.pk), "source": proposal.source_canonical_hash, "family": proposal.family, "lines": proposal.lines})
    proposal.save()
    FieldProposalTransition.objects.create(organization=organization, proposal=proposal, from_status=FieldProposalStatus.DRAFT, to_status=FieldProposalStatus.SUBMITTED, actor=actor, proposal_hash=proposal.proposal_hash, operation_key=operation_key, payload_hash=payload_hash)
    record_audit_event(action=AuditAction.FIELD_PROPOSAL_SUBMITTED, entity_type="field_proposal", entity_id=proposal.pk, organization=organization, actor=actor, metadata={"operation_key": str(operation_key)})
    return proposal


def _get_locked_proposal(*, organization: Organization, actor: User, proposal_id: str, permission: BusinessPermissionCode) -> FieldDownstreamProposal:
    try:
        proposal = FieldDownstreamProposal.objects.select_for_update(of=("self",)).select_related("project", "site", "observation").get(pk=proposal_id, organization=organization)
    except FieldDownstreamProposal.DoesNotExist as exc:
        raise PermissionDenied("پیشنهاد در این سازمان یافت نشد.") from exc
    _permission(actor=actor, organization=organization, code=permission, project=proposal.project, site=proposal.site)
    return proposal


@transaction.atomic
def review_field_proposal(*, organization: Organization, actor: User, proposal_id: str, accepted: bool, reason: str, operation_key: uuid.UUID) -> FieldDownstreamProposal:
    proposal = _get_locked_proposal(organization=organization, actor=actor, proposal_id=proposal_id, permission=BusinessPermissionCode.FIELD_PROPOSALS_REVIEW)
    if proposal.created_by_id == actor.pk or proposal.submitted_by_id == actor.pk:
        raise PermissionDenied("تهیه‌کننده یا ارسال‌کننده نمی‌تواند پیشنهاد را بررسی کند.")
    reason = reason.strip()
    if not accepted and not reason:
        raise ValidationError("دلیل رد پیشنهاد الزامی است.")
    to_status = FieldProposalStatus.ACCEPTED if accepted else FieldProposalStatus.REJECTED
    payload_hash = _sha({"proposal": str(proposal.pk), "status": to_status, "reason": reason})
    existing = FieldProposalTransition.objects.filter(organization=organization, actor=actor, to_status=to_status, operation_key=operation_key).first()
    if existing:
        if existing.proposal_id != proposal.pk or existing.payload_hash != payload_hash:
            raise ValidationError("کلید تکرار با داده متفاوت استفاده شده است.")
        return proposal
    if proposal.status != FieldProposalStatus.SUBMITTED:
        raise ValidationError("فقط پیشنهاد ارسال‌شده قابل بررسی است.")
    proposal.status = to_status
    proposal.reviewed_by = actor
    proposal.reviewed_at = timezone.now()
    proposal.review_reason = reason
    proposal.save()
    FieldProposalTransition.objects.create(organization=organization, proposal=proposal, from_status=FieldProposalStatus.SUBMITTED, to_status=to_status, actor=actor, proposal_hash=proposal.proposal_hash, reason=reason, operation_key=operation_key, payload_hash=payload_hash)
    record_audit_event(action=AuditAction.FIELD_PROPOSAL_ACCEPTED if accepted else AuditAction.FIELD_PROPOSAL_REJECTED, entity_type="field_proposal", entity_id=proposal.pk, organization=organization, actor=actor, metadata={"operation_key": str(operation_key), "reason": reason})
    return proposal
