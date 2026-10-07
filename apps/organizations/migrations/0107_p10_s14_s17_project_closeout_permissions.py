# ruff: noqa: RUF012

from django.db import migrations


PERMISSIONS = (
    ("reporting.project_closeout_profile.view", "مشاهده الگوی اختتام پروژه"),
    ("reporting.project_closeout_profile.prepare", "تهیه الگوی اختتام پروژه"),
    ("reporting.project_closeout_profile.publish", "انتشار الگوی اختتام پروژه"),
    ("reporting.project_closeout_case.view", "مشاهده پرونده اختتام پروژه"),
    ("reporting.project_closeout_case.prepare", "تهیه و ارزیابی پرونده اختتام پروژه"),
    ("reporting.project_closeout_case.coordinate", "هماهنگی پرونده اختتام پروژه"),
    ("reporting.project_closeout_case.review", "بررسی پرونده اختتام پروژه"),
    ("reporting.project_closeout_case.accept", "پذیرش کنترل‌شده پرونده اختتام پروژه"),
    ("reporting.project_closeout_case.reopen", "بازگشایی پرونده اختتام پروژه"),
    ("reporting.project_closeout_evidence.link", "پیوند شاهد اختتام پروژه"),
    ("reporting.project_closeout_sensitive.view", "مشاهده داده حساس اختتام پروژه"),
    ("reporting.project_closeout_export.create", "ایجاد خروجی اختتام پروژه"),
    ("reporting.project_closeout_export.download", "دریافت خروجی اختتام پروژه"),
    ("reporting.project_closeout_audit.view", "مشاهده ممیزی اختتام پروژه"),
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
    dependencies = [("organizations", "0106_p10_s07_s13_reconciliation_permissions")]
    operations = [migrations.RunPython(forward, reverse)]
