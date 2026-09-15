from hashlib import sha256

from django.db import migrations
from django.utils import timezone


WORKFLOW_TYPE_CODE = "procurement.purchase_request_approval"
SUBJECT_TYPE = "procurement.purchase_request"
TEMPLATE_CODE = "purchase_request_legacy_compatibility"
DEFINITION_CODE = "purchase-request-legacy-compatibility"


def _key(*parts):
    return sha256(":".join(str(part) for part in parts).encode()).hexdigest()


def _configuration():
    return {
        "steps": [
            {"key": "start", "name": "شروع", "step_type": "start", "is_start": True},
            {
                "key": "legacy_decision",
                "name": "تصمیم سازگار با خرید",
                "step_type": "approval",
                "configuration": {"decision_policy": "any"},
                "routing": [
                    {
                        "resolver_type": "business_permission",
                        "configuration": {"permission": "purchase_requests.approve"},
                    },
                    {
                        "resolver_type": "business_permission",
                        "configuration": {"permission": "purchase_requests.reject"},
                    },
                    {
                        "resolver_type": "organization_owner",
                        "configuration": {},
                        "is_fallback": True,
                    },
                ],
            },
            {
                "key": "approved",
                "name": "تأییدشده",
                "step_type": "end",
                "is_terminal": True,
            },
            {
                "key": "rejected",
                "name": "ردشده",
                "step_type": "end",
                "is_terminal": True,
            },
        ],
        "transitions": [
            {
                "source": "start",
                "target": "legacy_decision",
                "outcome": "submitted",
                "is_default": True,
            },
            {
                "source": "legacy_decision",
                "target": "approved",
                "outcome": "approved",
                "domain_command": "procurement.purchase_request.approve",
                "required_permission": "purchase_requests.approve",
            },
            {
                "source": "legacy_decision",
                "target": "rejected",
                "outcome": "rejected",
                "domain_command": "procurement.purchase_request.reject",
                "required_permission": "purchase_requests.reject",
            },
        ],
    }


def _create_version(apps, organization, actor_id, workflow_type, configuration):
    WorkflowDefinition = apps.get_model("workflows", "WorkflowDefinition")
    WorkflowVersion = apps.get_model("workflows", "WorkflowVersion")
    WorkflowStepDefinition = apps.get_model("workflows", "WorkflowStepDefinition")
    WorkflowRoutingRule = apps.get_model("workflows", "WorkflowRoutingRule")
    WorkflowTransitionDefinition = apps.get_model(
        "workflows", "WorkflowTransitionDefinition"
    )
    scope_key = sha256(b"{}").hexdigest()
    existing = WorkflowVersion.objects.filter(
        organization=organization,
        definition__workflow_type=workflow_type,
        definition__scope_key=scope_key,
        status="published",
    ).first()
    if existing:
        if (
            existing.definition.code == DEFINITION_CODE
            and existing.steps.filter(key="legacy_decision").exists()
        ):
            return existing
        return None
    definition, created = WorkflowDefinition.objects.get_or_create(
        organization=organization,
        workflow_type=workflow_type,
        scope_key=scope_key,
        defaults={
            "code": DEFINITION_CODE,
            "name": "سازگاری تأیید درخواست خرید",
            "description": "رفتار تک‌تصمیمی پیش از W3 را حفظ می‌کند.",
            "scope": {},
            "created_by_id": actor_id,
            "updated_by_id": actor_id,
        },
    )
    if not created:
        return None
    now = timezone.now()
    version = WorkflowVersion.objects.create(
        organization=organization,
        definition=definition,
        version_number=1,
        status="draft",
        change_summary="W3 legacy compatibility",
    )
    steps = {}
    for item in configuration["steps"]:
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
        for order, route in enumerate(item.get("routing", [])):
            WorkflowRoutingRule.objects.create(
                organization=organization,
                version=version,
                step=step,
                resolver_type=route["resolver_type"],
                configuration=route.get("configuration", {}),
                order=route.get("order", order),
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
            priority=item.get("priority", 0),
            is_default=item.get("is_default", False),
        )
    WorkflowVersion.objects.filter(pk=version.pk).update(
        status="published",
        validation_report=[],
        validated_at=now,
        validated_by_id=actor_id,
        published_at=now,
        published_by_id=actor_id,
        updated_at=now,
    )
    version.refresh_from_db()
    return version


def _actor_membership(apps, organization, user_id=None, permission=None):
    OrganizationMembership = apps.get_model("organizations", "OrganizationMembership")
    memberships = OrganizationMembership.objects.filter(
        organization=organization,
        status="active",
        role_definition__is_active=True,
        user__is_active=True,
    )
    if user_id:
        preferred_memberships = memberships.filter(user_id=user_id)
        if permission:
            preferred_memberships = preferred_memberships.filter(
                role_definition__permissions__code=permission,
                role_definition__permissions__is_active=True,
            )
        preferred = preferred_memberships.first()
        if preferred:
            return preferred
    return memberships.filter(role_definition__is_owner=True).first()


