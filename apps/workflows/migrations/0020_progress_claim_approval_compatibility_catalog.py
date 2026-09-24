from django.db import migrations


def seed_progress_claim_catalog(apps, schema_editor):
    del schema_editor
    WorkflowType = apps.get_model("workflows", "WorkflowType")
    WorkflowTemplate = apps.get_model("workflows", "WorkflowTemplate")
    OrganizationRole = apps.get_model("organizations", "OrganizationRole")
    BusinessPermission = apps.get_model("organizations", "BusinessPermission")
    approval_permission = "claims.approve"
    workflow_type, _ = WorkflowType.objects.update_or_create(
        code="billing.progress_claim_approval",
        defaults={
            "name": "تأیید صورت‌وضعیت",
            "description": "تأیید یا بازگردانی نسخه ارسالی صورت‌وضعیت.",
            "subject_type": "billing.progress_claim",
            "subject_adapter": "billing.progress_claim",
            "allowed_scope_fields": ["project_id", "contract_id", "baseline_id"],
            "is_active": True,
        },
    )
    configuration = {
        "steps": [
            {"key": "start", "name": "شروع", "step_type": "start", "is_start": True},
            {
                "key": "approval",
                "name": "تأیید صورت‌وضعیت",
                "step_type": "approval",
                "configuration": {
                    "decision_policy": "any",
                    "exclude_submitter": True,
                    "allow_submitter_if_no_other_candidate": True,
                },
                "routing": [
                    {
                        "resolver_type": "submitter_primary_position_manager",
                        "configuration": {"permission": approval_permission},
                    },
                    {
                        "resolver_type": "business_permission",
                        "configuration": {
                            "permission": approval_permission,
                            "exclude_submitter_unless_no_other": True,
                        },
                        "is_fallback": True,
                    },
                ],
            },
            {"key": "approved", "name": "تأییدشده", "step_type": "end", "is_terminal": True},
            {"key": "returned", "name": "بازگردانده‌شده", "step_type": "end", "is_terminal": True},
        ],
        "transitions": [
            {"source": "start", "target": "approval", "outcome": "requested", "is_default": True},
            {
                "source": "approval",
                "target": "approved",
                "outcome": "approved",
                "domain_command": "billing.progress_claim.approve",
                "required_permission": approval_permission,
            },
            {
                "source": "approval",
                "target": "returned",
                "outcome": "returned",
                "domain_command": "billing.progress_claim.return",
                "required_permission": approval_permission,
            },
        ],
    }
    WorkflowTemplate.objects.update_or_create(
        workflow_type=workflow_type,
        code="progress_claim_approval_f64",
        defaults={
            "name": "تأیید صورت‌وضعیت F6.4",
            "description": "مدیر سمت بالادست، سپس مسیر کوچک‌مستأجر با جداسازی وظایف.",
            "is_active": True,
            "configuration": configuration,
        },
    )
    runtime_permissions = list(
        BusinessPermission.objects.filter(
            code__in=("work_items.view", "work_items.claim", "work_items.act")
        )
    )
    for role in OrganizationRole.objects.filter(
        permissions__code=approval_permission
    ).distinct():
        role.permissions.add(*runtime_permissions)


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0004_f64_claim_approval"),
        ("organizations", "0028_claim_approval_permissions"),
        ("workflows", "0019_progress_verification_compatibility_catalog"),
    ]

    operations = [migrations.RunPython(seed_progress_claim_catalog, migrations.RunPython.noop)]
