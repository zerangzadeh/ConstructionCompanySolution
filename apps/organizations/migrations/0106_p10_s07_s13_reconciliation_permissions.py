# ruff: noqa: RUF012

from django.db import migrations


PERMISSIONS = (
    ("reporting.reconciliation_catalog.view", "مشاهده کاتالوگ تطبیق"),
    ("reporting.reconciliation_definition.prepare", "تهیه تعریف تطبیق"),
    ("reporting.reconciliation_definition.publish", "انتشار تعریف تطبیق"),
    ("reporting.reconciliation_run.execute", "اجرای تطبیق"),
    ("reporting.reconciliation_run.view", "مشاهده اجرای تطبیق"),
    ("reporting.reconciliation_run.review", "بررسی اجرای تطبیق"),
    ("reporting.reconciliation_exception.view", "مشاهده مغایرت تطبیق"),
    ("reporting.reconciliation_exception.assign", "ارجاع مغایرت تطبیق"),
    ("reporting.reconciliation_exception.disposition", "ثبت تصمیم مغایرت تطبیق"),
    ("reporting.reconciliation_exception.close", "بستن مغایرت تطبیق"),
    ("reporting.reconciliation_exception.reopen", "بازگشایی مغایرت تطبیق"),
    ("reporting.reconciliation_evidence.link", "پیوند شاهد مغایرت تطبیق"),
    ("reporting.reconciliation_rebuild.execute", "اجرای بازسازی تطبیق"),
    ("reporting.reconciliation_rebuild.review", "بررسی بازسازی تطبیق"),
    ("reporting.reconciliation_audit.view", "مشاهده ممیزی تطبیق"),
)


def forward(apps, schema_editor):
    del schema_editor
    model = apps.get_model("organizations", "BusinessPermission")
    for code, name in PERMISSIONS:
        model.objects.update_or_create(
            code=code,
            defaults={"name": name, "description": name, "is_active": True},
        )


def reverse(apps, schema_editor):
    del schema_editor
    apps.get_model("organizations", "BusinessPermission").objects.filter(
        code__in=[code for code, _ in PERMISSIONS]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("organizations", "0105_p10_s02_s06_reporting_permissions")]
    operations = [migrations.RunPython(forward, reverse)]
