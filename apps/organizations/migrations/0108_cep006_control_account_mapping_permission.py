from typing import ClassVar

from django.db import migrations


def forward(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    Role = apps.get_model("organizations", "OrganizationRole")
    permission, _ = Permission.objects.update_or_create(
        code="accounting.control_account_mappings_manage",
        defaults={
            "name": "مدیریت نگاشت حساب کنترل AP/AR",
            "description": "مدیریت نگاشت حساب کنترل AP/AR",
            "is_active": True,
        },
    )
    for role in Role.objects.filter(
        code__in=("tenant_owner", "company_owner", "tenant_admin", "accountant"),
        organization__isnull=True,
    ):
        role.permissions.add(permission)


class Migration(migrations.Migration):
    dependencies: ClassVar[list[tuple[str, str]]] = [
        ("organizations", "0107_p10_s14_s17_project_closeout_permissions")
    ]
    operations: ClassVar[list[migrations.operations.base.Operation]] = [
        migrations.RunPython(forward, migrations.RunPython.noop)
    ]
