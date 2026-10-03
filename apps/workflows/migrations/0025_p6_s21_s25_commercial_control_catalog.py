from typing import ClassVar

from django.db import migrations

WORKFLOWS = (
    (
        "billing.guarantee_approval",
        "billing.contract_guarantee",
        "تأیید ضمانت‌نامه قراردادی",
        "guarantee_approval_p6_s21_s25",
        "guarantees.approve",
        "billing.contract_guarantee",
    ),
    (
        "billing.compliance_evidence_approval",
        "billing.contract_compliance_evidence",
        "تأیید شاهد بیمه و مفاصاحساب",
        "compliance_evidence_approval_p6_s21_s25",
        "compliance_evidence.approve",
        "billing.contract_compliance_evidence",
    ),
    (
        "billing.retention_release_approval",
        "billing.retention_release",
        "تأیید آزادسازی کسور تضمین",
        "retention_release_approval_p6_s21_s25",
        "retention_releases.approve",
        "billing.retention_release",
    ),
)


def seed_catalog(apps, schema_editor):
    del schema_editor
    WorkflowType = apps.get_model("workflows", "WorkflowType")
    WorkflowTemplate = apps.get_model("workflows", "WorkflowTemplate")
    OrganizationRole = apps.get_model("organizations", "OrganizationRole")
    BusinessPermission = apps.get_model("organizations", "BusinessPermission")
    for (
        type_code,
        subject_type,
        name,
        template_code,
        permission,
        command_prefix,
    ) in WORKFLOWS:
        workflow_type, _ = WorkflowType.objects.update_or_create(
            code=type_code,
            defaults={
                "name": name,
                "description": f"{name} با جداسازی تهیه‌کننده و تأییدکننده.",
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
                    "domain_command": f"{command_prefix}.approve",
                    "required_permission": permission,
                },
                {
                    "source": "approval",
                    "target": "returned",
                    "outcome": "returned",
                    "domain_command": f"{command_prefix}.return",
                    "required_permission": permission,
                },
            ],
        }
        WorkflowTemplate.objects.update_or_create(
            workflow_type=workflow_type,
            code=template_code,
            defaults={
                "name": f"{name} P6-S21–S25",
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
        ("billing", "0012_p6_s21_s25_commercial_controls"),
        ("organizations", "0086_p6_s21_s25_commercial_control_permissions"),
        ("workflows", "0024_p6_s14_s20_payable_certificate_catalog"),
    ]
    operations: ClassVar[list] = [
        migrations.RunPython(seed_catalog, migrations.RunPython.noop)
    ]
