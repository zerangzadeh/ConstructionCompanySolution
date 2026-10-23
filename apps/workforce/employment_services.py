"""Effective source history and bounded clearance; no financial/access mutation."""

from dataclasses import dataclass
from datetime import date
from typing import Any
from zoneinfo import ZoneInfo

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.documents.employee_access import (
    get_employee_documents,
    get_employee_version_for_download,
)
from apps.documents.models import DocumentVersion
from apps.documents.services import get_organization_document
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import BusinessPermissionCode, Organization
from apps.workflows.models import WorkflowVersion, WorkItem, WorkItemStatus
from apps.workflows.runtime import start_workflow

from .ess_services import resolve_ess_subject
from .models import (
    EmploymentRecord,
    OffboardingCase,
    OffboardingReview,
    WorkRelationship,
    WorkRelationshipRevision,
)

SUBJECT = "workforce.offboarding"
DENIED = "اطلاعات مجاز در این شرکت یافت نشد."


def require(*, actor: User, organization: Organization, code: BusinessPermissionCode):
    organization = Organization.objects.get(pk=organization.pk)
    return require_business_permission(
        user=actor, organization=organization, permission=code, message=DENIED
    )


@transaction.atomic
def record_employment_version(
    *,
    actor: User,
    organization: Organization,
    relationship: WorkRelationship,
    record_key: str,
    kind: str,
    effective_from: date,
    effective_to: date | None,
    document_version: DocumentVersion,
    reason: str,
    supersedes: EmploymentRecord | None = None,
) -> EmploymentRecord:
    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    require(
        actor=actor,
        organization=organization,
        code=BusinessPermissionCode.EMPLOYMENT_RECORDS_MANAGE,
    )
    require(
        actor=actor,
        organization=organization,
        code=BusinessPermissionCode.EMPLOYEES_VIEW,
    )
    try:
        relationship = WorkRelationship.objects.select_for_update().get(
            pk=relationship.pk, organization=organization
        )
        version = (
            DocumentVersion.objects.select_for_update()
            .select_related("document")
            .get(pk=document_version.pk, organization=organization)
        )
    except (WorkRelationship.DoesNotExist, DocumentVersion.DoesNotExist) as exc:
        raise PermissionDenied(DENIED) from exc
    get_organization_document(
        user=actor, organization=organization, document_id=version.document_id
    )
    revision = (
        WorkRelationshipRevision.objects.filter(
            relationship=relationship, organization=organization
        )
        .order_by("-version")
        .first()
    )
    if revision is None or not version.is_available:
        raise ValidationError("نسخه منبع و سند ایمن لازم است.")
    previous = None
    existing = EmploymentRecord.objects.filter(
        organization=organization, relationship=relationship, record_key=record_key
    )
    if supersedes:
        try:
            previous = existing.select_for_update().get(pk=supersedes.pk)
        except EmploymentRecord.DoesNotExist as exc:
            raise PermissionDenied(DENIED) from exc
        if EmploymentRecord.objects.filter(supersedes=previous).exists():
            raise ValidationError("سابقه پیشین قبلاً جایگزین شده است.")
    elif existing.exists():
        raise ValidationError("جایگزینی سابقه باید صریح باشد.")
    return EmploymentRecord.objects.create(
        organization=organization,
        relationship=relationship,
        relationship_revision=revision,
        record_key=record_key,
        kind=kind,
        version=previous.version + 1 if previous else 1,
        effective_from=effective_from,
        effective_to=effective_to,
        document_version=version,
        document_sha256=version.sha256,
        actor=actor,
        reason=reason,
        supersedes=previous,
    )


@dataclass(frozen=True)
class OwnEmploymentRow:
    kind_label: str
    version: int
    effective_from: date
    effective_to: date | None
    status_label: str
    document_id: object
    document_version_id: object
    can_download: bool


@dataclass(frozen=True)
class OwnEmploymentHistory:
    rows: tuple[OwnEmploymentRow, ...]
    document_state: str


