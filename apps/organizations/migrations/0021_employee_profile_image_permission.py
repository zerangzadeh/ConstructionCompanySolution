from django.db import migrations

PERMISSION_CODE = "employees.change_profile_image"
MANAGEMENT_ROLE_CODES = (
    "company_owner",
    "company_manager",
    "operations_manager",
)


def add_employee_profile_image_permission(apps, schema_editor):
    permission_model = apps.get_model("organizations", "BusinessPermission")
    role_model = apps.get_model("organizations", "OrganizationRole")
    permission, _ = permission_model.objects.update_or_create(
        code=PERMISSION_CODE,
        defaults={
            "name": "تغییر عکس پرسنلی کارمند",
            "description": "مجوز سازمانی ریزدانه: تغییر عکس پرسنلی کارمند",
            "is_active": True,
        },
    )
    for role in role_model.objects.filter(code__in=MANAGEMENT_ROLE_CODES):
        role.permissions.add(permission)


def remove_employee_profile_image_permission(apps, schema_editor):
    permission_model = apps.get_model("organizations", "BusinessPermission")
    permission_model.objects.filter(code=PERMISSION_CODE).delete()


class Migration(migrations.Migration):
    dependencies = [  # noqa: RUF012
        ("organizations", "0020_add_organization_code_prefixes"),
    ]

    operations = [  # noqa: RUF012
        migrations.RunPython(
            add_employee_profile_image_permission,
            remove_employee_profile_image_permission,
        ),
    ]
