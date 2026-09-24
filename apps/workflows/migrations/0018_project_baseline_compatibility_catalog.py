from django.db import migrations


def seed_project_baseline_catalog(apps, schema_editor):
    del schema_editor
    WorkflowType = apps.get_model("workflows", "WorkflowType")
    WorkflowTemplate = apps.get_model("workflows", "WorkflowTemplate")
    OrganizationRole = apps.get_model("organizations", "OrganizationRole")
    BusinessPermission = apps.get_model("organizations", "BusinessPermission")
    permission = "baselines.approve"
    workflow_type, _ = WorkflowType.objects.update_or_create(
        code="billing.project_baseline_approval",
        defaults={
            "name": "تأیید مبنای تجاری پروژه",
            "description": "تأیید مبنای تجاری کاملاً قیمت‌گذاری‌شده پروژه.",
            "subject_type": "billing.project_baseline",
            "subject_adapter": "billing.project_baseline",
            "allowed_scope_fields": ["project_id", "contract_id"],
            "is_active": True,
        },
    )
    configuration = {
        "steps": [
            {"key": "start", "name": "شروع", "step_type": "start", "is_start": True},
            {
                "key": "approval",
                "name": "تأیید مبنای تجاری",
                "step_type": "approval",
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
            {"source": "start", "target": "approval", "outcome": "requested", "is_default": True},
            {
                "source": "approval",
                "target": "approved",
                "outcome": "approved",
                "domain_command": "billing.project_baseline.approve",
                "required_permission": permission,
            },
        ],
    }
    WorkflowTemplate.objects.update_or_create(
        workflow_type=workflow_type,
        code="project_baseline_f61",
        defaults={
            "name": "تأیید مبنای تجاری پروژه",
            "description": "مسیر تک‌مرحله‌ای مناسب سازمان‌های کوچک.",
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
    dependencies = [
        ("billing", "0001_initial"),
        ("organizations", "0025_baseline_permissions"),
        ("workflows", "0017_equipment_maintenance_compatibility_catalog"),
    ]

    operations = [migrations.RunPython(seed_project_baseline_catalog, migrations.RunPython.noop)]
