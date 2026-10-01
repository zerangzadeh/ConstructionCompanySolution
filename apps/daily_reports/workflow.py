"""W5.1 orchestration for the existing daily-report lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.authorization import (
    get_active_membership,
    membership_has_permission,
    require_business_permission,
)
from apps.organizations.models import (
    BusinessPermissionCode,
    MembershipStatus,
    Organization,
    OrganizationMembership,
)
from apps.workflows.models import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkflowRoutingRule,
    WorkflowStepDefinition,
    WorkflowTemplate,
    WorkflowTransitionDefinition,
    WorkflowType,
    WorkflowVersion,
    WorkflowVersionStatus,
    WorkItem,
    WorkItemCandidate,
    WorkItemStatus,
    canonical_scope,
)
from apps.workflows.registry import SubjectSnapshot, registry
from apps.workflows.runtime import (
    WorkflowConflict,
    claim_work_item,
    complete_work_item,
    start_workflow,
)
from apps.workflows.validators import validate_workflow_version

from .models import DailyReport, DailyReportStatus

WORKFLOW_TYPE_CODE = "daily_reports.daily_report_approval"
SUBJECT_TYPE = "daily_reports.daily_report"
COMPATIBILITY_TEMPLATE_CODE = "daily_report_legacy_compatibility"
COMPATIBILITY_DEFINITION_CODE = "daily-report-legacy-compatibility"
COMPATIBILITY_TEMPLATE_NAME = "سازگاری تأیید گزارش روزانه"
COMPATIBILITY_TEMPLATE_DESCRIPTION = (
    "رفتار draft → submitted → approved موجود را حفظ می‌کند."
)

COMPATIBILITY_CONFIGURATION: dict[str, Any] = {
    "steps": [
        {"key": "start", "name": "شروع", "step_type": "start", "is_start": True},
        {
            "key": "legacy_approval",
            "name": "تأیید گزارش روزانه",
            "step_type": "approval",
            "configuration": {"decision_policy": "any"},
            "routing": [
                {
                    "resolver_type": "business_permission",
                    "configuration": {"permission": "daily_reports.approve"},
                },
            ],
        },
        {
            "key": "approved",
            "name": "تأییدشده",
            "step_type": "end",
            "is_terminal": True,
        },
    ],
    "transitions": [
        {
            "source": "start",
            "target": "legacy_approval",
            "outcome": "submitted",
            "is_default": True,
        },
        {
            "source": "legacy_approval",
            "target": "approved",
            "outcome": "approved",
            "domain_command": "daily_reports.daily_report.approve",
            "required_permission": "daily_reports.approve",
        },
    ],
}


def _key(*parts: object) -> str:
    return sha256(":".join(str(part) for part in parts).encode()).hexdigest()


def _has_legacy_approver(organization: Organization) -> bool:
    return OrganizationMembership.objects.filter(
        organization=organization,
        status=MembershipStatus.ACTIVE,
        role_definition__is_active=True,
        user__is_active=True,
        role_definition__permissions__code=str(
            BusinessPermissionCode.DAILY_REPORTS_APPROVE
        ),
        role_definition__permissions__is_active=True,
    ).exists()


def _active_membership_id(organization: Organization, user_id: object) -> str | None:
    if not user_id:
        return None
    value = (
        OrganizationMembership.objects.filter(
            organization=organization,
            user_id=user_id,
            status=MembershipStatus.ACTIVE,
            role_definition__is_active=True,
            user__is_active=True,
        )
        .values_list("pk", flat=True)
        .first()
    )
    return str(value) if value else None


def load_daily_report_subject(
    *, organization: Organization, subject_id: UUID, actor: User, for_update: bool
) -> SubjectSnapshot:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.DAILY_REPORTS_VIEW,
        message="اجازه مشاهده این گزارش روزانه را ندارید.",
    )
    queryset = DailyReport.objects.select_related("project", "site")
    if for_update:
        queryset = queryset.select_for_update(of=("self",))
    try:
        report = queryset.get(pk=subject_id, organization=organization)
    except DailyReport.DoesNotExist as exc:
        raise PermissionDenied("گزارش روزانه در این سازمان یافت نشد.") from exc
    if (
        report.project.organization_id != organization.pk
        or report.site.organization_id != organization.pk
        or report.site.project_id != report.project_id
    ):
        raise PermissionDenied("دامنه گزارش روزانه نامعتبر است.")
    return SubjectSnapshot(
        subject=report,
        subject_id=str(report.pk),
        organization_id=str(organization.pk),
        attributes={
            "project_id": str(report.project_id),
            "site_id": str(report.site_id),
            "status": report.status,
            "created_by_id": str(report.created_by_id),
        },
        creator_membership_id=_active_membership_id(organization, report.created_by_id),
        submitter_membership_id=_active_membership_id(
            organization, report.updated_by_id
        ),
        display=f"{report.site} — {report.reporting_date}",
    )


def _submit_command(
    *, subject: DailyReport, actor: User, organization: Organization, **_: object
) -> DailyReport:
    from .services import _submit_daily_report_domain

    return _submit_daily_report_domain(
        organization=organization, report_id=str(subject.pk), actor=actor
    )


def _approve_command(
    *, subject: DailyReport, actor: User, organization: Organization, **_: object
) -> DailyReport:
    from .services import _approve_daily_report_domain

    return _approve_daily_report_domain(
        organization=organization, report_id=str(subject.pk), actor=actor
    )


def register_daily_report_workflow() -> None:
    registry.bind_subject_loader(SUBJECT_TYPE, load_daily_report_subject)
    registry.bind_domain_command("daily_reports.daily_report.submit", _submit_command)
    registry.bind_domain_command("daily_reports.daily_report.approve", _approve_command)


def _write_configuration(
    *,
    organization: Organization,
    version: WorkflowVersion,
    configuration: dict[str, Any],
) -> None:
    steps: dict[str, WorkflowStepDefinition] = {}
    for item in configuration["steps"]:
        step = WorkflowStepDefinition.objects.create(
            organization=organization,
            version=version,
            key=item["key"],
            name=item.get("name", item["key"]),
            step_type=item["step_type"],
            is_start=item.get("is_start", False),
            is_terminal=item.get("is_terminal", False),
            configuration=item.get("configuration", {}),
        )
        steps[step.key] = step
        for order, route in enumerate(item.get("routing", [])):
            WorkflowRoutingRule.objects.create(
                organization=organization,
                version=version,
                step=step,
                resolver_type=route["resolver_type"],
                configuration=route.get("configuration", {}),
                order=order,
                is_fallback=route.get("is_fallback", False),
            )
    for item in configuration["transitions"]:
        WorkflowTransitionDefinition.objects.create(
            organization=organization,
            version=version,
            source_step=steps[item["source"]],
            target_step=steps[item["target"]],
            outcome=item["outcome"],
            domain_command=item.get("domain_command", ""),
            required_permission=item.get("required_permission", ""),
            is_default=item.get("is_default", False),
        )


def _ensure_daily_report_platform_catalog() -> tuple[WorkflowType, WorkflowTemplate]:
    """Restore the code-owned compatibility template when it is absent."""

    workflow_type = WorkflowType.objects.get(code=WORKFLOW_TYPE_CODE, is_active=True)
    template, _ = WorkflowTemplate.objects.get_or_create(
        workflow_type=workflow_type,
        code=COMPATIBILITY_TEMPLATE_CODE,
        defaults={
            "name": COMPATIBILITY_TEMPLATE_NAME,
            "description": COMPATIBILITY_TEMPLATE_DESCRIPTION,
            "configuration": COMPATIBILITY_CONFIGURATION,
            "is_active": True,
        },
    )
    if not template.is_active:
        raise ValidationError("قالب سازگاری گزارش روزانه غیرفعال است.")
    return workflow_type, template


@transaction.atomic
def ensure_daily_report_compatibility_workflow(
    *, organization: Organization, actor: User
) -> WorkflowVersion:
    """Create a published, tenant-owned compatibility version when absent."""
    get_active_membership(user=actor, organization=organization)
    locked_organization = Organization.objects.select_for_update().get(
        pk=organization.pk
    )
    workflow_type, template = _ensure_daily_report_platform_catalog()
    _, scope_key = canonical_scope({})
    existing = (
        WorkflowVersion.objects.select_related("definition")
        .filter(
            organization=locked_organization,
            definition__workflow_type=workflow_type,
            definition__scope_key=scope_key,
            status=WorkflowVersionStatus.PUBLISHED,
        )
        .first()
    )
    if existing:
        if validate_workflow_version(existing):
            raise ValidationError("گردش‌کار پیش‌فرض گزارش روزانه معتبر نیست.")
        return existing
    definition, created = WorkflowDefinition.objects.get_or_create(
        organization=locked_organization,
        workflow_type=workflow_type,
        scope_key=scope_key,
        defaults={
            "code": COMPATIBILITY_DEFINITION_CODE,
            "name": "سازگاری تأیید گزارش روزانه",
            "description": "رفتار تک‌مرحله‌ای فعلی گزارش روزانه را حفظ می‌کند.",
            "scope": {},
            "created_by": actor,
            "updated_by": actor,
        },
    )
    if not created:
        raise ValidationError("تعریف پیش‌فرض گزارش روزانه نسخه منتشرشده ندارد.")
    version = WorkflowVersion.objects.create(
        organization=locked_organization,
        definition=definition,
        version_number=1,
        change_summary="W5.1 legacy compatibility",
    )
    _write_configuration(
        organization=locked_organization,
        version=version,
        configuration=template.configuration,
    )
    issues = validate_workflow_version(version)
    if issues:
        raise ValidationError([issue.message for issue in issues])
    now = timezone.now()
    models.QuerySet.update(
        WorkflowVersion.objects.filter(pk=version.pk),
        status=WorkflowVersionStatus.PUBLISHED,
        validation_report=[],
        validated_at=now,
        validated_by=actor,
        published_at=now,
        published_by=actor,
        updated_at=now,
    )
    record_audit_event(
        action=AuditAction.WORKFLOW_DEFINITION_CREATED,
        entity_type="workflows.WorkflowDefinition",
        entity_id=str(definition.pk),
        organization=locked_organization,
        actor=actor,
        metadata={"workflow_type": WORKFLOW_TYPE_CODE, "compatibility": True},
    )
    record_audit_event(
        action=AuditAction.WORKFLOW_VERSION_PUBLISHED,
        entity_type="workflows.WorkflowVersion",
        entity_id=str(version.pk),
        organization=locked_organization,
        actor=actor,
        metadata={"version": 1, "compatibility": True},
    )
    version.refresh_from_db()
    return version


def resolve_daily_report_workflow_version(
    *, organization: Organization, report: DailyReport
) -> WorkflowVersion:
    if report.organization_id != organization.pk:
        raise PermissionDenied("گزارش روزانه متعلق به سازمان دیگری است.")
    context = {"project_id": str(report.project_id), "site_id": str(report.site_id)}
    matches: list[tuple[int, WorkflowVersion]] = []
    versions = WorkflowVersion.objects.select_related("definition").filter(
        organization=organization,
        definition__workflow_type__code=WORKFLOW_TYPE_CODE,
        status=WorkflowVersionStatus.PUBLISHED,
    )
    for version in versions:
        if all(
            context.get(key) == value for key, value in version.definition.scope.items()
        ):
            matches.append((len(version.definition.scope), version))
    if not matches:
        raise ValidationError("نسخه منتشرشده برای گزارش روزانه یافت نشد.")
    specificity = max(score for score, _ in matches)
    selected = [version for score, version in matches if score == specificity]
    if len(selected) != 1:
        raise ValidationError("انتخاب نسخه گردش‌کار گزارش روزانه مبهم است.")
    return selected[0]


@transaction.atomic
def submit_daily_report_with_workflow(
    *, organization: Organization, report_id: str, actor: User
) -> DailyReport:
    from .services import _submit_daily_report_domain

    if not _has_legacy_approver(organization):
        # A legacy tenant may temporarily have no active approver. Keep its open
        # report in the domain until routing becomes actionable for backfill.
        return _submit_daily_report_domain(
            organization=organization, report_id=report_id, actor=actor
        )
    ensure_daily_report_compatibility_workflow(organization=organization, actor=actor)
    try:
        report = DailyReport.objects.get(pk=report_id, organization=organization)
    except DailyReport.DoesNotExist as exc:
        raise PermissionDenied("گزارش روزانه در این سازمان یافت نشد.") from exc
    version = resolve_daily_report_workflow_version(
        organization=organization, report=report
    )
    report = _submit_daily_report_domain(
        organization=organization, report_id=report_id, actor=actor
    )
    instance = start_workflow(
        actor=actor,
        organization=organization,
        version_id=version.pk,
        subject_id=report.pk,
        idempotency_key=_key(WORKFLOW_TYPE_CODE, report.pk, "start"),
    )
    if (
        instance.status != WorkflowInstanceStatus.ACTIVE
        or not instance.work_items.filter(
            status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED)
        ).exists()
    ):
        raise WorkflowConflict("ارسال گزارش روزانه بدون کار فعال قابل ثبت نیست.")
    return report


def _actor_item(
    *,
    organization: Organization,
    report: DailyReport,
    membership: OrganizationMembership,
) -> WorkItem:
    item = (
        WorkItem.objects.select_related("instance", "current_assignee")
        .filter(
            organization=organization,
            instance__subject_type=SUBJECT_TYPE,
            instance__subject_id=report.pk,
            instance__status=WorkflowInstanceStatus.ACTIVE,
            status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED),
            candidates__membership=membership,
            candidates__is_active=True,
        )
        .distinct()
        .first()
    )
    if item is None:
        raise PermissionDenied("کار فعال و نامزدی معتبر برای تأیید گزارش وجود ندارد.")
    return item


@transaction.atomic
def approve_daily_report_with_workflow(
    *, organization: Organization, report_id: str, actor: User
) -> DailyReport:
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.DAILY_REPORTS_APPROVE,
        message="اجازه تأیید گزارش‌های روزانه این سازمان را ندارید.",
    ) or get_active_membership(user=actor, organization=organization)
    try:
        report = DailyReport.objects.get(pk=report_id, organization=organization)
    except DailyReport.DoesNotExist as exc:
        raise PermissionDenied("گزارش روزانه در این سازمان یافت نشد.") from exc
    if report.status != DailyReportStatus.SUBMITTED:
        raise ValueError("فقط گزارش‌های روزانه ارسال‌شده قابل تأیید هستند.")
    instance_exists = WorkflowInstance.objects.filter(
        organization=organization,
        subject_type=SUBJECT_TYPE,
        subject_id=report.pk,
    ).exists()
    if not instance_exists:
        starter = _backfill_actor(report)
        if starter is None:
            raise WorkflowConflict("عضویت مجاز برای انتقال گزارش باز یافت نشد.")
        ensure_daily_report_compatibility_workflow(
            organization=organization, actor=starter
        )
    report = DailyReport.objects.select_for_update().get(
        pk=report.pk, organization=organization
    )
    if report.status != DailyReportStatus.SUBMITTED:
        raise ValueError("فقط گزارش‌های روزانه ارسال‌شده قابل تأیید هستند.")
    if (
        not instance_exists
        and not WorkflowInstance.objects.filter(
            organization=organization,
            subject_type=SUBJECT_TYPE,
            subject_id=report.pk,
        ).exists()
    ):
        _backfill_one(report=report, actor=starter)
    item = _actor_item(organization=organization, report=report, membership=membership)
    if item.status == WorkItemStatus.OPEN:
        item = claim_work_item(
            actor=actor,
            organization=organization,
            work_item_id=item.pk,
            idempotency_key=_key(item.pk, membership.pk, "claim"),
        )
    elif item.current_assignee_id != membership.pk:
        raise PermissionDenied("کار به عضویت دیگری تخصیص یافته است.")
    complete_work_item(
        actor=actor,
        organization=organization,
        work_item_id=item.pk,
        outcome="approved",
        idempotency_key=_key(item.pk, membership.pk, "approved"),
    )
    report.refresh_from_db()
    return report


@dataclass(frozen=True, slots=True)
class BackfillReport:
    scanned: int = 0
    created: int = 0
    existing: int = 0
    skipped: int = 0


def _backfill_actor(report: DailyReport) -> User | None:
    memberships = OrganizationMembership.objects.filter(
        organization=report.organization,
        status=MembershipStatus.ACTIVE,
        role_definition__is_active=True,
        user__is_active=True,
    ).select_related("user", "role_definition")
    preferred = memberships.filter(user_id=report.updated_by_id).first()
    required = (
        BusinessPermissionCode.DAILY_REPORTS_SUBMIT,
        BusinessPermissionCode.DAILY_REPORTS_VIEW,
    )
    if preferred and all(
        membership_has_permission(preferred, code) for code in required
    ):
        return preferred.user
    for membership in memberships.filter(role_definition__is_owner=True):
        if all(membership_has_permission(membership, code) for code in required):
            return membership.user
    return None


def backfill_submitted_daily_reports(
    *, organization: Organization | None = None
) -> BackfillReport:
    queryset = DailyReport.objects.filter(
        status=DailyReportStatus.SUBMITTED,
        project__deleted_at__isnull=True,
        site__is_active=True,
        project__organization_id=models.F("organization_id"),
        site__organization_id=models.F("organization_id"),
        site__project_id=models.F("project_id"),
    )
    if organization is not None:
        queryset = queryset.filter(organization=organization)
    scanned = created = existing = skipped = 0
    for report in queryset.select_related("organization", "updated_by").iterator():
        scanned += 1
        if not _has_legacy_approver(report.organization):
            skipped += 1
            continue
        actor = _backfill_actor(report)
        if actor is None:
            skipped += 1
            continue
        ensure_daily_report_compatibility_workflow(
            organization=report.organization, actor=actor
        )
        result = _backfill_one(report=report, actor=actor)
        if result == "existing":
            existing += 1
        elif result == "created":
            created += 1
        else:
            skipped += 1
    return BackfillReport(
        scanned=scanned, created=created, existing=existing, skipped=skipped
    )


@transaction.atomic
def _backfill_one(*, report: DailyReport, actor: User) -> str:
    try:
        locked = DailyReport.objects.select_for_update().get(
            pk=report.pk, organization=report.organization
        )
    except DailyReport.DoesNotExist:
        return "skipped"
    if locked.status != DailyReportStatus.SUBMITTED:
        return "skipped"
    was_present = WorkflowInstance.objects.filter(
        organization=report.organization,
        subject_type=SUBJECT_TYPE,
        subject_id=locked.pk,
    ).exists()
    version = resolve_daily_report_workflow_version(
        organization=report.organization, report=locked
    )
    start_workflow(
        actor=actor,
        organization=report.organization,
        version_id=version.pk,
        subject_id=locked.pk,
        idempotency_key=_key(WORKFLOW_TYPE_CODE, locked.pk, "start"),
    )
    return "existing" if was_present else "created"


def daily_report_shadow_comparison(
    *, organization: Organization, report: DailyReport
) -> dict[str, Any]:
    if report.organization_id != organization.pk:
        raise PermissionDenied("گزارش روزانه متعلق به سازمان دیگری است.")
    legacy_ids = {
        str(value)
        for value in OrganizationMembership.objects.filter(
            organization=organization,
            status=MembershipStatus.ACTIVE,
            role_definition__is_active=True,
            user__is_active=True,
            role_definition__permissions__code=str(
                BusinessPermissionCode.DAILY_REPORTS_APPROVE
            ),
            role_definition__permissions__is_active=True,
        ).values_list("pk", flat=True)
    }
    candidates = WorkItemCandidate.objects.filter(
        organization=organization,
        work_item__instance__subject_type=SUBJECT_TYPE,
        work_item__instance__subject_id=report.pk,
        work_item__status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED),
        is_active=True,
    ).select_related("membership__role_definition")
    workflow_ids = {str(item.membership_id) for item in candidates}
    required_runtime_permissions = (
        BusinessPermissionCode.WORK_ITEMS_VIEW,
        BusinessPermissionCode.WORK_ITEMS_CLAIM,
        BusinessPermissionCode.WORK_ITEMS_ACT,
    )
    blocked_ids = sorted(
        {
            str(item.membership_id)
            for item in candidates
            if not all(
                membership_has_permission(item.membership, code)
                for code in required_runtime_permissions
            )
        }
    )
    missing = sorted(legacy_ids - workflow_ids)
    unexpected = sorted(workflow_ids - legacy_ids)
    return {
        "daily_report_id": str(report.pk),
        "legacy_membership_ids": sorted(legacy_ids),
        "workflow_membership_ids": sorted(workflow_ids),
        "missing_membership_ids": missing,
        "unexpected_membership_ids": unexpected,
        "blocked_runtime_permission_membership_ids": blocked_ids,
        "mismatch": bool(missing or unexpected or blocked_ids),
    }
