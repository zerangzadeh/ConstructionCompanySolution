"""F6 workflow orchestration for commercial baselines and progress verification."""

from __future__ import annotations

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

from .models import (
    BaselineItem,
    ProgressClaim,
    ProgressRecord,
    ProgressRecordStatus,
    ProjectBaseline,
    ProjectBaselineStatus,
)

WORKFLOW_TYPE_CODE = "billing.project_baseline_approval"
SUBJECT_TYPE = "billing.project_baseline"
TEMPLATE_CODE = "project_baseline_f61"
DEFINITION_CODE = "project-baseline-f61"
APPROVE_PERMISSION = BusinessPermissionCode.BASELINES_APPROVE
PROGRESS_WORKFLOW_TYPE_CODE = "billing.progress_verification"
PROGRESS_SUBJECT_TYPE = "billing.progress_record"
PROGRESS_TEMPLATE_CODE = "progress_verification_f62"
PROGRESS_DEFINITION_CODE = "progress-verification-f62"
VERIFY_PERMISSION = BusinessPermissionCode.PROGRESS_VERIFY
CLAIM_WORKFLOW_TYPE_CODE = "billing.progress_claim_approval"
CLAIM_SUBJECT_TYPE = "billing.progress_claim"
CLAIM_TEMPLATE_CODE = "progress_claim_approval_f64"
CLAIM_DEFINITION_CODE = "progress-claim-f64"
CLAIM_APPROVE_PERMISSION = BusinessPermissionCode.CLAIMS_APPROVE


def _key(*parts: object) -> str:
    return sha256(":".join(str(part) for part in parts).encode()).hexdigest()


def _active_membership_id(organization: Organization, user_id: object) -> str | None:
    if not user_id:
        return None
    membership_id = (
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
    return str(membership_id) if membership_id else None


def load_project_baseline_subject(
    *, organization: Organization, subject_id: UUID, actor: User, for_update: bool
) -> SubjectSnapshot:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.BASELINES_VIEW,
        message="اجازه مشاهده مبنای تجاری را ندارید.",
    )
    queryset = ProjectBaseline.objects.select_related("project", "contract")
    if for_update:
        queryset = queryset.select_for_update(of=("self",))
    try:
        baseline = queryset.get(pk=subject_id, organization=organization)
    except ProjectBaseline.DoesNotExist as exc:
        raise PermissionDenied("مبنای تجاری در این سازمان یافت نشد.") from exc
    if (
        baseline.project.organization_id != organization.pk
        or baseline.project.deleted_at is not None
        or baseline.contract.organization_id != organization.pk
        or baseline.contract.deleted_at is not None
    ):
        raise PermissionDenied("دامنه مبنای تجاری معتبر نیست.")
    return SubjectSnapshot(
        subject=baseline,
        subject_id=str(baseline.pk),
        organization_id=str(organization.pk),
        attributes={
            "project_id": str(baseline.project_id),
            "contract_id": str(baseline.contract_id),
            "status": baseline.status,
            "version": baseline.version,
            "created_by_id": str(baseline.created_by_id)
            if baseline.created_by_id
            else None,
        },
        creator_membership_id=_active_membership_id(
            organization, baseline.created_by_id
        ),
        submitter_membership_id=_active_membership_id(
            organization, baseline.updated_by_id
        ),
        display=f"{baseline.contract.contract_number} — مبنا {baseline.version}",
    )


def _approve_command(
    *,
    subject: ProjectBaseline,
    actor: User,
    organization: Organization,
    context: dict[str, Any],
    **_: object,
) -> ProjectBaseline:
    from .services import _approve_project_baseline_domain

    reason = context.get("reason", "")
    if not isinstance(reason, str):
        raise ValidationError("دلیل تأیید مبنا معتبر نیست.")
    return _approve_project_baseline_domain(
        organization=organization, actor=actor, baseline=subject, reason=reason
    )


def register_project_baseline_workflow() -> None:
    registry.bind_subject_loader(SUBJECT_TYPE, load_project_baseline_subject)
    registry.bind_domain_command("billing.project_baseline.approve", _approve_command)


