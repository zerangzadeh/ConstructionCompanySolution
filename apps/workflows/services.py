from __future__ import annotations

from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, models, transaction
from django.db.models import Max
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import BusinessPermissionCode, Organization

from .models import (
    WorkflowCondition,
    WorkflowDefinition,
    WorkflowRoutingRule,
    WorkflowStepDefinition,
    WorkflowTransitionDefinition,
    WorkflowType,
    WorkflowVersion,
    WorkflowVersionStatus,
)
from .validators import validate_configuration_payload, validate_workflow_version


def _authorize(
    *, actor: User, organization: Organization, permission: BusinessPermissionCode
) -> None:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        message="اجازه مدیریت گردش‌کارهای این شرکت را ندارید.",
    )


def _lock_tenant_version(
    *, organization: Organization, version_id: object
) -> WorkflowVersion:
    try:
        return (
            WorkflowVersion.objects.select_for_update()
            .select_related("definition__workflow_type")
            .get(pk=version_id, organization=organization)
        )
    except (WorkflowVersion.DoesNotExist, ValueError) as exc:
        raise PermissionDenied("نسخه گردش‌کار در این شرکت یافت نشد.") from exc


@transaction.atomic
def create_workflow_draft(
    *,
    actor: User,
    organization: Organization,
    workflow_type_code: str,
    code: str,
    name: str,
    scope: dict[str, Any] | None = None,
    description: str = "",
    change_summary: str = "",
) -> WorkflowVersion:
    _authorize(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.WORKFLOWS_CREATE,
    )
    try:
        workflow_type = WorkflowType.objects.get(
            code=workflow_type_code, is_active=True
        )
    except WorkflowType.DoesNotExist as exc:
        raise ValidationError("نوع گردش‌کار فعال و ثبت‌شده نیست.") from exc
    definition = WorkflowDefinition(
        organization=organization,
        workflow_type=workflow_type,
        code=code,
        name=name,
        description=description,
        scope=scope or {},
        created_by=actor,
        updated_by=actor,
    )
    definition.save()
    version = WorkflowVersion.objects.create(
        organization=organization,
        definition=definition,
        version_number=1,
        change_summary=change_summary,
    )
    record_audit_event(
        action=AuditAction.WORKFLOW_DEFINITION_CREATED,
        entity_type="workflows.WorkflowDefinition",
        entity_id=str(definition.pk),
        organization=organization,
        actor=actor,
        metadata={"workflow_type": workflow_type.code, "version": 1},
    )
    return version


@transaction.atomic
def create_draft_version(
    *,
    actor: User,
    organization: Organization,
    definition_id: object,
    change_summary: str = "",
) -> WorkflowVersion:
    _authorize(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.WORKFLOWS_CHANGE_DRAFT,
    )
    try:
        definition = WorkflowDefinition.objects.select_for_update().get(
            pk=definition_id, organization=organization
        )
    except (WorkflowDefinition.DoesNotExist, ValueError) as exc:
        raise PermissionDenied("تعریف گردش‌کار در این شرکت یافت نشد.") from exc
    if definition.versions.filter(status=WorkflowVersionStatus.DRAFT).exists():
        raise ValidationError("این تعریف هم‌اکنون نسخه پیش‌نویس دارد.")
    number = (
        definition.versions.aggregate(value=Max("version_number"))["value"] or 0
    ) + 1
    return WorkflowVersion.objects.create(
        organization=organization,
        definition=definition,
        version_number=number,
        change_summary=change_summary,
    )


