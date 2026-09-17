from django.db import migrations


STAGES = (
    ("review", "بررسی حادثه", "review", "under_review", "safety_incidents.review"),
    ("assign", "تعیین مسئول", "assign", "assigned", "safety_incidents.review"),
    ("start_action", "آغاز اقدام", "start_action", "action_in_progress", "safety_incidents.manage"),
    ("resolve", "ثبت رفع", "resolve", "resolved", "safety_incidents.manage"),
    ("close", "بستن حادثه", "close", "closed", "safety_incidents.close"),
)


def _routes(key, permission):
    del key
    return [
        {
            "resolver_type": "business_permission",
            "configuration": {"permission": permission},
        },
        {"resolver_type": "organization_owner", "configuration": {}, "is_fallback": True},
    ]


def seed_safety_catalog(apps, schema_editor):
    del schema_editor
    WorkflowType = apps.get_model("workflows", "WorkflowType")
    WorkflowTemplate = apps.get_model("workflows", "WorkflowTemplate")
    OrganizationRole = apps.get_model("organizations", "OrganizationRole")
    BusinessPermission = apps.get_model("organizations", "BusinessPermission")
    workflow_type, _ = WorkflowType.objects.update_or_create(
        code="safety.safety_incident_lifecycle",
        defaults={
            "name": "چرخه حادثه ایمنی",
            "description": "بررسی، تخصیص، اقدام، رفع و بستن حادثه ایمنی.",
            "subject_type": "safety.safety_incident",
            "subject_adapter": "safety.safety_incident",
            "allowed_scope_fields": ["project_id", "site_id"],
            "is_active": True,
        },
    )
    configuration = {
        "steps": [
            {"key": "start", "name": "شروع", "step_type": "start", "is_start": True},
            *[
                {
                    "key": key, "name": title, "step_type": "approval",
                    "required_permission": permission,
                    "configuration": {"decision_policy": "any"},
                    "routing": _routes(key, permission),
                }
                for key, title, _, _, permission in STAGES
            ],
            {"key": "closed", "name": "بسته‌شده", "step_type": "end", "is_terminal": True},
        ],
        "transitions": [
            {"source": "start", "target": "review", "outcome": "reported", "is_default": True},
            *[
                {
                    "source": key,
                    "target": STAGES[index + 1][0] if index + 1 < len(STAGES) else "closed",
                    "outcome": outcome,
                    "domain_command": f"safety.safety_incident.{command}",
                    "required_permission": permission,
                }
                for index, (key, _, command, outcome, permission) in enumerate(STAGES)
            ],
        ],
    }
    WorkflowTemplate.objects.update_or_create(
        workflow_type=workflow_type,
        code="safety_incident_legacy_compatibility",
        defaults={
            "name": "سازگاری چرخه حادثه ایمنی",
            "description": "چرخه شش‌وضعیتی فعلی Safety را حفظ می‌کند.",
            "is_active": True,
            "configuration": configuration,
        },
    )
    runtime_permissions = list(BusinessPermission.objects.filter(
        code__in=("work_items.view", "work_items.claim", "work_items.act")
    ))
    for role in OrganizationRole.objects.filter(
        permissions__code__in=(
            "safety_incidents.review", "safety_incidents.manage", "safety_incidents.close"
        )
    ).distinct():
        role.permissions.add(*runtime_permissions)


class Migration(migrations.Migration):
    dependencies = [  # noqa: RUF012
        ("safety", "0001_initial"),
        ("workflows", "0012_daily_report_compatibility_catalog"),
    ]

    operations = [  # noqa: RUF012
        migrations.RunPython(seed_safety_catalog, migrations.RunPython.noop),
    ]
