"""Catalogue governed Price Book capabilities without default grants."""
from django.db import migrations

PERMISSIONS = (
    ("price_books.manage", "مدیریت منابع فهرست‌بها"),
    ("price_books.activate", "تأیید مستند منبع فهرست‌بها"),
    ("price_book_mappings.manage", "نگاشت نسخه‌دار فهرست‌بها"),
)

def forward(apps, schema_editor):
    model = apps.get_model("organizations", "BusinessPermission")
    for code, name in PERMISSIONS:
        model.objects.using(schema_editor.connection.alias).update_or_create(
            code=code, defaults={"name": name, "description": name, "is_active": True})

def reverse(apps, schema_editor):
    apps.get_model("organizations", "BusinessPermission").objects.using(
        schema_editor.connection.alias).filter(code__in=[c for c, _ in PERMISSIONS]).update(is_active=False)

class Migration(migrations.Migration):
    dependencies = [("organizations", "0117_cep033_ap_source_reversal_permission")]
    operations = [migrations.RunPython(forward, reverse)]
