from typing import ClassVar

from django.db import migrations


PERMISSIONS = (
    ("rfqs.view", "مشاهده استعلام‌ها"),
    ("rfqs.create", "ایجاد استعلام"),
    ("rfqs.change", "ویرایش استعلام"),
    ("rfqs.submit", "ارسال استعلام برای صدور"),
    ("rfqs.issue", "صدور استعلام"),
    ("rfqs.addendum", "افزودن الحاقیه استعلام"),
    ("rfqs.cancel", "لغو استعلام"),
    ("rfq_invitations.manage", "مدیریت دعوت‌نامه‌های استعلام"),
)
MAKER_CODES = ("rfqs.view", "rfqs.create", "rfqs.change", "rfqs.submit")
MANAGER_CODES = tuple(code for code, _ in PERMISSIONS)
MANAGER_ROLES = ("company_owner", "tenant_owner", "tenant_admin", "company_manager", "tenant_manager")


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
        role.permissions.add(*(permissions[code] for code in MANAGER_CODES))
    for role in Role.objects.filter(code="member", organization__isnull=True):
        role.permissions.add(*(permissions[code] for code in MAKER_CODES))


def reverse(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    Permission.objects.filter(code__in=[code for code, _ in PERMISSIONS]).delete()


class Migration(migrations.Migration):
    dependencies: ClassVar[list[tuple[str, str]]] = [("organizations", "0072_expense_category_change_permission")]
    operations: ClassVar[list] = [migrations.RunPython(forward, reverse)]
