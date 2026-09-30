from typing import ClassVar

from django.db import migrations


PERMISSIONS = (
    ("materials.steward", "راهبری هویت مصالح"),
    ("materials.merge", "ادغام غیرمخرب مصالح"),
)


def register_permissions(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    Role = apps.get_model("organizations", "OrganizationRole")
    permissions = [
        Permission.objects.update_or_create(
            code=code,
            defaults={"name": name, "description": name, "is_active": True},
        )[0]
        for code, name in PERMISSIONS
    ]
    for role in Role.objects.filter(
        code__in=("tenant_owner", "tenant_admin", "company_owner"),
        organization__isnull=True,
    ):
        role.permissions.add(*permissions)


def unregister_permissions(apps, schema_editor):
    del schema_editor
    apps.get_model("organizations", "BusinessPermission").objects.filter(
        code__in=[code for code, _ in PERMISSIONS]
    ).delete()


class Migration(migrations.Migration):
    dependencies: ClassVar[list[tuple[str, str]]] = [
        ("organizations", "0043_p1_s22_document_lifecycle_permissions"),
    ]
    operations: ClassVar[list[migrations.operations.base.Operation]] = [
        migrations.RunPython(register_permissions, unregister_permissions)
    ]