def own_employment_history(
    *, actor: User, organization: Organization
) -> OwnEmploymentHistory:
    organization = Organization.objects.get(pk=organization.pk)
    require(
        actor=actor,
        organization=organization,
        code=BusinessPermissionCode.EMPLOYMENT_RECORDS_VIEW_OWN,
    )
    subject = resolve_ess_subject(user=actor, organization=organization)
    # PD-WC-04: an explicit legacy Employee.user link is additionally required.
    # Person.user remains the existing ESS identity contract; neither link is inferred.
    employee = subject.current_relationship.legacy_employee
    if (
        employee is None
        or employee.organization_id != organization.pk
        or employee.user_id != actor.pk
    ):
        raise PermissionDenied(DENIED)
    try:
        access = {
            a.document.pk: a
            for a in get_employee_documents(user=actor, organization=organization)
        }
    except PermissionDenied:
        return OwnEmploymentHistory((), "unavailable")
    today = timezone.localdate(timezone=ZoneInfo(organization.settings.timezone))
    rows = []
    records = (
        EmploymentRecord.objects.filter(
            organization=organization,
            relationship__person=subject.person,
            effective_from__lte=today,
        )
        .select_related("document_version", "relationship")
        .order_by("-effective_from", "-version")
    )
    for record in records:
        permitted = access.get(record.document_version.document_id)
        if permitted is None or record.document_version_id not in {
            v.pk for v in permitted.versions
        }:
            continue
        historical = (
            EmploymentRecord.objects.filter(supersedes=record).exists()
            or (record.effective_to and record.effective_to < today)
            or record.relationship_id != subject.current_relationship.pk
        )
        if historical and not permitted.document.category.employee_history_visible:
            continue
        can_download = False
        try:
            get_employee_version_for_download(
                user=actor,
                organization=organization,
                document_id=str(permitted.document.pk),
                version_id=str(record.document_version_id),
            )
        except PermissionDenied:
            pass
        else:
            can_download = True
        rows.append(
            OwnEmploymentRow(
                record.get_kind_display(),
                record.version,
                record.effective_from,
                record.effective_to,
                "تاریخی" if historical else "مؤثر",
                permitted.document.pk,
                record.document_version_id,
                can_download,
            )
        )
    return OwnEmploymentHistory(tuple(rows), "ready" if rows else "empty")


def _source_snapshot(
    relationship: WorkRelationship, revision: WorkRelationshipRevision
) -> dict[str, Any]:
    # Only same-tenant, explicit links. Other tenant responsibilities are not inferred.
    person = relationship.person
    membership = (
        relationship.organization.memberships.filter(user_id=person.user_id).first()
        if person.user_id
        else None
    )
    return {
        "person_id": str(person.pk),
        "relationship_id": str(relationship.pk),
        "revision_id": str(revision.pk),
        "revision": revision.version,
        "effective_end": revision.effective_end.isoformat(),
        "end_actor_id": str(revision.recorded_by_id),
        "membership_id": str(membership.pk) if membership else None,
        "membership_status": membership.status if membership else None,
        "other_same_tenant_episodes": [
            str(i)
            for i in WorkRelationship.objects.filter(
                organization=relationship.organization, person=person
            )
            .exclude(pk=relationship.pk)
            .values_list("pk", flat=True)
        ],
        "other_tenant_responsibilities": "NOT_ASSESSED_NO_GLOBAL_ACCESS_ACTION",
        "informational_sources": {
            "payroll": "OWNING_DOMAIN_ONLY",
            "treasury": "OWNING_DOMAIN_ONLY",
            "equipment": "OWNING_DOMAIN_ONLY",
            "projects": "OWNING_DOMAIN_ONLY",
            "dms": "RETAINED_NO_DELETION",
            "workflow": "OWNING_WORKFLOW_ONLY",
        },
    }


@transaction.atomic
def start_offboarding(
    *,
    actor: User,
    organization: Organization,
    end_revision: WorkRelationshipRevision,
    workflow_version: WorkflowVersion,
    reason: str,
) -> OffboardingCase:
    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    require(
        actor=actor,
        organization=organization,
        code=BusinessPermissionCode.OFFBOARDING_START,
    )
    require(
        actor=actor,
        organization=organization,
        code=BusinessPermissionCode.OFFBOARDING_VIEW,
    )
    require(
        actor=actor,
        organization=organization,
        code=BusinessPermissionCode.EMPLOYEES_VIEW,
    )
    try:
        revision = (
            WorkRelationshipRevision.objects.select_for_update()
            .select_related("relationship__person", "relationship__organization")
            .get(pk=end_revision.pk, organization=organization)
        )
        workflow_version = WorkflowVersion.objects.get(
            pk=workflow_version.pk, organization=organization, status="published"
        )
    except (WorkRelationshipRevision.DoesNotExist, WorkflowVersion.DoesNotExist) as exc:
        raise PermissionDenied(DENIED) from exc
    if workflow_version.definition.scope:
        raise ValidationError("پرونده پایان همکاری در محدوده رابطه کاری شرکت است.")
    relationship = (
        WorkRelationship.objects.select_for_update()
        .select_related("person", "organization")
        .get(pk=revision.relationship_id, organization=organization)
    )
    if (
        not revision.effective_end
        or revision.effective_end != relationship.effective_end
        or revision.version
        != relationship.revisions.order_by("-version")
        .values_list("version", flat=True)
        .first()
    ):
        raise ValidationError("رویداد پایان مؤثر منبع لازم است؛ تسویه مجوز پایان نیست.")
    old = OffboardingCase.objects.filter(end_revision=revision).first()
    if old:
        if old.workflow_version_id != workflow_version.pk or old.reason != reason:
            raise ValidationError("پرونده موجود با ورودی متفاوت سازگار نیست.")
        return get_case(actor=actor, organization=organization, case_id=old.pk)
    case = OffboardingCase.objects.create(
        organization=organization,
        end_revision=revision,
        workflow_version=workflow_version,
        initiated_by=actor,
        reason=reason,
        source_snapshot=_source_snapshot(relationship, revision),
    )
    instance = start_workflow(
        actor=actor,
        organization=organization,
        version_id=workflow_version.pk,
        subject_id=case.pk,
        idempotency_key=f"offboarding:{case.pk}",
    )
    usable = False
    for item in instance.work_items.filter(
        status__in=[WorkItemStatus.OPEN, WorkItemStatus.CLAIMED]
    ):
        for candidate in item.candidates.filter(is_active=True).select_related(
            "membership__user"
        ):
            try:
                for code in (
                    BusinessPermissionCode.OFFBOARDING_VIEW,
                    BusinessPermissionCode.OFFBOARDING_REVIEW,
                    BusinessPermissionCode.WORK_ITEMS_VIEW,
                    BusinessPermissionCode.WORK_ITEMS_CLAIM,
                    BusinessPermissionCode.WORK_ITEMS_ACT,
                ):
                    require(
                        actor=candidate.membership.user,
                        organization=organization,
                        code=code,
                    )
            except PermissionDenied:
                continue
            usable = True
    if instance.status != "active" or not usable:
        raise ValidationError("مسیر بررسی تخصیص‌یافته مجاز موجود نیست.")
    return case


