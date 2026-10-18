# ruff: noqa: RUF012
"""Register distinct inquiry operations without assigning any tenant role."""

from django.db import migrations

PERMISSIONS = (
    ("payroll_ess.view_own", "مشاهده حقوق قطعی شخصی"),
    ("payroll_ess.export_own", "دریافت فیش قطعی شخصی"),
    ("payroll_inquiries.view", "مشاهده پرسش مجاز حقوق"),
    ("payroll_inquiries.request", "ثبت پرسش حقوق شخصی"),
    ("payroll_inquiries.respond", "پاسخ به پرسش تخصیص‌یافته حقوق"),
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
    dependencies = [("organizations", "0110_cep027_record_review_permissions")]
    operations = [migrations.RunPython(forward, reverse)]
