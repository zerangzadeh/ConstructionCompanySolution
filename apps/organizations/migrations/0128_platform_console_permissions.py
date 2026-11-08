from django.db import migrations

PERMISSIONS = {
    "platform_admin.manage_operators": "مدیریت مدیران پلتفرم",
    "platform_admin.inspect_audit": "مشاهده ممیزی پلتفرم",
    "platform_admin.inspect_health": "مشاهده سلامت پلتفرم",
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
    dependencies = [("organizations", "0127_platform_company_permissions")]  # noqa: RUF012
    operations = [migrations.RunPython(register_permissions, deactivate_permissions)]  # noqa: RUF012
