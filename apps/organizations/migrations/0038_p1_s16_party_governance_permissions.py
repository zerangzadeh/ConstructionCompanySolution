from typing import ClassVar

from django.db import migrations

PERMISSIONS = (
    ("parties.merge", "ثبت ادغام طرف تجاری"),
    ("party_restrictions.manage", "مدیریت محدودیت‌های طرف تجاری"),
)


def register_party_governance_permissions(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    Role = apps.get_model("organizations", "OrganizationRole")
    values = {
        code: Permission.objects.update_or_create(
            code=code,
            defaults={"name": name, "description": name, "is_active": True},
        )[0]
        for code, name in PERMISSIONS
    }
    for role_code in ("tenant_owner", "tenant_admin", "company_owner"):
        role = Role.objects.filter(code=role_code, organization__isnull=True).first()
        if role is not None:
            role.permissions.add(*values.values())


def unregister_party_governance_permissions(apps, schema_editor):
    del schema_editor
    apps.get_model("organizations", "BusinessPermission").objects.filter(
        code__in=[code for code, _ in PERMISSIONS]
    ).delete()


class Migration(migrations.Migration):
    dependencies: ClassVar[list[tuple[str, str]]] = [
        ("organizations", "0037_platformpolicy_platformpolicyversion_and_more"),
    ]

    operations: ClassVar[list[migrations.operations.base.Operation]] = [
        migrations.RunPython(
            register_party_governance_permissions,
            unregister_party_governance_permissions,
        ),
    ]
