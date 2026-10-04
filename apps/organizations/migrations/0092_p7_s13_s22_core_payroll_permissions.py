from typing import ClassVar

from django.db import migrations


PERMISSIONS = (
    ("payroll_configuration.view", "مشاهده پیکربندی و قواعد حقوق"),
    ("payroll_configuration.manage", "مدیریت پیکربندی و قواعد حقوق"),
    ("payroll.prepare", "تهیه ورودی و محاسبه حقوق"),
    ("payroll.review", "بررسی اجرای حقوق"),
    ("payroll.finalize", "قطعی‌سازی اجرای حقوق"),
    ("payroll.adjust", "تعدیل، برگشت و جایگزینی حقوق"),
    ("payroll_results.view", "مشاهده نتایج حساس حقوق"),
    ("payslips.view", "مشاهده فیش حقوق"),
    ("payslips.export", "خروجی فیش حقوق"),
    ("payroll_audit.view", "مشاهده ممیزی حساس حقوق"),
)


def forward(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    for code, name in PERMISSIONS:
        Permission.objects.update_or_create(
            code=code,
            defaults={"name": name, "description": name, "is_active": True},
        )
    # Core Payroll is highly sensitive. No built-in/global role receives these
    # permissions; each Tenant must make an explicit organization-specific grant.


def reverse(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    Permission.objects.filter(code__in=[code for code, _ in PERMISSIONS]).delete()


class Migration(migrations.Migration):
    dependencies: ClassVar[list] = [
        ("organizations", "0091_p7_s06_s12_timekeeping_permissions"),
        ("payroll", "0001_initial"),
    ]
    operations: ClassVar[list] = [migrations.RunPython(forward, reverse)]
