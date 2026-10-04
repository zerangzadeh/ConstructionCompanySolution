from typing import ClassVar

from django.db import migrations

PERMISSIONS = (
    ("payroll_statutory_configuration.view", "مشاهده قواعد مقرراتی حقوق"),
    ("payroll_statutory.prepare", "تهیه محاسبات مقرراتی حقوق"),
    ("payroll_statutory.review", "بررسی محاسبات مقرراتی حقوق"),
    ("payroll_statutory_outputs.generate", "تولید خروجی مقرراتی حقوق"),
    ("payroll_statutory_outputs.export", "ثبت خروجی و شاهد ارسال مقرراتی حقوق"),
    ("payroll_statutory.correct", "اصلاح و جایگزینی سابقه مقرراتی حقوق"),
    ("payroll_statutory_audit.view", "مشاهده ممیزی حساس مقرراتی حقوق"),
)


def forward(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    for code, name in PERMISSIONS:
        Permission.objects.update_or_create(
            code=code,
            defaults={"name": name, "description": name, "is_active": True},
        )
    # Statutory payroll is sensitive and independent from general Payroll,
    # Workforce, Accounting and Tenant-management access. No default grant.


def reverse(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    Permission.objects.filter(code__in=[code for code, _ in PERMISSIONS]).delete()


class Migration(migrations.Migration):
    dependencies: ClassVar[list] = [
        ("organizations", "0092_p7_s13_s22_core_payroll_permissions"),
        ("payroll", "0003_p7_s23_s28_statutory_payroll"),
    ]
    operations: ClassVar[list] = [migrations.RunPython(forward, reverse)]
