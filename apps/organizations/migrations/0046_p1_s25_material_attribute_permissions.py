from typing import ClassVar

from django.db import migrations


PERMISSIONS = (
    ("material_attributes.definitions_manage", "مدیریت تعریف نسخه‌دار ویژگی مصالح"),
    ("material_attributes.apply", "اعمال ویژگی مصالح"),
    ("material_attributes.import", "درون‌ریزی ویژگی مصالح"),
    ("material_prices.observations_record", "ثبت مشاهده قیمت مصالح"),
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
        ("organizations", "0045_p1_s24_uom_permissions"),
    ]
    operations: ClassVar[list[migrations.operations.base.Operation]] = [
        migrations.RunPython(register_permissions, unregister_permissions)
    ]