def load_progress_record_subject(
    *, organization: Organization, subject_id: UUID, actor: User, for_update: bool
) -> SubjectSnapshot:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.PROGRESS_VIEW,
        message="اجازه مشاهده پیشرفت را ندارید.",
    )
    queryset = ProgressRecord.objects.select_related(
        "baseline__project", "baseline__contract", "baseline_item"
    )
    if for_update:
        queryset = queryset.select_for_update(of=("self",))
    try:
        record = queryset.get(pk=subject_id, organization=organization)
    except ProgressRecord.DoesNotExist as exc:
        raise PermissionDenied("رکورد پیشرفت در این سازمان یافت نشد.") from exc
    if (
        record.baseline.organization_id != organization.pk
        or record.baseline_item.organization_id != organization.pk
        or record.baseline_item.baseline_id != record.baseline_id
        or record.baseline.project.deleted_at is not None
        or record.baseline.contract.deleted_at is not None
    ):
        raise PermissionDenied("دامنه رکورد پیشرفت معتبر نیست.")
    return SubjectSnapshot(
        subject=record,
        subject_id=str(record.pk),
        organization_id=str(organization.pk),
        attributes={
            "project_id": str(record.baseline.project_id),
            "contract_id": str(record.baseline.contract_id),
            "baseline_id": str(record.baseline_id),
            "baseline_item_id": str(record.baseline_item_id),
            "status": record.status,
            "created_by_id": str(record.created_by_id)
            if record.created_by_id
            else None,
        },
        creator_membership_id=_active_membership_id(organization, record.created_by_id),
        submitter_membership_id=_active_membership_id(
            organization, record.submitted_by_id or record.created_by_id
        ),
        display=f"{record.baseline.contract.contract_number} — {record.baseline_item.line_key}",
    )


def _verify_progress_command(
    *,
    subject: ProgressRecord,
    actor: User,
    organization: Organization,
    context: dict[str, Any],
    **_: object,
) -> ProgressRecord:
    from .services import _verify_progress_record_domain

    reason = context.get("reason", "")
    if not isinstance(reason, str):
        raise ValidationError("دلیل راستی‌آزمایی معتبر نیست.")
    return _verify_progress_record_domain(
        organization=organization, actor=actor, record=subject, reason=reason
    )


def _reject_progress_command(
    *,
    subject: ProgressRecord,
    actor: User,
    organization: Organization,
    context: dict[str, Any],
    **_: object,
) -> ProgressRecord:
    from .services import _reject_progress_record_domain

    reason = context.get("reason", "")
    if not isinstance(reason, str):
        raise ValidationError("دلیل رد معتبر نیست.")
    return _reject_progress_record_domain(
        organization=organization, actor=actor, record=subject, reason=reason
    )


def register_progress_verification_workflow() -> None:
    registry.bind_subject_loader(PROGRESS_SUBJECT_TYPE, load_progress_record_subject)
    registry.bind_domain_command("billing.progress.verify", _verify_progress_command)
    registry.bind_domain_command("billing.progress.reject", _reject_progress_command)


def load_progress_claim_subject(
    *, organization: Organization, subject_id: UUID, actor: User, for_update: bool
) -> SubjectSnapshot:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.CLAIMS_VIEW,
        message="اجازه مشاهده صورت‌وضعیت را ندارید.",
    )
    queryset = ProgressClaim.objects.select_related("project", "contract", "baseline")
    if for_update:
        queryset = queryset.select_for_update(of=("self",))
    try:
        claim = queryset.get(pk=subject_id, organization=organization)
    except ProgressClaim.DoesNotExist as exc:
        raise PermissionDenied("صورت‌وضعیت در این سازمان یافت نشد.") from exc
    if (
        claim.project.organization_id != organization.pk
        or claim.contract.organization_id != organization.pk
        or claim.baseline.organization_id != organization.pk
        or claim.baseline.project_id != claim.project_id
        or claim.baseline.contract_id != claim.contract_id
    ):
        raise PermissionDenied("دامنه صورت‌وضعیت معتبر نیست.")
    return SubjectSnapshot(
        subject=claim,
        subject_id=str(claim.pk),
        organization_id=str(organization.pk),
        attributes={
            "project_id": str(claim.project_id),
            "contract_id": str(claim.contract_id),
            "baseline_id": str(claim.baseline_id),
            "status": claim.status,
            "claim_number": claim.claim_number,
            "revision_number": claim.revision_number,
            "created_by_id": str(claim.created_by_id) if claim.created_by_id else None,
            "submitted_by_id": (
                str(claim.submitted_by_id) if claim.submitted_by_id else None
            ),
        },
        creator_membership_id=_active_membership_id(organization, claim.created_by_id),
        submitter_membership_id=_active_membership_id(
            organization, claim.submitted_by_id or claim.created_by_id
        ),
        display=(
            f"{claim.contract.contract_number} — صورت‌وضعیت "
            f"{claim.claim_number} / ویرایش {claim.revision_number}"
        ),
    )


