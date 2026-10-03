from typing import ClassVar

from django.db import migrations

PERMISSIONS = (
    ("payable_measurements.view", "مشاهده اندازه‌گیری پیمان جزء"),
    ("payable_measurements.record", "ثبت و ارسال اندازه‌گیری پیمان جزء"),
    ("payable_measurements.verify", "راستی‌آزمایی اندازه‌گیری پیمان جزء"),
    ("payable_certificates.view", "مشاهده گواهی‌های پرداخت پیمان جزء"),
    ("payable_certificates.create", "تهیه گواهی پرداخت پیمان جزء"),
    ("payable_certificates.revise", "بازنگری و اصلاح گواهی پرداخت"),
    ("payable_certificates.submit", "ارسال گواهی پرداخت"),
    ("payable_certificates.approve", "تأیید یا بازگرداندن گواهی پرداخت"),
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
    dependencies: ClassVar[list[tuple[str, str]]] = [
        ("organizations", "0084_p6_s01_s06_contract_term_permissions"),
    ]
    operations: ClassVar[list] = [migrations.RunPython(forward, reverse)]
