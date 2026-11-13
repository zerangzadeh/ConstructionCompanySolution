"""Reasoned Return, versioned submission and governed legacy adoption."""

from __future__ import annotations

from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.organizations.authorization import (
    get_active_membership,
    has_business_permission,
)
from apps.organizations.models import BusinessPermissionCode as P
from apps.organizations.models import Organization, OrganizationMembership
from apps.workflows.models import (
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkflowVersion,
    WorkItem,
    WorkItemCandidate,
    WorkItemStatus,
)
from apps.workflows.runtime import (
    WorkflowConflict,
    claim_work_item,
    complete_work_item,
    migrate_workflow_instance,
    start_workflow,
)
from apps.workflows.services import supersede_workflow_version
from core.product_surface import surface_profile

from .models import DailyReport, DailyReportStatus
from .return_configuration import RETURN_COMMAND
from .revision_services import (
    lock_report,
    receipt,
    require_author,
    require_correction_draft,
    scoped_permission,
    validate_correction,
    write_receipt,
)
from .services import _can_update_daily_report
from .submission_snapshots import seal_submission, verify_submission
from .workflow import (
    COMPATIBILITY_CONFIGURATION,
    COMPATIBILITY_DEFINITION_CODE,
    RETURN_CONFIGURATION,
    SUBJECT_TYPE,
    WORKFLOW_TYPE_CODE,
    _actor_item,
    _key,
    _write_configuration,
    ensure_daily_report_compatibility_workflow,
    resolve_daily_report_workflow_version,
)

APPROVE_COMMAND = "daily_reports.daily_report.approve"
REVIEW_STEP = "legacy_approval"
OPEN_ITEMS = (WorkItemStatus.OPEN, WorkItemStatus.CLAIMED)
LIVE_INSTANCES = (WorkflowInstanceStatus.ACTIVE, WorkflowInstanceStatus.SUSPENDED)


def _legacy_configuration_matches(version):
    """Automatic publication is bounded to the original code-owned template."""
    if version.steps.count() != len(COMPATIBILITY_CONFIGURATION["steps"]):
        return False
    for expected in COMPATIBILITY_CONFIGURATION["steps"]:
        step = version.steps.filter(
            key=expected["key"],
            name=expected["name"],
            step_type=expected["step_type"],
            is_start=expected.get("is_start", False),
            is_terminal=expected.get("is_terminal", False),
            configuration=expected.get("configuration", {}),
            domain_command="",
            required_permission="",
        ).first()
        if step is None or step.routing_rules.count() != len(
            expected.get("routing", [])
        ):
            return False
        for order, rule in enumerate(expected.get("routing", [])):
            if not step.routing_rules.filter(
                resolver_type=rule["resolver_type"],
                configuration=rule["configuration"],
                order=order,
                is_fallback=False,
            ).exists():
                return False
    if version.transitions.count() != len(COMPATIBILITY_CONFIGURATION["transitions"]):
        return False
    for expected in COMPATIBILITY_CONFIGURATION["transitions"]:
        transition = version.transitions.filter(
            source_step__key=expected["source"],
            target_step__key=expected["target"],
            outcome=expected["outcome"],
            is_default=expected.get("is_default", False),
            domain_command=expected.get("domain_command", ""),
            required_permission=expected.get("required_permission", ""),
            priority=0,
        ).first()
        if transition is None or transition.conditions.exists():
            return False
    return True


def _reason(value):
    value = value.strip()
    if not 1 <= len(value) <= 1000:
        raise ValidationError("دلیل باید بین ۱ تا ۱۰۰۰ نویسه باشد.")
    return value


def _instances(report):
    return WorkflowInstance.objects.filter(
        organization_id=report.organization_id,
        subject_type=SUBJECT_TYPE,
        subject_id=report.pk,
    )


