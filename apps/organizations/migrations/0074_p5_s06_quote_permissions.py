from typing import ClassVar

from django.db import migrations

PERMISSIONS = (
    ("rfq_quotes.view_metadata", "مشاهده فراداده پیشنهادها"),
    ("rfq_quotes.capture", "ثبت پیشنهادهای مهروموم‌شده"),
    ("rfq_quotes.submit", "ثبت نهایی پیشنهاد مهروموم‌شده"),
    ("rfq_quotes.withdraw", "بازپس‌گیری پیشنهاد مهروموم‌شده"),
)
MAKER_CODES = tuple(code for code, _ in PERMISSIONS)
MANAGER_ROLES = (
    "company_owner",
    "tenant_owner",
    "tenant_admin",
    "company_manager",
    "tenant_manager",
)


def forward(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    Role = apps.get_model("organizations", "OrganizationRole")
    permissions = {}
    for code, name in PERMISSIONS:
        permission, _ = Permission.objects.update_or_create(
            code=code,
            defaults={"name": name, "description": name, "is_active": True},
        )
        permissions[code] = permission
    for role in Role.objects.filter(code__in=MANAGER_ROLES, organization__isnull=True):
        role.permissions.add(*(permissions[code] for code in MAKER_CODES))
    for role in Role.objects.filter(code="member", organization__isnull=True):
        role.permissions.add(*(permissions[code] for code in MAKER_CODES))


def reverse(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    Permission.objects.filter(code__in=[code for code, _ in PERMISSIONS]).delete()


class Migration(migrations.Migration):
    dependencies: ClassVar[list[tuple[str, str]]] = [
        ("organizations", "0073_p5_s05_rfq_permissions")
    ]
    operations: ClassVar[list] = [migrations.RunPython(forward, reverse)]
