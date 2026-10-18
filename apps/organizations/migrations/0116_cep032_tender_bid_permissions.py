# ruff: noqa: RUF012
"""Catalogue Commercial Tender/Bid permissions without implicit role grants."""

from django.db import migrations

PERMISSIONS = (
    ("tender_bids.view", "مشاهده مناقصه‌های پیمانکار"),
    ("tender_bids.prepare", "تهیه و بازنگری مناقصه پیمانکار"),
    ("tender_bids.transition", "ثبت تغییر وضعیت مناقصه پیمانکار"),
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
    dependencies = [("organizations", "0115_cep022_employment_permissions")]
    operations = [migrations.RunPython(forward, reverse)]