def _compatible(version):
    review = version.steps.filter(key=REVIEW_STEP, step_type="approval").first()
    if not review or not all(
        review.configuration.get(key)
        for key in ("exclude_creator", "exclude_submitter")
    ):
        return False
    if review.configuration.get("decision_policy") != "any":
        return False
    for outcome, command in (
        ("approved", APPROVE_COMMAND),
        ("returned", RETURN_COMMAND),
    ):
        if not version.transitions.filter(
            source_step=review,
            outcome=outcome,
            domain_command=command,
            target_step__is_terminal=True,
            required_permission=P.DAILY_REPORTS_APPROVE,
        ).exists():
            return False
    return version.transitions.filter(
        source_step__is_start=True,
        target_step=review,
        conditions__condition_type="subject_attribute_equals",
        conditions__configuration={"attribute": "return_enabled", "value": True},
    ).exists()


def _return_version(report):
    version = resolve_daily_report_workflow_version(
        organization=report.organization, report=report
    )
    if not _compatible(version):
        raise WorkflowConflict("نسخه منتشرشده گردش‌کار از بازگشت گزارش پشتیبانی نمی‌کند.")
    return version


def _assert_actionable(report, instance):
    if instance.status != WorkflowInstanceStatus.ACTIVE:
        raise WorkflowConflict("بررسی مستقل برای این نسخه فعال نشد.")
    candidates = WorkItemCandidate.objects.filter(
        work_item__instance=instance,
        work_item__status__in=OPEN_ITEMS,
        work_item__step_instance__step_definition__key=REVIEW_STEP,
        is_active=True,
    ).values_list("membership__user_id", flat=True)
    from apps.accounts.models import User

    independent = User.objects.filter(pk__in=candidates).exclude(
        pk__in=(
            report.submission_snapshot["author_id"],
            report.submission_snapshot["submitter_id"],
        )
    )
    if not any(
        all(
            has_business_permission(
                user=user,
                organization=report.organization,
                permission=permission,
                project=report.project,
                site=report.site,
            )
            for permission in (
                P.DAILY_REPORTS_VIEW,
                P.DAILY_REPORTS_APPROVE,
                P.WORK_ITEMS_CLAIM,
                P.WORK_ITEMS_ACT,
            )
        )
        for user in independent
    ):
        raise WorkflowConflict("بازبین مستقل و مجاز برای این نسخه یافت نشد.")


def _start_review(report, actor, version):
    if _instances(report).filter(status__in=LIVE_INSTANCES).exists():
        raise WorkflowConflict("این نسخه گردش‌کار باز دارد.")
    instance = start_workflow(
        actor=actor,
        organization=report.organization,
        version_id=version.pk,
        subject_id=report.pk,
        idempotency_key=_key(WORKFLOW_TYPE_CODE, report.pk, "start"),
    )
    _assert_actionable(report, instance)
    return instance


def _seal_and_start(
    report, actor, membership, version, *, operation_key=None, payload=None
):
    validate_correction(report)
    creator = get_active_membership(
        user=report.created_by, organization=report.organization
    )
    report.status = DailyReportStatus.SUBMITTED
    report.submitted_at = timezone.now()
    report.updated_by = actor
    seal_submission(
        report, submitter=actor, membership=membership, creator_membership=creator
    )
    report.save(
        update_fields=[
            "status",
            "submitted_at",
            "updated_by",
            "updated_at",
            "submission_snapshot",
            "submission_hash",
        ]
    )
    instance = _start_review(report, actor, version)
    write_receipt(
        report,
        actor,
        operation_key,
        AuditAction.DAILY_REPORT_SUBMITTED,
        payload or {},
        before="draft",
        after="submitted",
        instance_id=str(instance.pk),
        workflow_version_id=str(version.pk),
        predecessor_id=str(report.previous_revision_id)
        if report.previous_revision_id
        else None,
    )
    return report


