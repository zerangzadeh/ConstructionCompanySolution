from django.db import migrations


def seed_w56_inventory_catalog(apps, schema_editor):
    del schema_editor
    WorkflowType = apps.get_model("workflows", "WorkflowType")
    WorkflowTemplate = apps.get_model("workflows", "WorkflowTemplate")
    OrganizationRole = apps.get_model("organizations", "OrganizationRole")
    BusinessPermission = apps.get_model("organizations", "BusinessPermission")
    definitions = (
        (
            "inventory.stock_transaction_posting",
            "ثبت نهایی گردش انبار",
            "ثبت نهایی گردش انبارِ دستی با تخصیص مسئولیت.",
            "stock_transaction_posting_legacy_compatibility",
            "سازگاری ثبت نهایی گردش انبار",
            "stock_transactions.post",
            "inventory.stock_transaction.post",
            "posted",
        ),
        (
            "inventory.stock_transaction_reversal",
            "برگشت گردش انبار",
            "برگشت تغییرناپذیر گردش انبارِ دستی با تخصیص مسئولیت.",
            "stock_transaction_reversal_legacy_compatibility",
            "سازگاری برگشت گردش انبار",
            "stock_transactions.reverse",
            "inventory.stock_transaction.reverse",
            "reversed",
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
        template_code,
        template_name,
        permission,
        command,
        outcome,
    ) in definitions:
        workflow_type, _ = WorkflowType.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "description": description,
                "subject_type": "inventory.stock_transaction",
                "subject_adapter": "inventory.stock_transaction",
                "allowed_scope_fields": ["project_id", "transaction_type"],
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
                    "key": "assignment",
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
                    "key": "completed",
                    "name": "تکمیل‌شده",
                    "step_type": "end",
                    "is_terminal": True,
                },
            ],
            "transitions": [
                {
                    "source": "start",
                    "target": "assignment",
                    "outcome": "requested",
                    "is_default": True,
                },
                {
                    "source": "assignment",
                    "target": "completed",
                    "outcome": outcome,
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
                "description": description,
                "is_active": True,
                "configuration": configuration,
            },
        )
        for role in OrganizationRole.objects.filter(
            permissions__code=permission
        ).distinct():
            role.permissions.add(*runtime_permissions)


class Migration(migrations.Migration):
    dependencies = [  # noqa: RUF012
        ("inventory", "0001_initial"),
        ("workflows", "0015_estimate_contract_amendment_compatibility_catalog"),
    ]

    operations = [  # noqa: RUF012
        migrations.RunPython(seed_w56_inventory_catalog, migrations.RunPython.noop)
    ]
