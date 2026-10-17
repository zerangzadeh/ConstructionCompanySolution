"""Catalog the governed forecast and budget-control permissions without implicit grants."""
# ruff: noqa: RUF012

from django.db import migrations

PERMISSIONS = (
    ("project_cost.forecasts_review", "بررسی مستقل پیش‌بینی هزینه پروژه"),
    ("project_cost.budget_overrides_approve", "تأیید عبور ثبت‌شده از کنترل بودجه"),
)


def forward(apps, schema_editor):
    del schema_editor
    permission = apps.get_model("organizations", "BusinessPermission")
    for code, name in PERMISSIONS:
        permission.objects.update_or_create(
            code=code,
            defaults={"name": name, "description": name, "is_active": True},
        )


def reverse(apps, schema_editor):
    del schema_editor
    apps.get_model("organizations", "BusinessPermission").objects.filter(
        code__in=[code for code, _ in PERMISSIONS]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("organizations", "0108_cep006_control_account_mapping_permission")]
    operations = [migrations.RunPython(forward, reverse)]