@transaction.atomic
def edit_workflow_draft(
    *,
    actor: User,
    organization: Organization,
    version_id: object,
    configuration: dict[str, Any],
    change_summary: str | None = None,
) -> WorkflowVersion:
    _authorize(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.WORKFLOWS_CHANGE_DRAFT,
    )
    version = _lock_tenant_version(organization=organization, version_id=version_id)
    if version.status != WorkflowVersionStatus.DRAFT:
        raise ValidationError("تنها نسخه پیش‌نویس قابل ویرایش است.")
    validate_configuration_payload(
        configuration, workflow_type_code=version.definition.workflow_type.code
    )
    version.transitions.all().delete()
    version.steps.all().delete()
    steps: dict[str, WorkflowStepDefinition] = {}
    for item in configuration.get("steps", []):
        step = WorkflowStepDefinition.objects.create(
            organization=organization,
            version=version,
            key=item["key"],
            name=item.get("name", item["key"]),
            step_type=item["step_type"],
            is_start=item.get("is_start", False),
            is_terminal=item.get("is_terminal", False),
            domain_command=item.get("domain_command", ""),
            required_permission=item.get("required_permission", ""),
            configuration=item.get("configuration", {}),
        )
        steps[step.key] = step
        for order, rule in enumerate(item.get("routing", [])):
            WorkflowRoutingRule.objects.create(
                organization=organization,
                version=version,
                step=step,
                resolver_type=rule["resolver_type"],
                configuration=rule.get("configuration", {}),
                order=rule.get("order", order),
                is_fallback=rule.get("is_fallback", False),
            )
    for item in configuration.get("transitions", []):
        transition = WorkflowTransitionDefinition.objects.create(
            organization=organization,
            version=version,
            source_step=steps[item["source"]],
            target_step=steps[item["target"]],
            outcome=item.get("outcome", "continue"),
            domain_command=item.get("domain_command", ""),
            required_permission=item.get("required_permission", ""),
            priority=item.get("priority", 0),
            is_default=item.get("is_default", False),
        )
        for order, condition in enumerate(item.get("conditions", [])):
            WorkflowCondition.objects.create(
                organization=organization,
                version=version,
                transition=transition,
                condition_type=condition["condition_type"],
                configuration=condition.get("configuration", {}),
                order=condition.get("order", order),
                negate=condition.get("negate", False),
            )
    update_values: dict[str, object] = {
        "validation_report": [],
        "validated_at": None,
        "validated_by": None,
        "updated_at": timezone.now(),
    }
    if change_summary is not None:
        update_values["change_summary"] = change_summary
    models.QuerySet.update(
        WorkflowVersion.objects.filter(pk=version.pk), **update_values
    )
    version.refresh_from_db()
    record_audit_event(
        action=AuditAction.WORKFLOW_DRAFT_UPDATED,
        entity_type="workflows.WorkflowVersion",
        entity_id=str(version.pk),
        organization=organization,
        actor=actor,
        metadata={"version": version.version_number},
    )
    return version


@transaction.atomic
def validate_workflow_draft(
    *, actor: User, organization: Organization, version_id: object
) -> list[dict[str, str]]:
    _authorize(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.WORKFLOWS_CHANGE_DRAFT,
    )
    version = _lock_tenant_version(organization=organization, version_id=version_id)
    if version.status != WorkflowVersionStatus.DRAFT:
        raise ValidationError("تنها نسخه پیش‌نویس قابل اعتبارسنجی است.")
    issues = validate_workflow_version(version)
    report = [issue.as_dict() for issue in issues]
    models.QuerySet.update(
        WorkflowVersion.objects.filter(pk=version.pk),
        validation_report=report,
        validated_at=timezone.now(),
        validated_by=actor,
        updated_at=timezone.now(),
    )
    record_audit_event(
        action=AuditAction.WORKFLOW_DEFINITION_VALIDATED,
        entity_type="workflows.WorkflowVersion",
        entity_id=str(version.pk),
        organization=organization,
        actor=actor,
        metadata={
            "version": version.version_number,
            "valid": not report,
            "error_count": len(report),
        },
    )
    return report


def _publish_locked(*, version: WorkflowVersion, actor: User) -> WorkflowVersion:
    issues = validate_workflow_version(version)
    if issues:
        raise ValidationError([issue.message for issue in issues])
    now = timezone.now()
    try:
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
    except IntegrityError as exc:
        raise ValidationError("نسخه منتشرشده رقیب برای این تعریف وجود دارد.") from exc
    version.refresh_from_db()
    record_audit_event(
        action=AuditAction.WORKFLOW_VERSION_PUBLISHED,
        entity_type="workflows.WorkflowVersion",
        entity_id=str(version.pk),
        organization=version.organization,
        actor=actor,
        metadata={"version": version.version_number},
    )
    return version