def submit_returnable(
    *, organization: Organization, actor: User, report_id: UUID | str
) -> DailyReport:
    # The factory runs before locking the report, and does not supersede configured versions.
    preliminary = (
        DailyReport.objects.select_related("organization", "project", "site")
        .filter(
            organization=organization,
            pk=report_id,
        )
        .first()
    )
    if preliminary is None:
        raise PermissionDenied("گزارش روزانه در این شرکت یافت نشد.")
    scoped_permission(preliminary, actor, P.DAILY_REPORTS_SUBMIT)
    scoped_permission(preliminary, actor, P.DAILY_REPORTS_VIEW)
    if preliminary.previous_revision_id:
        raise PermissionDenied("ارسال نسخه اصلاحی فقط از فرم اصلاح گزارش مجاز است.")
    if not preliminary.created_by_id or not _can_update_daily_report(
        organization=preliminary.organization,
        report=preliminary,
        actor=actor,
        permission=P.DAILY_REPORTS_SUBMIT,
    ):
        raise PermissionDenied("اجازه ارسال این گزارش روزانه را ندارید.")
    if preliminary.status != DailyReportStatus.DRAFT:
        raise WorkflowConflict("فقط گزارش پیش‌نویس اولیه قابل ارسال است.")
    ensure_daily_report_compatibility_workflow(
        organization=preliminary.organization, actor=actor
    )
    with transaction.atomic():
        report = lock_report(organization, report_id)
        if report.previous_revision_id or report.status != DailyReportStatus.DRAFT:
            raise WorkflowConflict("فقط گزارش پیش‌نویس اولیه قابل ارسال است.")
        membership = scoped_permission(report, actor, P.DAILY_REPORTS_SUBMIT)
        if not report.created_by_id or not _can_update_daily_report(
            organization=report.organization,
            report=report,
            actor=actor,
            permission=P.DAILY_REPORTS_SUBMIT,
        ):
            raise PermissionDenied("اجازه ارسال این گزارش روزانه را ندارید.")
        return _seal_and_start(report, actor, membership, _return_version(report))


@transaction.atomic
def resubmit_correction(
    *,
    organization: Organization,
    actor: User,
    report_id: UUID | str,
    operation_key: UUID,
    expected_version: int,
) -> DailyReport:
    report = lock_report(organization, report_id)
    require_author(report, actor, lock=True)
    membership = scoped_permission(report, actor, P.DAILY_REPORTS_SUBMIT)
    payload = {"action": "resubmit", "edit_version": expected_version}
    if receipt(
        report, actor, operation_key, AuditAction.DAILY_REPORT_SUBMITTED, payload
    ):
        return report
    require_correction_draft(report, expected_version)
    version = _return_version(report)
    return _seal_and_start(
        report, actor, membership, version, operation_key=operation_key, payload=payload
    )


def require_independent_reviewer(
    report: DailyReport, actor: User
) -> OrganizationMembership:
    verify_submission(report)
    if str(actor.pk) in (
        report.submission_snapshot["author_id"],
        report.submission_snapshot["submitter_id"],
    ):
        raise PermissionDenied("نویسنده یا ارسال‌کننده نمی‌تواند گزارش خود را بررسی کند.")
    return scoped_permission(report, actor, P.DAILY_REPORTS_APPROVE)


def require_review_item(
    report: DailyReport,
    membership: OrganizationMembership,
    work_item: WorkItem | None,
) -> WorkItem:
    if work_item is None or report.status != DailyReportStatus.SUBMITTED:
        raise PermissionDenied("کار بررسی فعال به این نسخه تعلق ندارد.")
    current = (
        WorkItem.objects.select_for_update(of=("self",))
        .select_related("instance")
        .filter(
            pk=work_item.pk,
            organization_id=report.organization_id,
            instance__subject_type=SUBJECT_TYPE,
            instance__subject_id=report.pk,
            instance__status=WorkflowInstanceStatus.ACTIVE,
            step_instance__status="active",
            step_instance__step_definition__key=REVIEW_STEP,
            status=WorkItemStatus.CLAIMED,
            current_assignee=membership,
            candidates__is_active=True,
            candidates__membership=membership,
        )
        .first()
    )
    if current is None:
        raise PermissionDenied("کار بررسی فعال به این نسخه تعلق ندارد.")
    return current


def return_command(
    *, subject, actor, organization, outcome, context, idempotency_key, work_item
):
    report = lock_report(organization, subject.pk)
    membership = require_independent_reviewer(report, actor)
    work_item = require_review_item(report, membership, work_item)
    if outcome != "returned":
        raise WorkflowConflict("نتیجه بازگشت معتبر نیست.")
    reason = _reason(context.get("reason", ""))
    report.status = DailyReportStatus.RETURNED
    report.updated_by = actor
    report.save(update_fields=["status", "updated_by", "updated_at"])
    write_receipt(
        report,
        actor,
        UUID(idempotency_key),
        AuditAction.DAILY_REPORT_RETURNED,
        {"reason": reason},
        reason=reason,
        before="submitted",
        after="returned",
        work_item_id=str(work_item.pk),
        workflow_version_id=str(work_item.instance.version_id),
    )


