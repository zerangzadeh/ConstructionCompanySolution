from django.db import migrations

PERMISSIONS = {
    "platform_admin.users_view": "مشاهده کاربران سامانه",
    "platform_admin.users_manage": "مدیریت کاربران سامانه",
    "platform_admin.users_recover": "بازیابی حساب کاربران سامانه",
}


def register_permissions(apps, schema_editor):
    catalog = apps.get_model("organizations", "BusinessPermission").objects.using(
        schema_editor.connection.alias
    )
    for code, name in PERMISSIONS.items():
        catalog.update_or_create(
            code=code,
            defaults={
                "name": name,
                "description": "ویژه نقش فعال مدیر پلتفرم",
                "is_active": True,
            },
        )


def deactivate_permissions(apps, schema_editor):
    apps.get_model("organizations", "BusinessPermission").objects.using(
        schema_editor.connection.alias
    ).filter(code__in=PERMISSIONS).update(is_active=False)


class Migration(migrations.Migration):
    dependencies = [("organizations", "0128_platform_console_permissions")]  # noqa: RUF012
    operations = [migrations.RunPython(register_permissions, deactivate_permissions)]  # noqa: RUF012