def _approve_progress_claim_command(
    *,
    subject: ProgressClaim,
    actor: User,
    organization: Organization,
    context: dict[str, Any],
    **_: object,
) -> ProgressClaim:
    from .services import _approve_progress_claim_domain

    reason = context.get("reason", "")
    if not isinstance(reason, str):
        raise ValidationError("دلیل تأیید صورت‌وضعیت معتبر نیست.")
    return _approve_progress_claim_domain(
        organization=organization, actor=actor, claim=subject, reason=reason
    )


def _return_progress_claim_command(
    *,
    subject: ProgressClaim,
    actor: User,
    organization: Organization,
    context: dict[str, Any],
    **_: object,
) -> ProgressClaim:
    from .services import _return_progress_claim_domain

    reason = context.get("reason", "")
    if not isinstance(reason, str):
        raise ValidationError("دلیل بازگردانی صورت‌وضعیت معتبر نیست.")
    return _return_progress_claim_domain(
        organization=organization, actor=actor, claim=subject, reason=reason
    )


def register_progress_claim_approval_workflow() -> None:
    registry.bind_subject_loader(CLAIM_SUBJECT_TYPE, load_progress_claim_subject)
    registry.bind_domain_command(
        "billing.progress_claim.approve", _approve_progress_claim_command
    )
    registry.bind_domain_command(
        "billing.progress_claim.return", _return_progress_claim_command
    )


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


@transaction.atomic
def ensure_project_baseline_workflow(
    *, organization: Organization, actor: User
) -> WorkflowVersion:
    """Publish the tenant's small-company starter route once, under tenant lock."""

    get_active_membership(user=actor, organization=organization)
    locked = Organization.objects.select_for_update().get(pk=organization.pk)
    workflow_type = WorkflowType.objects.get(code=WORKFLOW_TYPE_CODE, is_active=True)
    _, scope_key = canonical_scope({})
    existing = (
        WorkflowVersion.objects.select_related("definition")
        .filter(
            organization=locked,
            definition__workflow_type=workflow_type,
            definition__scope_key=scope_key,
            status=WorkflowVersionStatus.PUBLISHED,
        )
        .first()
    )
    if existing:
        if validate_workflow_version(existing):
            raise ValidationError("گردش‌کار پیش‌فرض مبنای تجاری معتبر نیست.")
        return existing
    template = WorkflowTemplate.objects.get(
        workflow_type=workflow_type, code=TEMPLATE_CODE, is_active=True
    )
    definition, created = WorkflowDefinition.objects.get_or_create(
        organization=locked,
        workflow_type=workflow_type,
        scope_key=scope_key,
        defaults={
            "code": DEFINITION_CODE,
            "name": "تأیید مبنای تجاری پروژه",
            "description": "تأیید تک‌مرحله‌ای مبنای تجاری کاملاً قیمت‌گذاری‌شده.",
            "scope": {},
            "created_by": actor,
            "updated_by": actor,
        },
    )
    if not created:
        raise ValidationError("تعریف پیش‌فرض مبنا نسخه منتشرشده ندارد.")
    version = WorkflowVersion.objects.create(
        organization=locked,
        definition=definition,
        version_number=1,
        change_summary="F6.1 baseline starter workflow",
    )
    _write_configuration(
        organization=locked, version=version, configuration=template.configuration
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
    for action, entity_type, entity_id in (
        (
            AuditAction.WORKFLOW_DEFINITION_CREATED,
            "workflows.WorkflowDefinition",
            definition.pk,
        ),
        (
            AuditAction.WORKFLOW_VERSION_PUBLISHED,
            "workflows.WorkflowVersion",
            version.pk,
        ),
    ):
        record_audit_event(
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            organization=locked,
            actor=actor,
            metadata={"workflow_type": WORKFLOW_TYPE_CODE, "starter": True},
        )
    version.refresh_from_db()
    return version


def resolve_project_baseline_version(
    *, organization: Organization, baseline: ProjectBaseline
) -> WorkflowVersion:
    if baseline.organization_id != organization.pk:
        raise PermissionDenied("مبنای تجاری متعلق به سازمان دیگری است.")
    context = {
        "project_id": str(baseline.project_id),
        "contract_id": str(baseline.contract_id),
    }
    matches = [
        (len(version.definition.scope), version)
        for version in WorkflowVersion.objects.select_related("definition").filter(
            organization=organization,
            definition__workflow_type__code=WORKFLOW_TYPE_CODE,
            status=WorkflowVersionStatus.PUBLISHED,
        )
        if all(
            context.get(key) == value for key, value in version.definition.scope.items()
        )
    ]
    if not matches:
        raise ValidationError("نسخه منتشرشده برای مبنای تجاری یافت نشد.")
    score = max(value for value, _ in matches)
    selected = [version for value, version in matches if value == score]
    if len(selected) != 1:
        raise ValidationError("انتخاب نسخه گردش‌کار مبنا مبهم است.")
    return selected[0]


@transaction.atomic
def request_project_baseline_approval_with_workflow(
    *, organization: Organization, actor: User, baseline: ProjectBaseline
) -> WorkflowInstance:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.BASELINES_MANAGE,
        message="اجازه ارسال مبنای تجاری برای تأیید را ندارید.",
    )
    try:
        locked = (
            ProjectBaseline.objects.select_for_update()
            .select_related("project", "contract")
            .get(pk=baseline.pk, organization=organization)
        )
    except ProjectBaseline.DoesNotExist as exc:
        raise PermissionDenied("مبنای تجاری متعلق به این سازمان نیست.") from exc
    if locked.status != ProjectBaselineStatus.DRAFT:
        raise ValidationError("فقط مبنای پیش‌نویس قابل ارسال برای تأیید است.")
    if not BaselineItem.objects.filter(
        organization=organization, baseline=locked
    ).exists():
        raise ValidationError("مبنای تجاری باید دست‌کم یک ردیف قیمت‌گذاری‌شده داشته باشد.")
    ensure_project_baseline_workflow(organization=organization, actor=actor)
    version = resolve_project_baseline_version(
        organization=organization, baseline=locked
    )
    instance = start_workflow(
        actor=actor,
        organization=organization,
        version_id=version.pk,
        subject_id=locked.pk,
        idempotency_key=_key(WORKFLOW_TYPE_CODE, locked.pk, "request"),
    )
    if (
        instance.status != WorkflowInstanceStatus.ACTIVE
        or not instance.work_items.filter(
            status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED)
        ).exists()
    ):
        raise WorkflowConflict("درخواست تأیید مبنا بدون کار فعال قابل ثبت نیست.")
    return instance


