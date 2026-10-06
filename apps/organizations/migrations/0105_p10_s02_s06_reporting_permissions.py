# ruff: noqa: RUF012

from django.db import migrations

PERMISSIONS = (
    ("reporting.metric_catalog.view", "مشاهده کاتالوگ شاخص‌های حاکم‌شده"),
    ("reporting.metric_definition.prepare", "تهیه تعریف شاخص"),
    ("reporting.metric_definition.review", "بررسی تعریف شاخص"),
    ("reporting.metric_definition.publish", "انتشار تعریف شاخص"),
    ("reporting.metric_result.view", "مشاهده نتیجه شاخص"),
    ("reporting.metric_result.view_sensitive", "مشاهده نتیجه حساس شاخص"),
    ("reporting.portfolio.view", "مشاهده شاخص‌های سبد پروژه"),
    ("reporting.metric_refresh.run", "اجرای بازسازی شاخص"),
    ("reporting.metric_refresh.review", "بررسی نتیجه بازسازی شاخص"),
    ("reporting.source_drillthrough.view", "مشاهده مسیر منبع شاخص"),
    ("reporting.saved_view.manage_own", "مدیریت نمای ذخیره‌شده شخصی"),
    ("reporting.saved_view.manage_shared", "مدیریت نمای ذخیره‌شده مشترک"),
    ("reporting.export.create", "ایجاد خروجی کنترل‌شده شاخص"),
    ("reporting.export.download", "دریافت خروجی کنترل‌شده شاخص"),
    ("reporting.export.sensitive", "خروجی حساس شاخص"),
    ("reporting.audit.view", "مشاهده ممیزی گزارش‌گیری"),
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
    dependencies = [("organizations", "0104_p9_s21_s24_knowledge_permissions")]
    operations = [migrations.RunPython(forward, reverse)]
