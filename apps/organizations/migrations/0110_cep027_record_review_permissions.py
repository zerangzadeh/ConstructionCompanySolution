"""Map distinct record-review permissions from existing Safety/Quality grants."""

# ruff: noqa: RUF012

from django.db import migrations

PERMISSIONS = (
    ("safety_incidents.record_submit", "ارسال و اصلاح رکورد ایمنی", "safety_incidents.create"),
    ("safety_incidents.record_decide", "تصمیم بررسی رکورد ایمنی", "safety_incidents.review"),
    ("quality_issues.record_submit", "ارسال و اصلاح رکورد کیفیت", "quality_issues.create"),
    ("quality_issues.record_decide", "تصمیم بررسی رکورد کیفیت", "quality_issues.review"),
)


def forward(apps, schema_editor):
    del schema_editor
    permission_model = apps.get_model("organizations", "BusinessPermission")
    role_model = apps.get_model("organizations", "OrganizationRole")
    for code, name, old_code in PERMISSIONS:
        permission, _ = permission_model.objects.update_or_create(
            code=code,
            defaults={"name": name, "description": name, "is_active": True},
        )
        for role in role_model.objects.filter(permissions__code=old_code).distinct():
            role.permissions.add(permission)


def reverse(apps, schema_editor):
    del schema_editor
    apps.get_model("organizations", "BusinessPermission").objects.filter(
        code__in=[code for code, _, _ in PERMISSIONS]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("organizations", "0109_cep020_forecast_budget_control_permissions")]
    operations = [migrations.RunPython(forward, reverse)]
