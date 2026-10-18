# ruff: noqa: RUF012
"""Catalogue AP source reversal permission without implicit role grants."""

from django.db import migrations

PERMISSIONS = (
    ("subledgers.sources_reverse", "برگشت کنترل‌شده منبع تعهد AP"),
)


def forward(apps, schema_editor):
    model = apps.get_model("organizations", "BusinessPermission")
    for code, name in PERMISSIONS:
        model.objects.using(schema_editor.connection.alias).update_or_create(
            code=code, defaults={"name": name, "description": name, "is_active": True}
        )


def reverse(apps, schema_editor):
    apps.get_model("organizations", "BusinessPermission").objects.using(
        schema_editor.connection.alias
    ).filter(code__in=[code for code, _ in PERMISSIONS]).update(is_active=False)


class Migration(migrations.Migration):
    dependencies = [("organizations", "0116_cep032_tender_bid_permissions")]
    operations = [migrations.RunPython(forward, reverse)]
