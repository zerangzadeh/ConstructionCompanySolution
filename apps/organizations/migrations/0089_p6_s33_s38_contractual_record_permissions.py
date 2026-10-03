from typing import ClassVar

from django.db import migrations

PERMISSIONS = (
    (
        "contractual_records.view",
        "مشاهده دستورها، تغییرات، ادعاها و تمدید مدت قراردادی",
    ),
    ("contractual_records.prepare", "تهیه و اصلاح رکورد قراردادی"),
    ("contractual_records.submit", "ارسال رکورد قراردادی برای تأیید"),
    ("contractual_records.approve", "تأیید یا بازگرداندن رکورد قراردادی"),
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
    roles = Role.objects.filter(
        code__in=MANAGEMENT_ROLE_CODES, organization__isnull=True
    )
    for code, name in PERMISSIONS:
        permission, _ = Permission.objects.update_or_create(
            code=code,
            defaults={"name": name, "description": name, "is_active": True},
        )
        for role in roles:
            role.permissions.add(permission)


def reverse(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    Permission.objects.filter(code__in=[code for code, _ in PERMISSIONS]).delete()


class Migration(migrations.Migration):
    dependencies: ClassVar[list] = [
        ("organizations", "0088_p6_s26_s32_national_regulatory_resolution"),
    ]
    operations: ClassVar[list] = [migrations.RunPython(forward, reverse)]