def get_case(
    *, actor: User, organization: Organization, case_id: object
) -> OffboardingCase:
    member = require(
        actor=actor,
        organization=organization,
        code=BusinessPermissionCode.OFFBOARDING_VIEW,
    )
    try:
        case = OffboardingCase.objects.select_related(
            "end_revision__relationship__person"
        ).get(pk=case_id, organization=organization)
    except OffboardingCase.DoesNotExist as exc:
        raise PermissionDenied(DENIED) from exc
    if (
        case.initiated_by_id != actor.pk
        and not WorkItem.objects.filter(
            organization=organization,
            instance__subject_type=SUBJECT,
            instance__subject_id=case.pk,
        )
        .filter(
            Q(current_assignee=member)
            | Q(candidates__membership=member, candidates__is_active=True)
        )
        .exists()
    ):
        raise PermissionDenied(DENIED)
    return case


def requester_status(
    *, actor: User, organization: Organization, case_id: object
) -> dict[str, str]:
    case = get_case(actor=actor, organization=organization, case_id=case_id)
    # Private review notes, access assessment/actions and reviewer identity never escape.
    return {
        "case_id": str(case.pk),
        "status": case.status,
        "employment_end": case.end_revision.effective_end.isoformat(),
    }


@transaction.atomic
def complete_clearance(
    *,
    subject: OffboardingCase,
    actor: User,
    organization: Organization,
    work_item: WorkItem,
    context: dict[str, Any],
    **kwargs: Any,
) -> None:
    del kwargs
    member = require(
        actor=actor,
        organization=organization,
        code=BusinessPermissionCode.OFFBOARDING_REVIEW,
    )
    work_item = (
        WorkItem.objects.select_for_update()
        .select_related("instance")
        .get(pk=work_item.pk, organization=organization)
    )
    case = (
        OffboardingCase.objects.select_for_update()
        .select_related(
            "end_revision__relationship__person",
            "end_revision__relationship__organization",
        )
        .get(pk=subject.pk, organization=organization)
    )
    if (
        work_item.organization_id != organization.pk
        or work_item.status != WorkItemStatus.CLAIMED
        or work_item.current_assignee_id != member.pk
        or work_item.instance.subject_id != case.pk
        or work_item.instance.subject_type != SUBJECT
    ):
        raise PermissionDenied(DENIED)
    if OffboardingReview.objects.filter(case=case).exists():
        raise ValidationError("بررسی قبلاً ثبت شده است.")
    allowed = {"workforce_evidence", "access_assessment", "access_action_audit_id"}
    if set(context) - allowed or any(
        not isinstance(context.get(k), str) or not context[k].strip()
        for k in ("workforce_evidence", "access_assessment")
    ):
        raise ValidationError(
            "هر دو نتیجه ضروری صریح لازم است؛ بررسی اطلاعاتی مانع نیست."
        )
    action = None
    relationship = case.end_revision.relationship
    snapshot = _source_snapshot(relationship, case.end_revision)
    if context.get("access_action_audit_id"):
        try:
            action = AuditEvent.objects.get(
                pk=context["access_action_audit_id"],
                organization=organization,
                entity_id=snapshot["membership_id"],
                action__in=[
                    AuditAction.MEMBERSHIP_STATUS_CHANGED,
                    AuditAction.MEMBERSHIP_ROLE_REVOKED,
                    AuditAction.MEMBERSHIP_SCOPE_REVOKED,
                ],
            )
        except (AuditEvent.DoesNotExist, ValueError) as exc:
            raise ValidationError(
                "مرجع اقدام دسترسی باید از اختیار همان منبع باشد."
            ) from exc
    OffboardingReview.objects.create(
        organization=organization,
        case=case,
        work_item=work_item,
        actor=actor,
        workforce_evidence=context["workforce_evidence"].strip(),
        access_assessment=context["access_assessment"].strip(),
        access_action_audit=action,
        source_snapshot=snapshot,
    )
