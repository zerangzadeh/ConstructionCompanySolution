from typing import ClassVar

from django.db import migrations

PERMISSION_CODE = "accounting.reconciliations_dispose"


def forward(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    Role = apps.get_model("organizations", "OrganizationRole")
    permission, _ = Permission.objects.update_or_create(
        code=PERMISSION_CODE,
        defaults={
            "name": "ثبت تعیین تکلیف استثنای تطبیق حسابداری",
            "description": "ثبت تعیین تکلیف استثنای تطبیق حسابداری",
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
        ("organizations", "0052_p2_reconciliation_run_permission")
    ]
    operations: ClassVar[list[migrations.operations.base.Operation]] = [
        migrations.RunPython(forward, migrations.RunPython.noop)
    ]