def _actor_item(
    *,
    organization: Organization,
    baseline: ProjectBaseline,
    membership: OrganizationMembership,
) -> WorkItem:
    item = (
        WorkItem.objects.select_related("instance", "current_assignee")
        .filter(
            organization=organization,
            instance__subject_type=SUBJECT_TYPE,
            instance__subject_id=baseline.pk,
            instance__status=WorkflowInstanceStatus.ACTIVE,
            status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED),
            candidates__membership=membership,
            candidates__is_active=True,
        )
        .distinct()
        .first()
    )
    if item is None:
        raise PermissionDenied("کار فعال و نامزدی معتبر برای تأیید مبنا وجود ندارد.")
    return item


@transaction.atomic
def approve_project_baseline_with_workflow(
    *,
    organization: Organization,
    actor: User,
    baseline: ProjectBaseline,
    reason: str,
) -> ProjectBaseline:
    """Complete the common work item; direct F6 baseline approval is prohibited."""

    if not reason.strip():
        raise ValidationError("دلیل تأیید مبنا الزامی است.")
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=APPROVE_PERMISSION,
        message="اجازه تأیید مبنای تجاری این سازمان را ندارید.",
    ) or get_active_membership(user=actor, organization=organization)
    try:
        locked = ProjectBaseline.objects.select_for_update().get(
            pk=baseline.pk, organization=organization
        )
    except ProjectBaseline.DoesNotExist as exc:
        raise PermissionDenied("مبنای تجاری متعلق به این سازمان نیست.") from exc
    if locked.status != ProjectBaselineStatus.DRAFT:
        raise ValidationError("فقط مبنای پیش‌نویس قابل تأیید است.")
    item = _actor_item(
        organization=organization, baseline=locked, membership=membership
    )
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
        command_context={"reason": reason.strip()},
    )
    locked.refresh_from_db()
    return locked