@transaction.atomic
def return_daily_report(
    *,
    organization: Organization,
    actor: User,
    report_id: UUID | str,
    reason: str,
    operation_key: UUID,
) -> DailyReport:
    report = lock_report(organization, report_id)
    membership = require_independent_reviewer(report, actor)
    for permission in (P.DAILY_REPORTS_VIEW, P.WORK_ITEMS_CLAIM, P.WORK_ITEMS_ACT):
        scoped_permission(report, actor, permission)
    reason = _reason(reason)
    if receipt(
        report,
        actor,
        operation_key,
        AuditAction.DAILY_REPORT_RETURNED,
        {"reason": reason},
    ):
        return report
    if report.status != DailyReportStatus.SUBMITTED:
        raise WorkflowConflict("فقط گزارش ارسال‌شده قابل بازگشت است.")
    item = _actor_item(organization=organization, report=report, membership=membership)
    if item.status == WorkItemStatus.OPEN:
        claim_work_item(
            actor=actor,
            organization=organization,
            work_item_id=item.pk,
            idempotency_key=_key(item.pk, operation_key, "return-claim"),
        )
    complete_work_item(
        actor=actor,
        organization=organization,
        work_item_id=item.pk,
        outcome="returned",
        idempotency_key=operation_key.hex,
        command_context={"reason": reason},
    )
    report.refresh_from_db()
    if report.status != DailyReportStatus.RETURNED:
        raise WorkflowConflict("گردش‌کار، بازگشت نسخه را تکمیل نکرد.")
    return report


@transaction.atomic
def publish_return_workflow(
    *, organization: Organization, actor: User, reason: str
) -> WorkflowVersion:
    """Supersede only the tenant's code-owned compatibility definition."""
    reason = _reason(reason)
    organization = (
        type(organization).objects.select_for_update().get(pk=organization.pk)
    )
    from apps.organizations.authorization import require_business_permission

    require_business_permission(
        user=actor,
        organization=organization,
        permission=P.WORKFLOWS_PUBLISH,
        message="مجوز انتشار گردش‌کار الزامی است.",
    )
    current = (
        WorkflowVersion.objects.select_related("definition")
        .filter(
            organization=organization,
            definition__code=COMPATIBILITY_DEFINITION_CODE,
            definition__workflow_type__code=WORKFLOW_TYPE_CODE,
            definition__scope={},
            status="published",
        )
        .first()
    )
    if current is None:
        raise WorkflowConflict("تعریف سازگاری منتشرشده برای این شرکت یافت نشد.")
    if _compatible(current):
        return current
    if (
        current.version_number != 1
        or set(current.steps.values_list("key", flat=True))
        != {
            "start",
            "legacy_approval",
            "approved",
        }
        or current.change_summary != "W5.1 legacy compatibility"
        or not _legacy_configuration_matches(current)
    ):
        raise WorkflowConflict("تعریف سفارشی باید از مسیر پیکربندی گردش‌کار بررسی شود.")
    number = current.definition.versions.aggregate(number=Max("version_number"))[
        "number"
    ]
    draft = WorkflowVersion.objects.create(
        organization=organization,
        definition=current.definition,
        version_number=number + 1,
        change_summary="Daily Report compatibility and independent Return",
    )
    _write_configuration(
        organization=organization, version=draft, configuration=RETURN_CONFIGURATION
    )
    return supersede_workflow_version(
        actor=actor,
        organization=organization,
        new_version_id=draft.pk,
        replaced_version_id=current.pk,
        reason=reason,
    )


