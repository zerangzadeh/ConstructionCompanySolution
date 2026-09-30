from typing import ClassVar

from django.db import migrations


PERMISSIONS = (
    ("units.conversions_manage", "مدیریت تبدیل نسخه‌دار واحدها"),
    ("units.rounding_manage", "مدیریت سیاست گرد کردن کمیت"),
    ("units.convert", "اجرای تبدیل کمیت"),
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
        ("organizations", "0044_p1_s23_material_identity_permissions"),
    ]
    operations: ClassVar[list[migrations.operations.base.Operation]] = [
        migrations.RunPython(register_permissions, unregister_permissions)
    ]
