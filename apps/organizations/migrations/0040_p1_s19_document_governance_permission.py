from typing import ClassVar

from django.db import migrations

PERMISSION = ("document_categories.manage", "مدیریت دسته‌بندی اسناد")


def register_permission(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    Role = apps.get_model("organizations", "OrganizationRole")
    permission = Permission.objects.update_or_create(
        code=PERMISSION[0],
        defaults={
            "name": PERMISSION[1],
            "description": PERMISSION[1],
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
        code=PERMISSION[0]
    ).delete()


class Migration(migrations.Migration):
    dependencies: ClassVar[list[tuple[str, str]]] = [
        ("organizations", "0039_p1_s17_party_governance_permission"),
    ]
    operations: ClassVar[list[migrations.operations.base.Operation]] = [
        migrations.RunPython(register_permission, unregister_permission)
    ]
