from django.db import migrations


def seed_w57_equipment_maintenance_catalog(apps, schema_editor):
    del schema_editor
    WorkflowType = apps.get_model("workflows", "WorkflowType")
    WorkflowTemplate = apps.get_model("workflows", "WorkflowTemplate")
    OrganizationRole = apps.get_model("organizations", "OrganizationRole")
    BusinessPermission = apps.get_model("organizations", "BusinessPermission")
    permission = "maintenance_records.transition"
    workflow_type, _ = WorkflowType.objects.update_or_create(
        code="equipment.maintenance_record_lifecycle",
        defaults={
            "name": "چرخه سرویس و تعمیر تجهیز",
            "description": "چرخه اقدام‌پذیر سرویس، تعمیر و بازرسی تجهیزات.",
            "subject_type": "equipment.maintenance_record",
            "subject_adapter": "equipment.maintenance_record",
            "allowed_scope_fields": ["project_id", "site_id", "maintenance_type"],
            "is_active": True,
        },
    )
    configuration = {
        "steps": [
            {"key": "start", "name": "شروع", "step_type": "start", "is_start": True},
            {
                "key": "scheduled",
                "name": "شروع یا لغو سرویس",
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
                "key": "in_progress",
                "name": "تکمیل یا لغو سرویس",
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
                "key": "completed",
                "name": "تکمیل‌شده",
                "step_type": "end",
                "is_terminal": True,
            },
            {
                "key": "cancelled",
                "name": "لغوشده",
                "step_type": "end",
                "is_terminal": True,
            },
        ],
        "transitions": [
            {
                "source": "start",
                "target": "scheduled",
                "outcome": "requested",
                "is_default": True,
            },
            {
                "source": "scheduled",
                "target": "in_progress",
                "outcome": "in_progress",
                "domain_command": "equipment.maintenance_record.start",
                "required_permission": permission,
            },
            {
                "source": "scheduled",
                "target": "completed",
                "outcome": "completed",
                "domain_command": "equipment.maintenance_record.complete",
                "required_permission": permission,
            },
            {
                "source": "scheduled",
                "target": "cancelled",
                "outcome": "cancelled",
                "domain_command": "equipment.maintenance_record.cancel",
                "required_permission": permission,
            },
            {
                "source": "in_progress",
                "target": "completed",
                "outcome": "completed",
                "domain_command": "equipment.maintenance_record.complete",
                "required_permission": permission,
            },
            {
                "source": "in_progress",
                "target": "cancelled",
                "outcome": "cancelled",
                "domain_command": "equipment.maintenance_record.cancel",
                "required_permission": permission,
            },
        ],
    }
    WorkflowTemplate.objects.update_or_create(
        workflow_type=workflow_type,
        code="maintenance_record_lifecycle_legacy_compatibility",
        defaults={
            "name": "سازگاری چرخه سرویس و تعمیر تجهیز",
            "description": "سازگاری با lifecycle فعلی نگهداری تجهیزات.",
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
    dependencies = [  # noqa: RUF012
        ("equipment", "0001_initial"),
        ("workflows", "0016_inventory_stock_transaction_compatibility_catalog"),
    ]

    operations = [  # noqa: RUF012
        migrations.RunPython(
            seed_w57_equipment_maintenance_catalog, migrations.RunPython.noop
        )
    ]
