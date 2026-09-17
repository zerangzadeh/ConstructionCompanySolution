from django.db import migrations

STAGES = (
    ("review", "بررسی مسئله", "review", "under_review", "quality_issues.review"),
    ("assign", "تعیین مسئول", "assign", "assigned", "quality_issues.review"),
    (
        "start_action",
        "آغاز اقدام اصلاحی",
        "start_action",
        "action_in_progress",
        "quality_issues.manage",
    ),
    (
        "submit_for_verification",
        "ارسال برای راستی‌آزمایی",
        "submit_for_verification",
        "awaiting_verification",
        "quality_issues.manage",
    ),
    (
        "verify",
        "راستی‌آزمایی",
        "verify",
        "verified",
        "quality_issues.verify",
    ),
    ("close", "بستن مسئله", "close", "closed", "quality_issues.close"),
)


def _routes(key, permission):
    del key
    return [
        {
            "resolver_type": "business_permission",
            "configuration": {"permission": permission},
        },
        {
            "resolver_type": "organization_owner",
            "configuration": {},
            "is_fallback": True,
        },
    ]


def seed_quality_catalog(apps, schema_editor):
    del schema_editor
    WorkflowType = apps.get_model("workflows", "WorkflowType")
    WorkflowTemplate = apps.get_model("workflows", "WorkflowTemplate")
    OrganizationRole = apps.get_model("organizations", "OrganizationRole")
    BusinessPermission = apps.get_model("organizations", "BusinessPermission")
    workflow_type, _ = WorkflowType.objects.update_or_create(
        code="quality.quality_issue_lifecycle",
        defaults={
            "name": "چرخه مسئله کیفیت",
            "description": "بررسی، تخصیص، اقدام، راستی‌آزمایی و بستن مسئله کیفیت.",
            "subject_type": "quality.quality_issue",
            "subject_adapter": "quality.quality_issue",
            "allowed_scope_fields": ["project_id", "site_id"],
            "is_active": True,
        },
    )
    configuration = {
        "steps": [
            {"key": "start", "name": "شروع", "step_type": "start", "is_start": True},
            *[
                {
                    "key": key,
                    "name": title,
                    "step_type": "approval",
                    "required_permission": permission,
                    "configuration": {"decision_policy": "any"},
                    "routing": _routes(key, permission),
                }
                for key, title, _, _, permission in STAGES
            ],
            {
                "key": "closed",
                "name": "بسته‌شده",
                "step_type": "end",
                "is_terminal": True,
            },
        ],
        "transitions": [
            {
                "source": "start",
                "target": "review",
                "outcome": "reported",
                "is_default": True,
            },
            *[
                {
                    "source": key,
                    "target": STAGES[index + 1][0]
                    if index + 1 < len(STAGES)
                    else "closed",
                    "outcome": outcome,
                    "domain_command": f"quality.quality_issue.{command}",
                    "required_permission": permission,
                }
                for index, (key, _, command, outcome, permission) in enumerate(STAGES)
            ],
        ],
    }
    WorkflowTemplate.objects.update_or_create(
        workflow_type=workflow_type,
        code="quality_issue_legacy_compatibility",
        defaults={
            "name": "سازگاری چرخه مسئله کیفیت",
            "description": "چرخه هفت‌وضعیتی فعلی Quality را حفظ می‌کند.",
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
        permissions__code__in=(
            "quality_issues.review",
            "quality_issues.manage",
            "quality_issues.verify",
            "quality_issues.close",
        )
    ).distinct():
        role.permissions.add(*runtime_permissions)


class Migration(migrations.Migration):
    dependencies = [  # noqa: RUF012
        ("quality", "0001_initial"),
        ("workflows", "0013_safety_compatibility_catalog"),
    ]

    operations = [  # noqa: RUF012
        migrations.RunPython(seed_quality_catalog, migrations.RunPython.noop),
    ]