def _backfill_request(apps, purchase_request, version, actor_membership):
    WorkflowInstance = apps.get_model("workflows", "WorkflowInstance")
    WorkflowStepInstance = apps.get_model("workflows", "WorkflowStepInstance")
    WorkItem = apps.get_model("workflows", "WorkItem")
    WorkItemCandidate = apps.get_model("workflows", "WorkItemCandidate")
    OrganizationMembership = apps.get_model("organizations", "OrganizationMembership")
    existing = WorkflowInstance.objects.filter(
        organization=purchase_request.organization,
        subject_type=SUBJECT_TYPE,
        subject_id=purchase_request.pk,
    ).first()
    if existing:
        return
    now = timezone.now()
    creator_membership = _actor_membership(
        apps, purchase_request.organization, purchase_request.created_by_id
    )
    submitter_membership = _actor_membership(
        apps, purchase_request.organization, purchase_request.updated_by_id
    )
    instance = WorkflowInstance.objects.create(
        organization=purchase_request.organization,
        definition=version.definition,
        version=version,
        subject_type=SUBJECT_TYPE,
        subject_id=purchase_request.pk,
        subject_context={
            "project_id": str(purchase_request.project_id),
            "status": purchase_request.status,
            "created_by_id": str(purchase_request.created_by_id),
            "creator_membership_id": (
                str(creator_membership.pk) if creator_membership else None
            ),
            "submitter_membership_id": (
                str(submitter_membership.pk) if submitter_membership else None
            ),
            "starter_membership_id": str(actor_membership.pk),
            "subject_display": purchase_request.request_number,
        },
        idempotency_key=_key(WORKFLOW_TYPE_CODE, purchase_request.pk, "start"),
        started_by=actor_membership,
    )
    start = version.steps.get(key="start")
    decision = version.steps.get(key="legacy_decision")
    WorkflowStepInstance.objects.create(
        organization=purchase_request.organization,
        instance=instance,
        step_definition=start,
        sequence=1,
        status="completed",
        completed_at=now,
        outcome="submitted",
    )
    step_instance = WorkflowStepInstance.objects.create(
        organization=purchase_request.organization,
        instance=instance,
        step_definition=decision,
        sequence=2,
        status="active",
    )
    work_item = WorkItem.objects.create(
        organization=purchase_request.organization,
        instance=instance,
        step_instance=step_instance,
        action_key="legacy_decision",
        status="open",
        required_permission="",
        routing_basis=[{"resolver": "business_permission", "backfill": "true"}],
        idempotency_key=_key(instance.pk, step_instance.pk, "legacy_decision"),
    )
    candidates = OrganizationMembership.objects.filter(
        organization=purchase_request.organization,
        status="active",
        role_definition__is_active=True,
        user__is_active=True,
        role_definition__permissions__code__in=(
            "purchase_requests.approve",
            "purchase_requests.reject",
        ),
        role_definition__permissions__is_active=True,
    ).distinct()
    for membership in candidates:
        WorkItemCandidate.objects.get_or_create(
            organization=purchase_request.organization,
            work_item=work_item,
            membership=membership,
            is_active=True,
            defaults={"routing_basis": work_item.routing_basis},
        )


def seed_and_backfill(apps, schema_editor):
    del schema_editor
    WorkflowType = apps.get_model("workflows", "WorkflowType")
    WorkflowTemplate = apps.get_model("workflows", "WorkflowTemplate")
    Organization = apps.get_model("organizations", "Organization")
    OrganizationRole = apps.get_model("organizations", "OrganizationRole")
    BusinessPermission = apps.get_model("organizations", "BusinessPermission")
    PurchaseRequest = apps.get_model("procurement", "PurchaseRequest")
    workflow_type = WorkflowType.objects.get(code=WORKFLOW_TYPE_CODE)
    configuration = _configuration()
    WorkflowTemplate.objects.update_or_create(
        workflow_type=workflow_type,
        code=TEMPLATE_CODE,
        defaults={
            "name": "سازگاری گردش تأیید درخواست خرید",
            "description": "رفتار draft → submitted → approved/rejected موجود را حفظ می‌کند.",
            "configuration": configuration,
            "is_active": True,
        },
    )
    WorkflowTemplate.objects.filter(
        workflow_type=workflow_type, code="small_tenant_owner_approval"
    ).update(is_active=False)
    runtime_permissions = list(
        BusinessPermission.objects.filter(
            code__in=("work_items.view", "work_items.claim", "work_items.act")
        )
    )
    for role in OrganizationRole.objects.filter(
        permissions__code__in=(
            "purchase_requests.approve",
            "purchase_requests.reject",
        )
    ).distinct():
        role.permissions.add(*runtime_permissions)
    versions = {}
    for organization in Organization.objects.all().iterator():
        actor_membership = _actor_membership(
            apps, organization, getattr(organization, "created_by_id", None)
        )
        if actor_membership is None:
            continue
        version = _create_version(
            apps,
            organization,
            actor_membership.user_id,
            workflow_type,
            configuration,
        )
        if version is not None:
            versions[organization.pk] = (version, actor_membership)
    for purchase_request in PurchaseRequest.objects.filter(
        status="submitted"
    ).iterator():
        pair = versions.get(purchase_request.organization_id)
        if pair is None:
            continue
        version, default_actor = pair
        actor_membership = (
            _actor_membership(
                apps,
                purchase_request.organization,
                purchase_request.updated_by_id,
                "purchase_requests.submit",
            )
            or default_actor
        )
        _backfill_request(apps, purchase_request, version, actor_membership)


class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0023_workflow_runtime_permissions"),
        ("procurement", "0002_alter_goodsreceipt_options_and_more"),
        ("workflows", "0009_runtime_tenant_and_immutability_guards"),
    ]

    operations = [migrations.RunPython(seed_and_backfill, migrations.RunPython.noop)]
