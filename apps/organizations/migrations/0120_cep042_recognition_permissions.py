"""Explicit CEP-042 catalog only; preserve every existing role grant."""

from django.db import migrations

PERMISSIONS = (
    ("accounting_recognition.mappings_manage", "تهیه نگاشت شناسایی حسابداری"),
    ("accounting_recognition.mappings_approve", "پذیرش مستقل نگاشت شناسایی"),
    ("accounting_recognition.prepare", "تهیه و تلاش مجدد پیش‌نویس شناسایی"),
    ("accounting_recognition.view", "مشاهده و تطبیق شناسایی حسابداری"),
)


def forward(apps, schema_editor):
    permission = apps.get_model("organizations", "BusinessPermission")
    for code, name in PERMISSIONS:
        permission.objects.using(schema_editor.connection.alias).update_or_create(
            code=code, defaults={"name": name, "description": name, "is_active": True}
        )


def reverse(apps, schema_editor):
    apps.get_model("organizations", "BusinessPermission").objects.using(
        schema_editor.connection.alias
    ).filter(code__in=[code for code, _ in PERMISSIONS]).update(is_active=False)


class Migration(migrations.Migration):
    dependencies = [("organizations", "0119_cep037_variation_eligibility_permissions")]
    operations = [migrations.RunPython(forward, reverse)]