@transaction.atomic
def publish_workflow_version(
    *, actor: User, organization: Organization, version_id: object
) -> WorkflowVersion:
    _authorize(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.WORKFLOWS_PUBLISH,
    )
    version = _lock_tenant_version(organization=organization, version_id=version_id)
    Organization.objects.select_for_update().get(pk=organization.pk)
    if version.status != WorkflowVersionStatus.DRAFT:
        raise ValidationError("تنها نسخه پیش‌نویس قابل انتشار است.")
    if version.definition.versions.filter(
        status=WorkflowVersionStatus.PUBLISHED
    ).exists():
        raise ValidationError("برای جایگزینی نسخه منتشرشده از supersede استفاده کنید.")
    return _publish_locked(version=version, actor=actor)


@transaction.atomic
def retire_workflow_version(
    *, actor: User, organization: Organization, version_id: object, reason: str
) -> WorkflowVersion:
    _authorize(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.WORKFLOWS_RETIRE,
    )
    if not reason.strip():
        raise ValidationError("دلیل بازنشستگی الزامی است.")
    version = _lock_tenant_version(organization=organization, version_id=version_id)
    if version.status != WorkflowVersionStatus.PUBLISHED:
        raise ValidationError("تنها نسخه منتشرشده قابل بازنشستگی است.")
    now = timezone.now()
    models.QuerySet.update(
        WorkflowVersion.objects.filter(pk=version.pk),
        status=WorkflowVersionStatus.RETIRED,
        retired_at=now,
        retired_by=actor,
        updated_at=now,
    )
    version.refresh_from_db()
    record_audit_event(
        action=AuditAction.WORKFLOW_VERSION_RETIRED,
        entity_type="workflows.WorkflowVersion",
        entity_id=str(version.pk),
        organization=organization,
        actor=actor,
        metadata={"version": version.version_number, "reason": reason.strip()},
    )
    return version


@transaction.atomic
def supersede_workflow_version(
    *,
    actor: User,
    organization: Organization,
    new_version_id: object,
    replaced_version_id: object,
    reason: str,
) -> WorkflowVersion:
    _authorize(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.WORKFLOWS_PUBLISH,
    )
    if not reason.strip():
        raise ValidationError("دلیل جایگزینی الزامی است.")
    Organization.objects.select_for_update().get(pk=organization.pk)
    locked_versions = list(
        WorkflowVersion.objects.select_for_update()
        .select_related("definition__workflow_type")
        .filter(pk__in=[new_version_id, replaced_version_id], organization=organization)
        .order_by("pk")
    )
    locked = {str(item.pk): item for item in locked_versions}
    try:
        new_version = locked[str(new_version_id)]
        replaced = locked[str(replaced_version_id)]
    except KeyError as exc:
        raise PermissionDenied("نسخه گردش‌کار در این شرکت یافت نشد.") from exc
    if new_version.definition_id != replaced.definition_id:
        raise ValidationError("نسخه جایگزین باید متعلق به همان تعریف باشد.")
    if (
        new_version.status != WorkflowVersionStatus.DRAFT
        or replaced.status != WorkflowVersionStatus.PUBLISHED
    ):
        raise ValidationError("وضعیت نسخه‌های جایگزینی معتبر نیست.")
    issues = validate_workflow_version(new_version)
    if issues:
        raise ValidationError([issue.message for issue in issues])
    now = timezone.now()
    models.QuerySet.update(
        WorkflowVersion.objects.filter(pk=replaced.pk),
        status=WorkflowVersionStatus.RETIRED,
        retired_at=now,
        retired_by=actor,
        updated_at=now,
    )
    record_audit_event(
        action=AuditAction.WORKFLOW_VERSION_RETIRED,
        entity_type="workflows.WorkflowVersion",
        entity_id=str(replaced.pk),
        organization=organization,
        actor=actor,
        metadata={
            "version": replaced.version_number,
            "reason": reason.strip(),
            "superseded": True,
        },
    )
    return _publish_locked(version=new_version, actor=actor)