@transaction.atomic
def adopt_submitted_report(
    *,
    organization: Organization,
    actor: User,
    report_id: UUID | str,
    reason: str,
    operation_key: UUID,
) -> DailyReport:
    if surface_profile() != "MVP":
        raise PermissionDenied("انتقال به بررسی اصلاحی در این سطح در دسترس نیست.")
    report = lock_report(organization, report_id)
    scoped_permission(report, actor, P.WORKFLOWS_MIGRATE_INSTANCES)
    scoped_permission(report, actor, P.DAILY_REPORTS_VIEW)
    reason = _reason(reason)
    action = AuditAction.DAILY_REPORT_BASELINE_FROZEN
    payload = {"reason": reason}
    if receipt(report, actor, operation_key, action, payload):
        return report
    if (
        report.status != DailyReportStatus.SUBMITTED
        or report.submission_hash
        or not report.submitted_at
    ):
        raise WorkflowConflict("این گزارش ارسال‌شده برای انتقال واجد شرایط نیست.")
    version = _return_version(report)
    instances = list(_instances(report)[:2])
    instance = instances[0] if len(instances) == 1 else None
    if instances and (
        instance is None
        or instance.status != WorkflowInstanceStatus.ACTIVE
        or instance.definition_id != version.definition_id
        or not instance.step_instances.filter(
            status="active",
            step_definition__key=REVIEW_STEP,
        ).exists()
    ):
        raise WorkflowConflict("اجرای قبلی گزارش نگاشت قطعی به بررسی مستقل ندارد.")
    evidence = AuditEvent.objects.filter(
        organization=organization,
        entity_type="daily_report",
        entity_id=str(report.pk),
    )
    authors = list(
        evidence.filter(action=AuditAction.DAILY_REPORT_CREATED).values_list(
            "actor_id", flat=True
        )[:2]
    )
    submissions = list(
        evidence.filter(action=AuditAction.DAILY_REPORT_SUBMITTED).select_related(
            "actor"
        )[:2]
    )
    if (
        not report.created_by_id
        or authors != [report.created_by_id]
        or len(submissions) != 1
        or not submissions[0].actor_id
        or report.updated_by_id != submissions[0].actor_id
    ):
        raise WorkflowConflict("هویت نویسنده یا ارسال‌کننده از سابقه قابل اثبات نیست.")
    submitter = submissions[0].actor
    creator = get_active_membership(
        user=report.created_by, organization=report.organization
    )
    membership = get_active_membership(user=submitter, organization=report.organization)
    if instance and (
        str(creator.pk) != instance.subject_context.get("creator_membership_id")
        or str(membership.pk) != instance.subject_context.get("submitter_membership_id")
    ):
        raise WorkflowConflict("هویت ثبت‌شده با سابقه گردش‌کار هم‌خوان نیست.")
    old_version = instance.version_id if instance else None
    seal_submission(
        report,
        submitter=submitter,
        membership=membership,
        creator_membership=creator,
        legacy=True,
    )
    report.save(update_fields=["submission_snapshot", "submission_hash"])
    if instance:
        instance = migrate_workflow_instance(
            actor=actor,
            organization=report.organization,
            instance_id=instance.pk,
            target_version_id=version.pk,
            reason=reason,
            idempotency_key=operation_key.hex,
        )
        _assert_actionable(report, instance)
    else:
        instance = _start_review(report, submitter, version)
    write_receipt(
        report,
        actor,
        operation_key,
        action,
        payload,
        reason=reason,
        before="submitted",
        after="submitted",
        instance_id=str(instance.pk),
        old_workflow_version_id=str(old_version) if old_version else None,
        workflow_version_id=str(version.pk),
    )
    return report


def review_controls(report: DailyReport, actor: User) -> bool:
    """Check exact current candidate before showing Return or approval."""
    if report.status != DailyReportStatus.SUBMITTED or not report.submission_hash:
        return False
    try:
        membership = require_independent_reviewer(report, actor)
        for permission in (P.WORK_ITEMS_CLAIM, P.WORK_ITEMS_ACT):
            scoped_permission(report, actor, permission)
        item = _actor_item(
            organization=report.organization, report=report, membership=membership
        )
        return (
            item.status == WorkItemStatus.OPEN
            or item.current_assignee_id == membership.pk
        )
    except (PermissionDenied, ValidationError, WorkflowConflict):
        return False
