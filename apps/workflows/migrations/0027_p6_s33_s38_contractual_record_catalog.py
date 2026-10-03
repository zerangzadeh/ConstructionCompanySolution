from typing import ClassVar

from django.db import migrations

WORKFLOW_TYPE = "contracts.contractual_record_approval"
SUBJECT_TYPE = "contracts.contractual_record"
TEMPLATE_CODE = "contractual_record_approval_p6_s33_s38"
APPROVE_PERMISSION = "contractual_records.approve"


def seed_catalog(apps, schema_editor):
    del schema_editor
    WorkflowType = apps.get_model("workflows", "WorkflowType")
    WorkflowTemplate = apps.get_model("workflows", "WorkflowTemplate")
    OrganizationRole = apps.get_model("organizations", "OrganizationRole")
    BusinessPermission = apps.get_model("organizations", "BusinessPermission")
    workflow_type, _ = WorkflowType.objects.update_or_create(
        code=WORKFLOW_TYPE,
        defaults={
            "name": "تأیید رکورد قراردادی",
            "description": "تصمیم صریح استحقاق و آثار قراردادی بدون اثر خودکار.",
            "subject_type": SUBJECT_TYPE,
            "subject_adapter": SUBJECT_TYPE,
            "allowed_scope_fields": ["project_id", "contract_id"],
            "is_active": True,
        },
    )
    configuration = {
        "steps": [
            {"key": "start", "name": "شروع", "step_type": "start", "is_start": True},
            {
                "key": "approval",
                "name": "تصمیم رکورد قراردادی",
                "step_type": "approval",
                "configuration": {
                    "decision_policy": "any",
                    "exclude_submitter": True,
                    "allow_submitter_if_no_other_candidate": False,
                },
                "routing": [
                    {
                        "resolver_type": "submitter_primary_position_manager",
                        "configuration": {"permission": APPROVE_PERMISSION},
                    },
                    {
                        "resolver_type": "business_permission",
                        "configuration": {
                            "permission": APPROVE_PERMISSION,
                            "exclude_submitter_unless_no_other": False,
                        },
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
                "key": "returned",
                "name": "بازگردانده‌شده",
                "step_type": "end",
                "is_terminal": True,
            },
        ],
        "transitions": [
            {
                "source": "start",
                "target": "approval",
                "outcome": "requested",
                "is_default": True,
            },
            {
                "source": "approval",
                "target": "approved",
                "outcome": "approved",
                "domain_command": "contracts.contractual_record.approve",
                "required_permission": APPROVE_PERMISSION,
            },
            {
                "source": "approval",
                "target": "returned",
                "outcome": "returned",
                "domain_command": "contracts.contractual_record.return",
                "required_permission": APPROVE_PERMISSION,
            },
        ],
    }
    WorkflowTemplate.objects.update_or_create(
        workflow_type=workflow_type,
        code=TEMPLATE_CODE,
        defaults={
            "name": "تأیید رکورد قراردادی P6-S33–S38",
            "description": "مسیر پایه با جداسازی قطعی ارسال‌کننده و تأییدکننده.",
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
        permissions__code=APPROVE_PERMISSION
    ).distinct():
        role.permissions.add(*runtime_permissions)


class Migration(migrations.Migration):
    dependencies: ClassVar[list] = [
        ("contracts", "0008_contractualrecord_contractualrecordevidence_and_more"),
        ("organizations", "0089_p6_s33_s38_contractual_record_permissions"),
        ("workflows", "0026_p6_s26_s32_statutory_catalog"),
    ]
    operations: ClassVar[list] = [
        migrations.RunPython(seed_catalog, migrations.RunPython.noop)
    ]
