"""Operational editing uses the existing permission catalog, without role inference."""

from django.db import migrations

CODE = "employees.change_operational"


def forward(apps, schema_editor):
    alias = schema_editor.connection.alias
    Permission = apps.get_model("organizations", "BusinessPermission")
    Role = apps.get_model("organizations", "OrganizationRole")
    permission, _ = Permission.objects.using(alias).update_or_create(
        code=CODE,
        defaults={
            "name": "ویرایش اطلاعات عملیاتی نیروی کار",
            "description": "ویرایش هویت و گروه کاری؛ بدون اختیار اتصال حساب یا تغییر وضعیت.",
            "is_active": True,
        },
    )
    # Extend only the built-in default roles already explicitly granted creation.
    # Tenant custom roles retain their exact grants and must opt in explicitly.
    for role in Role.objects.using(alias).filter(
        organization__isnull=True, permissions__code="employees.create"
    ):
        role.permissions.add(permission)


def reverse(apps, schema_editor):
    apps.get_model("organizations", "BusinessPermission").objects.using(
        schema_editor.connection.alias
    ).filter(code=CODE).update(is_active=False)


class Migration(migrations.Migration):
    dependencies = [("organizations", "0124_fiscal_year_closing_permissions")]  # noqa: RUF012
    operations = [migrations.RunPython(forward, reverse)]  # noqa: RUF012
