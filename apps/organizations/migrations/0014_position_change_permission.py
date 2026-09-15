from django.db import migrations


PERMISSION = {
    "code": "positions.change",
    "name": "ویرایش سمت شغلی",
}
MANAGEMENT_ROLE_CODES = (
    "company_owner",
    "company_manager",
    "operations_manager",
)


def add_position_change_permission(apps, schema_editor):
    business_permission = apps.get_model("organizations", "BusinessPermission")
    organization_role = apps.get_model("organizations", "OrganizationRole")
    permission, _ = business_permission.objects.update_or_create(
        code=PERMISSION["code"],
        defaults={
            "name": PERMISSION["name"],
            "description": f"مجوز سازمانی ریزدانه: {PERMISSION['name']}",
            "is_active": True,
        },
    )
    for role in organization_role.objects.filter(code__in=MANAGEMENT_ROLE_CODES):
        role.permissions.add(permission)


def remove_position_change_permission(apps, schema_editor):
    business_permission = apps.get_model("organizations", "BusinessPermission")
    business_permission.objects.filter(code=PERMISSION["code"]).delete()


class Migration(migrations.Migration):
    dependencies = [  # noqa: RUF012
        ("organizations", "0013_employee_position_permissions"),
    ]

    operations = [  # noqa: RUF012
        migrations.RunPython(
            add_position_change_permission,
            remove_position_change_permission,
        ),
    ]
