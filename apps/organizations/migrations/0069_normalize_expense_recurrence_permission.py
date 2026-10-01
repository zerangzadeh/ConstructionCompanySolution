from typing import ClassVar

from django.db import migrations


OLD_CODE = "expense_recurrences.manage"
NEW_CODE = "expenses.recurrences_manage"
NAME = "مدیریت پیشنهادهای هزینه تکرارشونده"


def forward(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    Role = apps.get_model("organizations", "OrganizationRole")
    new_permission, _ = Permission.objects.update_or_create(
        code=NEW_CODE,
        defaults={"name": NAME, "description": NAME, "is_active": True},
    )
    old_permission = Permission.objects.filter(code=OLD_CODE).first()
    if old_permission:
        for role in Role.objects.filter(permissions=old_permission):
            role.permissions.add(new_permission)
        old_permission.delete()


class Migration(migrations.Migration):
    dependencies: ClassVar[list[tuple[str, str]]] = [
        ("organizations", "0068_p4_s26_s30_expense_permissions")
    ]
    operations: ClassVar[list] = [migrations.RunPython(forward, migrations.RunPython.noop)]
