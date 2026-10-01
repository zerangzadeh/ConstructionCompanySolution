from typing import ClassVar

from django.db import migrations

PERMISSIONS = (
    (
        "project_cost.reconciliations_view",
        "مشاهده تطبیق محدود شواهد هزینه پروژه",
    ),
    (
        "project_cost.reconciliations_export",
        "خروجی تطبیق محدود شواهد هزینه پروژه",
    ),
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


def reverse(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    Permission.objects.filter(code__in=[code for code, _ in PERMISSIONS]).delete()


class Migration(migrations.Migration):
    dependencies: ClassVar[list[tuple[str, str]]] = [
        ("organizations", "0070_p4_s31_s34_project_controls_permissions")
    ]
    operations: ClassVar[list[migrations.operations.base.Operation]] = [
        migrations.RunPython(forward, reverse)
    ]
