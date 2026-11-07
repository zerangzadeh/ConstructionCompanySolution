"""Bounded report reference authority; custom role grants remain explicit."""

from django.db import migrations

CODE = "daily_reports.link_records"


def forward(apps, schema_editor):
    alias = schema_editor.connection.alias
    permission, _ = (
        apps.get_model("organizations", "BusinessPermission")
        .objects.using(alias)
        .update_or_create(
            code=CODE,
            defaults={
                "name": "ارجاع رکورد ایمنی و کیفیت در گزارش روزانه",
                "description": "ارجاع رکورد قابل مشاهده در محدوده همان گزارش؛ بدون تغییر رکورد اصلی.",
                "is_active": True,
            },
        )
    )
    for role in (
        apps.get_model("organizations", "OrganizationRole")
        .objects.using(alias)
        .filter(organization__isnull=True, permissions__code="daily_reports.create")
    ):
        role.permissions.add(permission)


def reverse(apps, schema_editor):
    apps.get_model("organizations", "BusinessPermission").objects.using(
        schema_editor.connection.alias
    ).filter(code=CODE).update(is_active=False)


class Migration(migrations.Migration):
    dependencies = [("organizations", "0125_mvp02_field_workforce_permission")]  # noqa: RUF012
    operations = [migrations.RunPython(forward, reverse)]  # noqa: RUF012
