"""Register correction authority without adding any role grants."""
from django.db import migrations


def seed(apps, schema_editor):
    permission, _ = apps.get_model("organizations", "BusinessPermission").objects.using(
        schema_editor.connection.alias
    ).get_or_create(
        code="daily_reports.correct",
        defaults={
            "name": "اصلاح نسخه بازگشتی گزارش روزانه",
            "description": "اصلاح نسخه جدید توسط نویسنده گزارش در محدوده همان کارگاه.",
            "is_active": True,
        },
    )
    for role in apps.get_model("organizations", "OrganizationRole").objects.using(
        schema_editor.connection.alias
    ).filter(organization__isnull=True, permissions=permission):
        role.permissions.remove(permission)


def unseed(apps, schema_editor):
    apps.get_model("organizations", "BusinessPermission").objects.using(
        schema_editor.connection.alias
    ).filter(code="daily_reports.correct").update(is_active=False)


class Migration(migrations.Migration):
    dependencies = [("organizations", "0129_platform_user_permissions")]
    operations = [migrations.RunPython(seed, unseed)]
