from typing import ClassVar

from django.db import migrations

PERMISSIONS = (
    ("guarantees.view", "مشاهده ضمانت‌نامه‌ها و مواجهه"),
    ("guarantees.manage", "ثبت و اصلاح ضمانت‌نامه"),
    ("guarantees.submit", "ارسال ضمانت‌نامه"),
    ("guarantees.approve", "تأیید ضمانت‌نامه یا آزادسازی"),
    ("compliance_evidence.view", "مشاهده شواهد بیمه و مفاصاحساب"),
    ("compliance_evidence.manage", "ثبت و اصلاح شواهد بیمه و مفاصاحساب"),
    ("compliance_evidence.submit", "ارسال شواهد بیمه و مفاصاحساب"),
    ("compliance_evidence.approve", "تأیید شواهد بیمه و مفاصاحساب"),
    ("retention_releases.view", "مشاهده آزادسازی کسور تضمین"),
    ("retention_releases.create", "تهیه آزادسازی کسور تضمین"),
    ("retention_releases.submit", "ارسال آزادسازی کسور تضمین"),
    ("retention_releases.approve", "تأیید یا بازگرداندن آزادسازی کسور تضمین"),
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
        ("organizations", "0085_p6_s14_s20_payable_permissions"),
    ]
    operations: ClassVar[list] = [migrations.RunPython(forward, reverse)]