@transaction.atomic
def ensure_progress_verification_workflow(
    *, organization: Organization, actor: User
) -> WorkflowVersion:
    """Publish the F6.2 small-tenant verification route once per organization."""

    get_active_membership(user=actor, organization=organization)
    locked = Organization.objects.select_for_update().get(pk=organization.pk)
    workflow_type = WorkflowType.objects.get(
        code=PROGRESS_WORKFLOW_TYPE_CODE, is_active=True
    )
    _, scope_key = canonical_scope({})
    existing = (
        WorkflowVersion.objects.select_related("definition")
        .filter(
            organization=locked,
            definition__workflow_type=workflow_type,
            definition__scope_key=scope_key,
            status=WorkflowVersionStatus.PUBLISHED,
        )
        .first()
    )
    if existing:
        if validate_workflow_version(existing):
            raise ValidationError("گردش‌کار پیش‌فرض راستی‌آزمایی پیشرفت معتبر نیست.")
        return existing
    template = WorkflowTemplate.objects.get(
        workflow_type=workflow_type, code=PROGRESS_TEMPLATE_CODE, is_active=True
    )
    definition, created = WorkflowDefinition.objects.get_or_create(
        organization=locked,
        workflow_type=workflow_type,
        scope_key=scope_key,
        defaults={
            "code": PROGRESS_DEFINITION_CODE,
            "name": "راستی‌آزمایی پیشرفت",
            "description": "راستی‌آزمایی تک‌مرحله‌ای منبع پیشرفت برای سازمان‌های کوچک.",
            "scope": {},
            "created_by": actor,
            "updated_by": actor,
        },
    )
    if not created:
        raise ValidationError("تعریف پیش‌فرض پیشرفت نسخه منتشرشده ندارد.")
    version = WorkflowVersion.objects.create(
        organization=locked,
        definition=definition,
        version_number=1,
        change_summary="F6.2 progress verification starter workflow",
    )
    _write_configuration(
        organization=locked, version=version, configuration=template.configuration
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
    for action, entity_type, entity_id in (
        (
            AuditAction.WORKFLOW_DEFINITION_CREATED,
            "workflows.WorkflowDefinition",
            definition.pk,
        ),
        (
            AuditAction.WORKFLOW_VERSION_PUBLISHED,
            "workflows.WorkflowVersion",
            version.pk,
        ),
    ):
        record_audit_event(
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            organization=locked,
            actor=actor,
            metadata={"workflow_type": PROGRESS_WORKFLOW_TYPE_CODE, "starter": True},
        )
    version.refresh_from_db()
    return version


def resolve_progress_verification_version(
    *, organization: Organization, record: ProgressRecord
) -> WorkflowVersion:
    if record.organization_id != organization.pk:
        raise PermissionDenied("رکورد پیشرفت متعلق به سازمان دیگری است.")
    context = {
        "project_id": str(record.baseline.project_id),
        "contract_id": str(record.baseline.contract_id),
        "baseline_id": str(record.baseline_id),
    }
    matches = [
        (len(version.definition.scope), version)
        for version in WorkflowVersion.objects.select_related("definition").filter(
            organization=organization,
            definition__workflow_type__code=PROGRESS_WORKFLOW_TYPE_CODE,
            status=WorkflowVersionStatus.PUBLISHED,
        )
        if all(
            context.get(key) == value for key, value in version.definition.scope.items()
        )
    ]
    if not matches:
        raise ValidationError("نسخه منتشرشده برای راستی‌آزمایی پیشرفت یافت نشد.")
    score = max(value for value, _ in matches)
    selected = [version for value, version in matches if value == score]
    if len(selected) != 1:
        raise ValidationError("انتخاب نسخه گردش‌کار پیشرفت مبهم است.")
    return selected[0]


@transaction.atomic
def request_progress_verification_with_workflow(
    *, organization: Organization, actor: User, record: ProgressRecord
) -> WorkflowInstance:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.PROGRESS_RECORD,
        message="اجازه ارسال پیشرفت برای راستی‌آزمایی را ندارید.",
    )
    try:
        locked = (
            ProgressRecord.objects.select_for_update()
            .select_related("baseline__project", "baseline__contract", "baseline_item")
            .get(pk=record.pk, organization=organization)
        )
    except ProgressRecord.DoesNotExist as exc:
        raise PermissionDenied("رکورد پیشرفت متعلق به این سازمان نیست.") from exc
    if locked.status != ProgressRecordStatus.DRAFT:
        raise ValidationError("فقط رکورد پیش‌نویس قابل ارسال برای راستی‌آزمایی است.")
    if locked.baseline.status != ProjectBaselineStatus.APPROVED:
        raise ValidationError("مبنای رکورد پیشرفت باید تأییدشده باشد.")
    ensure_progress_verification_workflow(organization=organization, actor=actor)
    version = resolve_progress_verification_version(
        organization=organization, record=locked
    )
    instance = start_workflow(
        actor=actor,
        organization=organization,
        version_id=version.pk,
        subject_id=locked.pk,
        idempotency_key=_key(PROGRESS_WORKFLOW_TYPE_CODE, locked.pk, "request"),
    )
    if (
        instance.status != WorkflowInstanceStatus.ACTIVE
        or not instance.work_items.filter(
            status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED)
        ).exists()
    ):
        raise WorkflowConflict("درخواست راستی‌آزمایی بدون کار فعال قابل ثبت نیست.")
    locked.status = ProgressRecordStatus.SUBMITTED
    locked.submitted_by = actor
    locked.submitted_at = timezone.now()
    locked.updated_by = actor
    locked.save(
        update_fields=[
            "status",
            "submitted_by",
            "submitted_at",
            "updated_by",
            "updated_at",
        ]
    )
    return instance


