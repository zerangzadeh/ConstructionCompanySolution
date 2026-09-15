from django.db import migrations

PERMISSIONS = {
    "employee_positions.assign": "تخصیص سمت شغلی به کارمند",
    "employee_positions.end": "پایان تخصیص سمت شغلی کارمند",
}
MANAGEMENT_ROLE_CODES = (
    "company_owner",
    "company_manager",
    "operations_manager",
)


def add_employee_position_permissions(apps, schema_editor):
    business_permission = apps.get_model("organizations", "BusinessPermission")
    organization_role = apps.get_model("organizations", "OrganizationRole")

    permissions = []
    for code, name in PERMISSIONS.items():
        permission, _ = business_permission.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "description": f"مجوز سازمانی ریزدانه: {name}",
                "is_active": True,
            },
        )
        permissions.append(permission)
    for role in organization_role.objects.filter(code__in=MANAGEMENT_ROLE_CODES):
        role.permissions.add(*permissions)


def remove_employee_position_permissions(apps, schema_editor):
    business_permission = apps.get_model("organizations", "BusinessPermission")
    business_permission.objects.filter(code__in=PERMISSIONS).delete()


class Migration(migrations.Migration):
    dependencies = [  # noqa: RUF012
        ("organizations", "0012_generalize_document_permission_labels"),
    ]

    operations = [  # noqa: RUF012
        migrations.RunPython(
            add_employee_position_permissions,
            remove_employee_position_permissions,
        ),
    ]
