"""Explicit Variation eligibility retry/view catalogue; no default grants."""
from django.db import migrations

PERMISSIONS = (
    ("billing_variation_eligibility.view", "مشاهده اهلیت منبع تغییر"),
    ("billing_variation_eligibility.retry", "تلاش مجدد پذیرش منبع تغییر"),
)

def forward(apps, schema_editor):
    model = apps.get_model("organizations", "BusinessPermission")
    for code, name in PERMISSIONS:
        model.objects.using(schema_editor.connection.alias).update_or_create(code=code, defaults={"name":name,"description":name,"is_active":True})

def reverse(apps, schema_editor):
    apps.get_model("organizations", "BusinessPermission").objects.using(schema_editor.connection.alias).filter(code__in=[c for c,_ in PERMISSIONS]).update(is_active=False)

class Migration(migrations.Migration):
    dependencies = [("organizations", "0118_cep035_price_book_permissions")]
    operations = [migrations.RunPython(forward, reverse)]