def _actor_progress_item(
    *,
    organization: Organization,
    record: ProgressRecord,
    membership: OrganizationMembership,
) -> WorkItem:
    item = (
        WorkItem.objects.select_related("instance", "current_assignee")
        .filter(
            organization=organization,
            instance__subject_type=PROGRESS_SUBJECT_TYPE,
            instance__subject_id=record.pk,
            instance__status=WorkflowInstanceStatus.ACTIVE,
            status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED),
            candidates__membership=membership,
            candidates__is_active=True,
        )
        .distinct()
        .first()
    )
    if item is None:
        raise PermissionDenied("کار فعال و نامزدی معتبر برای راستی‌آزمایی وجود ندارد.")
    return item


def _complete_progress_work_item(
    *,
    organization: Organization,
    actor: User,
    record: ProgressRecord,
    reason: str,
    outcome: str,
) -> ProgressRecord:
    if not reason.strip():
        raise ValidationError("دلیل تصمیم راستی‌آزمایی الزامی است.")
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=VERIFY_PERMISSION,
        message="اجازه راستی‌آزمایی پیشرفت این سازمان را ندارید.",
    ) or get_active_membership(user=actor, organization=organization)
    try:
        locked = ProgressRecord.objects.select_for_update().get(
            pk=record.pk, organization=organization
        )
    except ProgressRecord.DoesNotExist as exc:
        raise PermissionDenied("رکورد پیشرفت متعلق به این سازمان نیست.") from exc
    if locked.status != ProgressRecordStatus.SUBMITTED:
        raise ValidationError("فقط رکورد ارسال‌شده قابل تصمیم‌گیری است.")
    item = _actor_progress_item(
        organization=organization, record=locked, membership=membership
    )
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
        outcome=outcome,
        idempotency_key=_key(item.pk, membership.pk, outcome),
        command_context={"reason": reason.strip()},
    )
    locked.refresh_from_db()
    return locked


@transaction.atomic
def verify_progress_record_with_workflow(
    *, organization: Organization, actor: User, record: ProgressRecord, reason: str
) -> ProgressRecord:
    return _complete_progress_work_item(
        organization=organization,
        actor=actor,
        record=record,
        reason=reason,
        outcome="verified",
    )


@transaction.atomic
def reject_progress_record_with_workflow(
    *, organization: Organization, actor: User, record: ProgressRecord, reason: str
) -> ProgressRecord:
    return _complete_progress_work_item(
        organization=organization,
        actor=actor,
        record=record,
        reason=reason,
        outcome="rejected",
    )


