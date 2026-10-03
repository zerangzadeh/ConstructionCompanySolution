from typing import ClassVar

from django.db import migrations

WORKFLOWS = (
    (
        "billing.taxpayer_invoice_approval",
        "billing.taxpayer_invoice",
        "تأیید صورتحساب مؤدیان",
        "taxpayer_invoice_approval_p6_s26_s32",
        "taxpayer_invoices.approve",
        "billing.taxpayer_invoice",
    ),
    (
        "billing.contractor_compliance_approval",
        "billing.contractor_compliance_assessment",
        "تأیید ارزیابی انطباق بیمه پیمانکار",
        "contractor_compliance_approval_p6_s26_s32",
        "contractor_compliance.approve",
        "billing.contractor_compliance_assessment",
    ),
)


def seed_catalog(apps, schema_editor):
    del schema_editor
    WorkflowType = apps.get_model("workflows", "WorkflowType")
    WorkflowTemplate = apps.get_model("workflows", "WorkflowTemplate")
    OrganizationRole = apps.get_model("organizations", "OrganizationRole")
    BusinessPermission = apps.get_model("organizations", "BusinessPermission")
    for type_code, subject_type, name, template_code, permission, prefix in WORKFLOWS:
        workflow_type, _ = WorkflowType.objects.update_or_create(
            code=type_code,
            defaults={
                "name": name,
                "description": f"{name} با جداسازی قطعی تهیه‌کننده و تأییدکننده.",
                "subject_type": subject_type,
                "subject_adapter": subject_type,
                "allowed_scope_fields": ["project_id", "contract_id"],
                "is_active": True,
            },
        )
        configuration = {
            "steps": [
                {
                    "key": "start",
                    "name": "شروع",
                    "step_type": "start",
                    "is_start": True,
                },
                {
                    "key": "approval",
                    "name": name,
                    "step_type": "approval",
                    "configuration": {
                        "decision_policy": "any",
                        "exclude_submitter": True,
                        "allow_submitter_if_no_other_candidate": False,
                    },
                    "routing": [
                        {
                            "resolver_type": "submitter_primary_position_manager",
                            "configuration": {"permission": permission},
                        },
                        {
                            "resolver_type": "business_permission",
                            "configuration": {
                                "permission": permission,
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
                    "domain_command": f"{prefix}.approve",
                    "required_permission": permission,
                },
                {
                    "source": "approval",
                    "target": "returned",
                    "outcome": "returned",
                    "domain_command": f"{prefix}.return",
                    "required_permission": permission,
                },
            ],
        }
        WorkflowTemplate.objects.update_or_create(
            workflow_type=workflow_type,
            code=template_code,
            defaults={
                "name": f"{name} P6-S26–S32",
                "description": "مسیر پایه با جداسازی قطعی تهیه‌کننده و تأییدکننده.",
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
            permissions__code=permission
        ).distinct():
            role.permissions.add(*runtime_permissions)


class Migration(migrations.Migration):
    dependencies: ClassVar[list] = [
        ("billing", "0013_contractorcomplianceassessment_and_more"),
        ("organizations", "0087_p6_s26_s32_statutory_permissions"),
        ("workflows", "0025_p6_s21_s25_commercial_control_catalog"),
    ]
    operations: ClassVar[list] = [
        migrations.RunPython(seed_catalog, migrations.RunPython.noop)
    ]
