from typing import ClassVar

from django.db import migrations


def seed_payable_certificate_catalog(apps, schema_editor):
    del schema_editor
    WorkflowType = apps.get_model("workflows", "WorkflowType")
    WorkflowTemplate = apps.get_model("workflows", "WorkflowTemplate")
    OrganizationRole = apps.get_model("organizations", "OrganizationRole")
    BusinessPermission = apps.get_model("organizations", "BusinessPermission")
    approval_permission = "payable_certificates.approve"
    workflow_type, _ = WorkflowType.objects.update_or_create(
        code="billing.payable_certificate_approval",
        defaults={
            "name": "تأیید گواهی پرداخت پیمان جزء",
            "description": "تأیید یا بازگردانی نسخه ارسالی گواهی پرداخت.",
            "subject_type": "billing.payable_certificate",
            "subject_adapter": "billing.payable_certificate",
            "allowed_scope_fields": ["project_id", "contract_id"],
            "is_active": True,
        },
    )
    configuration = {
        "steps": [
            {"key": "start", "name": "شروع", "step_type": "start", "is_start": True},
            {
                "key": "approval",
                "name": "تأیید گواهی پرداخت",
                "step_type": "approval",
                "configuration": {
                    "decision_policy": "any",
                    "exclude_submitter": True,
                    "allow_submitter_if_no_other_candidate": False,
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
                "domain_command": "billing.payable_certificate.approve",
                "required_permission": approval_permission,
            },
            {
                "source": "approval",
                "target": "returned",
                "outcome": "returned",
                "domain_command": "billing.payable_certificate.return",
                "required_permission": approval_permission,
            },
        ],
    }
    WorkflowTemplate.objects.update_or_create(
        workflow_type=workflow_type,
        code="payable_certificate_approval_p6_s14_s20",
        defaults={
            "name": "تأیید گواهی پرداخت P6-S14–S20",
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
        permissions__code=approval_permission
    ).distinct():
        role.permissions.add(*runtime_permissions)


class Migration(migrations.Migration):
    dependencies: ClassVar[list] = [
        ("billing", "0011_payablecertificate_payablecertificateadjustment_and_more"),
        ("organizations", "0085_p6_s14_s20_payable_permissions"),
        ("workflows", "0023_p1_1_remove_deferred_self_approval"),
    ]

    operations: ClassVar[list] = [
        migrations.RunPython(
            seed_payable_certificate_catalog, migrations.RunPython.noop
        )
    ]
