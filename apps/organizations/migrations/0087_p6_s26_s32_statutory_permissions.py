from typing import ClassVar

from django.db import migrations

PERMISSIONS = (
    ("taxpayer_invoices.view", "مشاهده صورتحساب‌های مؤدیان"),
    ("taxpayer_invoices.prepare", "تهیه و اصلاح صورتحساب مؤدیان"),
    ("taxpayer_invoices.submit", "ارسال صورتحساب مؤدیان برای تأیید"),
    ("taxpayer_invoices.approve", "تأیید یا بازگرداندن صورتحساب مؤدیان"),
    ("contractor_compliance.view", "مشاهده ارزیابی انطباق بیمه پیمانکار"),
    ("contractor_compliance.prepare", "تهیه ارزیابی انطباق بیمه پیمانکار"),
    ("contractor_compliance.submit", "ارسال ارزیابی انطباق بیمه پیمانکار"),
    ("contractor_compliance.approve", "تأیید ارزیابی انطباق بیمه پیمانکار"),
    ("statutory_submissions.execute", "ثبت خروجی یا اجرای adapter آزمون مقرراتی"),
    ("statutory_submissions.resolve", "ثبت حل انسانی خطای ارسال مقرراتی"),
)

MANAGEMENT_ROLE_CODES = (
    "tenant_owner",
    "company_owner",
    "tenant_admin",
    "tenant_manager",
    "project_manager",
    "company_manager",
)


def forward(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    Role = apps.get_model("organizations", "OrganizationRole")
    for code, name in PERMISSIONS:
        permission, _ = Permission.objects.update_or_create(
            code=code,
            defaults={"name": name, "description": name, "is_active": True},
        )
        for role in Role.objects.filter(
            code__in=MANAGEMENT_ROLE_CODES, organization__isnull=True
        ):
            role.permissions.add(permission)


def reverse(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    Permission.objects.filter(code__in=[code for code, _ in PERMISSIONS]).delete()


class Migration(migrations.Migration):
    dependencies: ClassVar[list] = [
        ("organizations", "0086_p6_s21_s25_commercial_control_permissions"),
    ]
    operations: ClassVar[list] = [migrations.RunPython(forward, reverse)]
