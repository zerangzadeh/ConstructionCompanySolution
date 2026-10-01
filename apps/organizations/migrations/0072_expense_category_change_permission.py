from typing import ClassVar

from django.db import migrations


PERMISSION = ("expense_categories.change", "ویرایش دسته هزینه")
DEFAULT_ROLES = ("tenant_owner", "company_owner", "tenant_admin")


def forward(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    Role = apps.get_model("organizations", "OrganizationRole")
    permission, _ = Permission.objects.update_or_create(
        code=PERMISSION[0],
        defaults={
            "name": PERMISSION[1],
            "description": PERMISSION[1],
            "is_active": True,
        },
    )
    for role in Role.objects.filter(code__in=DEFAULT_ROLES, organization__isnull=True):
        role.permissions.add(permission)


def reverse(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    Permission.objects.filter(code=PERMISSION[0]).delete()


class Migration(migrations.Migration):
    dependencies: ClassVar[list[tuple[str, str]]] = [
        ("organizations", "0071_p4_s35_s37_reconciliation_permissions")
    ]
    operations: ClassVar[list] = [migrations.RunPython(forward, reverse)]
