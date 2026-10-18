# ruff: noqa: RUF012
"""Register personal data operations without assigning any tenant role."""

from django.db import migrations

PERMISSIONS = (
    ("ess_evidence.view_own", "مشاهده سوابق و شواهد شخصی"),
    ("hr_certificates.view", "مشاهده درخواست گواهی مجاز"),
    ("hr_certificates.request", "درخواست گواهی شخصی"),
    ("hr_certificates.review", "بررسی گواهی تخصیص‌یافته"),
    ("hr_certificates.generate", "تولید گواهی با سیاست مجاز"),
    ("hr_certificates.configure", "پیکربندی چارچوب گواهی"),
    ("hr_certificates.cancel", "لغو گواهی طبق سیاست منبع"),
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
    dependencies = [("organizations", "0112_cep055_personal_data_permissions")]
    operations = [migrations.RunPython(forward, reverse)]
