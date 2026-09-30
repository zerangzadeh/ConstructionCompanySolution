from typing import ClassVar

from django.db import migrations

PERMISSIONS = (
    (
        "accounting.reports_view",
        "مشاهده گزارش‌ها و صورت‌های مالی حسابداری",
    ),
    ("accounting.statements_run", "نگهداری اجرای صورت مالی"),
    ("accounting.adjustments_prepare", "تهیه تعدیل کنترل‌شده"),
)


def forward(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    Role = apps.get_model("organizations", "OrganizationRole")
    roles = Role.objects.filter(
        code__in=("tenant_owner", "company_owner", "tenant_admin", "accountant"),
        organization__isnull=True,
    )
    for code, name in PERMISSIONS:
        permission, _ = Permission.objects.update_or_create(
            code=code,
            defaults={"name": name, "description": name, "is_active": True},
        )
        for role in roles:
            role.permissions.add(permission)


class Migration(migrations.Migration):
    dependencies: ClassVar[list[tuple[str, str]]] = [
        ("organizations", "0054_p2_reconciliation_sign_off")
    ]
    operations: ClassVar[list[migrations.operations.base.Operation]] = [
        migrations.RunPython(forward, migrations.RunPython.noop)
    ]
