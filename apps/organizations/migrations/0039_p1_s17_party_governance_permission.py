from typing import ClassVar

from django.db import migrations

PERMISSIONS = (("party_governance.manage", "مدیریت شواهد و دسته‌بندی طرف تجاری"),)


def register_permission(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    Role = apps.get_model("organizations", "OrganizationRole")
    permission = Permission.objects.update_or_create(
        code=PERMISSIONS[0][0],
        defaults={
            "name": PERMISSIONS[0][1],
            "description": PERMISSIONS[0][1],
            "is_active": True,
        },
    )[0]
    for role_code in ("tenant_owner", "tenant_admin", "company_owner"):
        role = Role.objects.filter(code=role_code, organization__isnull=True).first()
        if role is not None:
            role.permissions.add(permission)


def unregister_permission(apps, schema_editor):
    del schema_editor
    apps.get_model("organizations", "BusinessPermission").objects.filter(
        code=PERMISSIONS[0][0]
    ).delete()


class Migration(migrations.Migration):
    dependencies: ClassVar[list[tuple[str, str]]] = [
        ("organizations", "0038_p1_s16_party_governance_permissions"),
    ]

    operations: ClassVar[list[migrations.operations.base.Operation]] = [
        migrations.RunPython(register_permission, unregister_permission),
    ]
