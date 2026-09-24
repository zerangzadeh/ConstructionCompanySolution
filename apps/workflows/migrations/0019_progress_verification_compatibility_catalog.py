from django.db import migrations


def seed_progress_catalog(apps, schema_editor):
    del schema_editor
    WorkflowType = apps.get_model("workflows", "WorkflowType")
    WorkflowTemplate = apps.get_model("workflows", "WorkflowTemplate")
    OrganizationRole = apps.get_model("organizations", "OrganizationRole")
    BusinessPermission = apps.get_model("organizations", "BusinessPermission")
    permission = "progress.verify"
    workflow_type, _ = WorkflowType.objects.update_or_create(
        code="billing.progress_verification",
        defaults={
            "name": "راستی‌آزمایی پیشرفت",
            "description": "راستی‌آزمایی منبع اندازه‌گیری پیشرفت پروژه.",
            "subject_type": "billing.progress_record",
            "subject_adapter": "billing.progress_record",
            "allowed_scope_fields": ["project_id", "contract_id", "baseline_id"],
            "is_active": True,
        },
    )
    configuration = {
        "steps": [
            {"key": "start", "name": "شروع", "step_type": "start", "is_start": True},
            {"key": "verification", "name": "راستی‌آزمایی پیشرفت", "step_type": "approval", "configuration": {"decision_policy": "any"}, "routing": [{"resolver_type": "business_permission", "configuration": {"permission": permission}}, {"resolver_type": "organization_owner", "configuration": {}, "is_fallback": True}]},
            {"key": "verified", "name": "راستی‌آزمایی‌شده", "step_type": "end", "is_terminal": True},
            {"key": "rejected", "name": "ردشده", "step_type": "end", "is_terminal": True},
        ],
        "transitions": [
            {"source": "start", "target": "verification", "outcome": "requested", "is_default": True},
            {"source": "verification", "target": "verified", "outcome": "verified", "domain_command": "billing.progress.verify", "required_permission": permission},
            {"source": "verification", "target": "rejected", "outcome": "rejected", "domain_command": "billing.progress.reject", "required_permission": permission},
        ],
    }
    WorkflowTemplate.objects.update_or_create(
        workflow_type=workflow_type,
        code="progress_verification_f62",
        defaults={"name": "راستی‌آزمایی پیشرفت", "description": "مسیر تک‌مرحله‌ای مناسب سازمان‌های کوچک.", "is_active": True, "configuration": configuration},
    )
    runtime_permissions = list(BusinessPermission.objects.filter(code__in=("work_items.view", "work_items.claim", "work_items.act")))
    for role in OrganizationRole.objects.filter(permissions__code=permission).distinct():
        role.permissions.add(*runtime_permissions)


class Migration(migrations.Migration):
    dependencies = [("billing", "0002_progressrecord"), ("organizations", "0026_progress_permissions"), ("workflows", "0018_project_baseline_compatibility_catalog")]

    operations = [migrations.RunPython(seed_progress_catalog, migrations.RunPython.noop)]