@transaction.atomic
def ensure_progress_claim_approval_workflow(
    *, organization: Organization, actor: User
) -> WorkflowVersion:
    """Publish the immutable F6.4 starter approval route once per tenant."""

    get_active_membership(user=actor, organization=organization)
    locked = Organization.objects.select_for_update().get(pk=organization.pk)
    workflow_type = WorkflowType.objects.get(
        code=CLAIM_WORKFLOW_TYPE_CODE, is_active=True
    )
    _, scope_key = canonical_scope({})
    existing = (
        WorkflowVersion.objects.select_related("definition")
        .filter(
            organization=locked,
            definition__workflow_type=workflow_type,
            definition__scope_key=scope_key,
            status=WorkflowVersionStatus.PUBLISHED,
        )
        .first()
    )
    if existing:
        if validate_workflow_version(existing):
            raise ValidationError("گردش‌کار پیش‌فرض صورت‌وضعیت معتبر نیست.")
        return existing
    template = WorkflowTemplate.objects.get(
        workflow_type=workflow_type, code=CLAIM_TEMPLATE_CODE, is_active=True
    )
    definition, created = WorkflowDefinition.objects.get_or_create(
        organization=locked,
        workflow_type=workflow_type,
        scope_key=scope_key,
        defaults={
            "code": CLAIM_DEFINITION_CODE,
            "name": "تأیید صورت‌وضعیت پروژه",
            "description": "تأیید مدیر سمت بالادست با مسیر کوچک‌مستأجر.",
            "scope": {},
            "created_by": actor,
            "updated_by": actor,
        },
    )
    if not created:
        raise ValidationError("تعریف پیش‌فرض صورت‌وضعیت نسخه منتشرشده ندارد.")
    version = WorkflowVersion.objects.create(
        organization=locked,
        definition=definition,
        version_number=1,
        change_summary="F6.4 progress claim approval starter workflow",
    )
    _write_configuration(
        organization=locked, version=version, configuration=template.configuration
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
    for action, entity_type, entity_id in (
        (
            AuditAction.WORKFLOW_DEFINITION_CREATED,
            "workflows.WorkflowDefinition",
            definition.pk,
        ),
        (
            AuditAction.WORKFLOW_VERSION_PUBLISHED,
            "workflows.WorkflowVersion",
            version.pk,
        ),
    ):
        record_audit_event(
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            organization=locked,
            actor=actor,
            metadata={"workflow_type": CLAIM_WORKFLOW_TYPE_CODE, "starter": True},
        )
    version.refresh_from_db()
    return version


def resolve_progress_claim_approval_version(
    *, organization: Organization, claim: ProgressClaim
) -> WorkflowVersion:
    if claim.organization_id != organization.pk:
        raise PermissionDenied("صورت‌وضعیت متعلق به سازمان دیگری است.")
    context = {
        "project_id": str(claim.project_id),
        "contract_id": str(claim.contract_id),
        "baseline_id": str(claim.baseline_id),
    }
    matches = [
        (len(version.definition.scope), version)
        for version in WorkflowVersion.objects.select_related("definition").filter(
            organization=organization,
            definition__workflow_type__code=CLAIM_WORKFLOW_TYPE_CODE,
            status=WorkflowVersionStatus.PUBLISHED,
        )
        if all(
            context.get(key) == value for key, value in version.definition.scope.items()
        )
    ]
    if not matches:
        raise ValidationError("نسخه منتشرشده برای تأیید صورت‌وضعیت یافت نشد.")
    score = max(value for value, _ in matches)
    selected = [version for value, version in matches if value == score]
    if len(selected) != 1:
        raise ValidationError("انتخاب نسخه گردش‌کار صورت‌وضعیت مبهم است.")
    return selected[0]


def _claim_submission_snapshot(claim: ProgressClaim) -> dict[str, Any]:
    return {
        "claim": {
            "id": str(claim.pk),
            "claim_number": claim.claim_number,
            "revision_number": claim.revision_number,
            "period_start": claim.period_start.isoformat(),
            "period_end": claim.period_end.isoformat(),
            "measurement_cutoff": claim.measurement_cutoff.isoformat(),
            "gross_amount": str(claim.gross_amount),
            "adjustment_amount": str(claim.adjustment_amount),
            "net_amount": str(claim.net_amount),
            "policy": claim.policy_snapshot,
        },
        "items": [
            {
                "id": str(item.pk),
                "baseline_item_id": str(item.baseline_item_id),
                "previous_cumulative_quantity": str(item.previous_cumulative_quantity),
                "current_quantity": str(item.current_quantity),
                "new_cumulative_quantity": str(item.new_cumulative_quantity),
                "unit_rate_snapshot": str(item.unit_rate_snapshot),
                "current_amount": str(item.current_amount),
                "source_ids": [
                    str(source.progress_record_id) for source in item.sources.all()
                ],
            }
            for item in claim.items.prefetch_related("sources").order_by("pk")
        ],
        "adjustments": [
            {
                "id": str(item.pk),
                "adjustment_type": item.adjustment_type,
                "description": item.description,
                "sequence": item.sequence,
                "rate_snapshot": str(item.rate_snapshot)
                if item.rate_snapshot is not None
                else None,
                "base_amount_snapshot": (
                    str(item.base_amount_snapshot)
                    if item.base_amount_snapshot is not None
                    else None
                ),
                "amount": str(item.amount),
                "evidence": item.evidence,
            }
            for item in claim.adjustments.order_by("sequence", "pk")
        ],
    }


@transaction.atomic
def submit_progress_claim_with_workflow(
    *, organization: Organization, actor: User, claim: ProgressClaim
) -> WorkflowInstance:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.CLAIMS_SUBMIT,
        message="اجازه ارسال صورت‌وضعیت را ندارید.",
    )
    try:
        locked = (
            ProgressClaim.objects.select_for_update()
            .select_related("project", "contract", "baseline")
            .get(pk=claim.pk, organization=organization)
        )
    except ProgressClaim.DoesNotExist as exc:
        raise PermissionDenied("صورت‌وضعیت متعلق به این سازمان نیست.") from exc
    if locked.status == "submitted":
        instance = WorkflowInstance.objects.filter(
            organization=organization,
            subject_type=CLAIM_SUBJECT_TYPE,
            subject_id=locked.pk,
            status=WorkflowInstanceStatus.ACTIVE,
        ).first()
        if instance is not None:
            return instance
    if locked.status != "draft":
        raise ValidationError("فقط صورت‌وضعیت پیش‌نویس قابل ارسال است.")
    if not locked.items.exists():
        raise ValidationError("صورت‌وضعیت بدون ردیف محاسباتی قابل ارسال نیست.")
    # The shared runtime snapshots the submitter when it starts. Persist this
    # provisional provenance inside the enclosing transaction before loading it.
    locked.submitted_by = actor
    locked.updated_by = actor
    locked.save(update_fields=["submitted_by", "updated_by", "updated_at"])
    ensure_progress_claim_approval_workflow(organization=organization, actor=actor)
    version = resolve_progress_claim_approval_version(
        organization=organization, claim=locked
    )
    instance = start_workflow(
        actor=actor,
        organization=organization,
        version_id=version.pk,
        subject_id=locked.pk,
        idempotency_key=_key(CLAIM_WORKFLOW_TYPE_CODE, locked.pk, "submit"),
    )
    if (
        instance.status != WorkflowInstanceStatus.ACTIVE
        or not instance.work_items.filter(
            status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED)
        ).exists()
    ):
        raise WorkflowConflict("ارسال صورت‌وضعیت بدون کار فعال قابل ثبت نیست.")
    locked.submitted_by = actor
    locked.submitted_at = timezone.now()
    locked.submission_snapshot = _claim_submission_snapshot(locked)
    locked.status = "submitted"
    locked.updated_by = actor
    locked.save(
        update_fields=[
            "status",
            "submitted_by",
            "submitted_at",
            "submission_snapshot",
            "updated_by",
            "updated_at",
        ]
    )
    record_audit_event(
        action=AuditAction.PROGRESS_CLAIM_SUBMITTED,
        entity_type="billing.ProgressClaim",
        entity_id=str(locked.pk),
        organization=organization,
        actor=actor,
        metadata={
            "claim_number": locked.claim_number,
            "revision": locked.revision_number,
        },
    )
    return instance


