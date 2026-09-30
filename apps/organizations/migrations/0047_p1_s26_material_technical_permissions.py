from django.db import migrations


PERMISSIONS = (
    ("material_relationships.manage", "مدیریت هم‌ارز/جایگزین مصالح"),
    ("material_technical.submit", "ارسال بررسی فنی مصالح"),
    ("material_technical.review", "بازبینی فنی مصالح"),
    ("material_technical.approve", "تأیید فنی مصالح"),
    ("material_documents.link", "پیوند سند فنی مصالح"),
)


def forward(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    Role = apps.get_model("organizations", "OrganizationRole")
    records = [Permission.objects.update_or_create(code=code, defaults={"name": name, "description": name, "is_active": True})[0] for code, name in PERMISSIONS]
    for role in Role.objects.filter(code__in=("tenant_owner", "tenant_admin", "company_owner"), organization__isnull=True):
        role.permissions.add(*records)


class Migration(migrations.Migration):
    dependencies = [("organizations", "0046_p1_s25_material_attribute_permissions")]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
