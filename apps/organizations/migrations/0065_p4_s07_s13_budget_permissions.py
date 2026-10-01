from typing import ClassVar

from django.db import migrations

PERMISSIONS = (
    ("cost_structures.manage", "مدیریت نسخه‌های CBS و مرکز هزینه"),
    ("budgets.view", "مشاهده بودجه‌های پروژه"),
    ("budgets.prepare", "آماده‌سازی بودجه پروژه"),
    ("budgets.submit", "ارسال بودجه پروژه"),
    ("budgets.accept", "پذیرش مستقل مبنای بودجه"),
)
DEFAULT_ROLES = ("tenant_owner", "company_owner", "tenant_admin")


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
            code__in=DEFAULT_ROLES, organization__isnull=True
        ):
            role.permissions.add(permission)


class Migration(migrations.Migration):
    dependencies: ClassVar[list[tuple[str, str]]] = [
        ("organizations", "0064_p4_s01_s06_estimate_depth_permissions")
    ]
    operations: ClassVar[list[migrations.operations.base.Operation]] = [
        migrations.RunPython(forward, migrations.RunPython.noop)
    ]
