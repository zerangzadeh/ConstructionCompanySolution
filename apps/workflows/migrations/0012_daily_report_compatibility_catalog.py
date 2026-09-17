from django.db import migrations


def seed_daily_report_catalog(apps, schema_editor):
    del schema_editor
    WorkflowType = apps.get_model("workflows", "WorkflowType")
    WorkflowTemplate = apps.get_model("workflows", "WorkflowTemplate")
    OrganizationRole = apps.get_model("organizations", "OrganizationRole")
    BusinessPermission = apps.get_model("organizations", "BusinessPermission")

    workflow_type, _ = WorkflowType.objects.update_or_create(
        code="daily_reports.daily_report_approval",
        defaults={
            "name": "تأیید گزارش روزانه",
            "description": "گردش‌کار مرحله‌ای ارسال و تأیید گزارش روزانه.",
            "subject_type": "daily_reports.daily_report",
            "subject_adapter": "daily_reports.daily_report",
            "allowed_scope_fields": ["project_id", "site_id"],
            "is_active": True,
        },
    )
    WorkflowTemplate.objects.update_or_create(
        workflow_type=workflow_type,
        code="daily_report_legacy_compatibility",
        defaults={
            "name": "سازگاری تأیید گزارش روزانه",
            "description": "رفتار draft → submitted → approved موجود را حفظ می‌کند.",
            "is_active": True,
            "configuration": {
                "steps": [
                    {
                        "key": "start",
                        "name": "شروع",
                        "step_type": "start",
                        "is_start": True,
                    },
                    {
                        "key": "legacy_approval",
                        "name": "تأیید گزارش روزانه",
                        "step_type": "approval",
                        "configuration": {"decision_policy": "any"},
                        "routing": [
                            {
                                "resolver_type": "business_permission",
                                "configuration": {
                                    "permission": "daily_reports.approve"
                                },
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
                        "target": "legacy_approval",
                        "outcome": "submitted",
                        "is_default": True,
                    },
                    {
                        "source": "legacy_approval",
                        "target": "approved",
                        "outcome": "approved",
                        "domain_command": "daily_reports.daily_report.approve",
                        "required_permission": "daily_reports.approve",
                    },
                ],
            },
        },
    )
    runtime_permissions = list(
        BusinessPermission.objects.filter(
            code__in=("work_items.view", "work_items.claim", "work_items.act")
        )
    )
    for role in OrganizationRole.objects.filter(
        permissions__code="daily_reports.approve"
    ).distinct():
        role.permissions.add(*runtime_permissions)


class Migration(migrations.Migration):
    dependencies = [  # noqa: RUF012
        ("daily_reports", "0003_alter_dailyactivity_options_and_more"),
        ("workflows", "0011_purchase_request_canonical_scope"),
    ]

    operations = [  # noqa: RUF012
        migrations.RunPython(seed_daily_report_catalog, migrations.RunPython.noop)
    ]
