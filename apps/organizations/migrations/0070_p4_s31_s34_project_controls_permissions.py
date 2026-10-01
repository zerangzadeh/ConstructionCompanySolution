from typing import ClassVar

from django.db import migrations

PERMISSIONS = (
    ("project_controls.compare", "مقایسه بودجه پذیرفته‌شده و شواهد هزینه پروژه"),
    ("project_controls.exceptions_view", "مشاهده استثناهای محدود کنترل پروژه"),
    ("project_controls.export", "خروجی ایمن کنترل پروژه"),
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
        ("organizations", "0069_normalize_expense_recurrence_permission")
    ]
    operations: ClassVar[list] = [migrations.RunPython(forward, migrations.RunPython.noop)]
