# ruff: noqa: RUF012
"""Catalogue indexation capabilities without assigning any tenant role."""

from django.db import migrations

PERMISSIONS = (
    ("indexation_rules.manage", "تهیه نسخه قانون تعدیل"),
    ("indexation.calculate", "محاسبه تعدیل با سیاست مجاز"),
    ("indexation.correct", "اصلاح و برگشت تعدیل با سیاست مجاز"),
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
    dependencies = [("organizations", "0113_cep056_certificate_permissions")]
    operations = [migrations.RunPython(forward, reverse)]
