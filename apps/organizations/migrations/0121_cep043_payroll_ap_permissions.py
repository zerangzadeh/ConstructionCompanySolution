"""Explicit AP capabilities only; no existing grants or policy rows changed."""

from django.db import migrations

PERMISSIONS = (
    ("subledgers_payroll.enrollments_manage", "تهیه ثبت بدهی حقوق در AP"),
    ("subledgers_payroll.enrollments_approve", "فعال‌سازی و توقف ثبت بدهی حقوق در AP"),
    ("subledgers_payroll.prepare", "تهیه پیش‌نویس و اصلاح بدهی حقوق در AP"),
    ("subledgers_payroll.view", "مشاهده و تطبیق بدهی حقوق در AP"),
)


def forward(apps, schema_editor):
    model = apps.get_model("organizations", "BusinessPermission")
    for code, name in PERMISSIONS:
        model.objects.using(schema_editor.connection.alias).update_or_create(
            code=code, defaults={"name": name, "description": name, "is_active": True}
        )


def reverse(apps, schema_editor):
    # Preserve catalog/grant history on rollback; only deactivate these new codes.
    apps.get_model("organizations", "BusinessPermission").objects.using(
        schema_editor.connection.alias
    ).filter(code__in=[code for code, _ in PERMISSIONS]).update(is_active=False)


class Migration(migrations.Migration):
    dependencies = [("organizations", "0120_cep042_recognition_permissions")]
    operations = [migrations.RunPython(forward, reverse)]
