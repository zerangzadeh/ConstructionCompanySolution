from django.db import migrations


def seed_w54_catalog(apps, schema_editor):
    del schema_editor
    WorkflowType = apps.get_model("workflows", "WorkflowType")
    WorkflowTemplate = apps.get_model("workflows", "WorkflowTemplate")
    OrganizationRole = apps.get_model("organizations", "OrganizationRole")
    BusinessPermission = apps.get_model("organizations", "BusinessPermission")
    definitions = (
        (
            "estimates.estimate_approval",
            "تأیید برآورد",
            "تأیید برآورد و بازنگری جاری.",
            "estimates.estimate",
            "estimates.estimate",
            ["project_id", "phase_id", "contract_id"],
            "estimate_legacy_compatibility",
            "سازگاری تأیید برآورد",
            "تأیید تک‌مرحله‌ای برآورد را حفظ می‌کند.",
            "estimates.approve",
            "estimates.estimate.approve",
        ),
        (
            "contracts.contract_amendment_approval",
            "تأیید الحاقیه قرارداد",
            "تأیید الحاقیه تغییرناپذیر قرارداد.",
            "contracts.contract_amendment",
            "contracts.contract_amendment",
            ["project_id", "contract_id"],
            "contract_amendment_legacy_compatibility",
            "سازگاری تأیید الحاقیه",
            "تأیید تک‌مرحله‌ای الحاقیه را حفظ می‌کند.",
            "contract_amendments.approve",
            "contracts.contract_amendment.approve",
        ),
    )
    runtime_permissions = list(
        BusinessPermission.objects.filter(
            code__in=("work_items.view", "work_items.claim", "work_items.act")
        )
    )
    for (
        code,
        name,
        description,
        subject_type,
        adapter,
        scopes,
        template_code,
        template_name,
        template_description,
        permission,
        command,
    ) in definitions:
        workflow_type, _ = WorkflowType.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "description": description,
                "subject_type": subject_type,
                "subject_adapter": adapter,
                "allowed_scope_fields": scopes,
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
                    "required_permission": permission,
                    "configuration": {"decision_policy": "any"},
                    "routing": [
                        {
                            "resolver_type": "business_permission",
                            "configuration": {"permission": permission},
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
                    "domain_command": command,
                    "required_permission": permission,
                },
            ],
        }
        WorkflowTemplate.objects.update_or_create(
            workflow_type=workflow_type,
            code=template_code,
            defaults={
                "name": template_name,
                "description": template_description,
                "is_active": True,
                "configuration": configuration,
            },
        )
        for role in OrganizationRole.objects.filter(
            permissions__code=permission
        ).distinct():
            role.permissions.add(*runtime_permissions)


class Migration(migrations.Migration):
    dependencies = [
        ("contracts", "0003_alter_contract_options_and_more"),
        (
            "estimates",
            "0003_alter_estimate_options_alter_estimateitem_options_and_more",
        ),
        ("workflows", "0014_quality_compatibility_catalog"),
    ]

    operations = [migrations.RunPython(seed_w54_catalog, migrations.RunPython.noop)]
