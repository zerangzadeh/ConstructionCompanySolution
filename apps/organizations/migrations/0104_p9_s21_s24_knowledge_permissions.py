# ruff: noqa: RUF012

from django.db import migrations

PERMISSIONS = (
    ("knowledge.candidates_create", "ایجاد پیش‌نویس دانش"),
    ("knowledge.candidates_submit", "ارسال کاندید دانش"),
    ("knowledge.candidates_review", "بررسی کاندید دانش"),
    ("knowledge.publications_approve", "تأیید انتشار دانش"),
    ("knowledge.publications_publish", "انتشار دانش"),
    ("knowledge.publications_view", "مشاهده دانش منتشرشده"),
    ("knowledge.unpublished_view", "مشاهده کاندیدهای دانش"),
    ("knowledge.publications_supersede", "جایگزینی انتشار دانش"),
    ("knowledge.publications_withdraw", "پس‌گرفتن انتشار دانش"),
    ("knowledge.history_view", "مشاهده تاریخچه دانش"),
    ("knowledge.sensitive_provenance_view", "مشاهده منبع حساس دانش"),
    ("knowledge.recurrence_record", "ثبت شواهد تکرار"),
    ("knowledge.reuse_record", "ثبت استفاده مجدد دانش"),
    ("knowledge.taxonomy_manage", "مدیریت طبقه‌بندی دانش"),
    ("knowledge.export", "خروجی کنترل‌شده دانش"),
    ("knowledge.audit_reconcile", "ممیزی و تطبیق دانش"),
)


def forward(apps, schema_editor):
    del schema_editor
    model = apps.get_model("organizations", "BusinessPermission")
    for code, name in PERMISSIONS:
        model.objects.update_or_create(code=code, defaults={"name": name, "description": name, "is_active": True})


def reverse(apps, schema_editor):
    del schema_editor
    apps.get_model("organizations", "BusinessPermission").objects.filter(code__in=[code for code, _ in PERMISSIONS]).delete()


class Migration(migrations.Migration):
    dependencies = [("organizations", "0103_p9_s16_s20_support_permissions")]
    operations = [migrations.RunPython(forward, reverse)]
