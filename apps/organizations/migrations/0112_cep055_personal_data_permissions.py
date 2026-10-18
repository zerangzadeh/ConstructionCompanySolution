# ruff: noqa: RUF012
"""Register personal data operations without assigning any tenant role."""

from django.db import migrations

PERMISSIONS = (
    ("personal_data.view", "مشاهده درخواست تغییر اطلاعات مجاز"),
    ("personal_data.request", "درخواست تغییر اطلاعات شخصی"),
    ("personal_data.review", "تصمیم تغییر اطلاعات تخصیص‌یافته"),
    ("personal_data.configure", "پیکربندی ثبت تغییر اطلاعات"),
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
    dependencies = [("organizations", "0111_cep054_payroll_inquiry_permissions")]
    operations = [migrations.RunPython(forward, reverse)]