def _actor_claim_item(
    *,
    organization: Organization,
    claim: ProgressClaim,
    membership: OrganizationMembership,
) -> WorkItem:
    item = (
        WorkItem.objects.select_related("instance", "current_assignee")
        .filter(
            organization=organization,
            instance__subject_type=CLAIM_SUBJECT_TYPE,
            instance__subject_id=claim.pk,
            instance__status=WorkflowInstanceStatus.ACTIVE,
            status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED),
            candidates__membership=membership,
            candidates__is_active=True,
        )
        .distinct()
        .first()
    )
    if item is None:
        raise PermissionDenied("کار فعال و نامزدی معتبر برای صورت‌وضعیت وجود ندارد.")
    return item


def _complete_claim_work_item(
    *,
    organization: Organization,
    actor: User,
    claim: ProgressClaim,
    reason: str,
    outcome: str,
) -> ProgressClaim:
    if not reason.strip():
        raise ValidationError("دلیل تصمیم صورت‌وضعیت الزامی است.")
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=CLAIM_APPROVE_PERMISSION,
        message="اجازه تأیید صورت‌وضعیت این سازمان را ندارید.",
    ) or get_active_membership(user=actor, organization=organization)
    try:
        locked = ProgressClaim.objects.select_for_update().get(
            pk=claim.pk, organization=organization
        )
    except ProgressClaim.DoesNotExist as exc:
        raise PermissionDenied("صورت‌وضعیت متعلق به این سازمان نیست.") from exc
    terminal_status = "approved" if outcome == "approved" else "returned"
    terminal_actor_field = (
        "approved_by_id" if outcome == "approved" else "returned_by_id"
    )
    if (
        locked.status == terminal_status
        and getattr(locked, terminal_actor_field) == actor.pk
    ):
        return locked
    if locked.status != "submitted":
        raise ValidationError("فقط صورت‌وضعیت ارسال‌شده قابل تصمیم‌گیری است.")
    item = _actor_claim_item(
        organization=organization, claim=locked, membership=membership
    )
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
        outcome=outcome,
        idempotency_key=_key(item.pk, membership.pk, outcome),
        command_context={"reason": reason.strip()},
    )
    locked.refresh_from_db()
    return locked


@transaction.atomic
def approve_progress_claim_with_workflow(
    *, organization: Organization, actor: User, claim: ProgressClaim, reason: str
) -> ProgressClaim:
    return _complete_claim_work_item(
        organization=organization,
        actor=actor,
        claim=claim,
        reason=reason,
        outcome="approved",
    )


@transaction.atomic
def return_progress_claim_with_workflow(
    *, organization: Organization, actor: User, claim: ProgressClaim, reason: str
) -> ProgressClaim:
    return _complete_claim_work_item(
        organization=organization,
        actor=actor,
        claim=claim,
        reason=reason,
        outcome="returned",
    )
