# ruff: noqa: RUF012
"""Catalogue only; no default or existing tenant-role grants."""

from django.db import migrations

PERMISSIONS = (
    ("employment_records.manage", "ثبت نسخه سابقه استخدام"),
    ("employment_records.view_own", "مشاهده سوابق استخدام شخصی"),
    ("offboarding.start", "آغاز بررسی تسویه همکاری"),
    ("offboarding.view", "مشاهده پرونده مجاز پایان همکاری"),
    ("offboarding.review", "ثبت بررسی تخصیص‌یافته پایان همکاری"),
    ("rosters.manage", "ثبت نسخه برنامه شیفت"),
    ("rosters.view", "مشاهده برنامه شیفت مجاز"),
)


def forward(apps, schema_editor):
    for code, name in PERMISSIONS:
        apps.get_model("organizations", "BusinessPermission").objects.using(
            schema_editor.connection.alias
        ).update_or_create(
            code=code, defaults={"name": name, "description": name, "is_active": True}
        )


def reverse(apps, schema_editor):
    apps.get_model("organizations", "BusinessPermission").objects.using(
        schema_editor.connection.alias
    ).filter(code__in=[c for c, _ in PERMISSIONS]).update(is_active=False)


class Migration(migrations.Migration):
    dependencies = [("organizations", "0114_cep036_indexation_permissions")]
    operations = [migrations.RunPython(forward, reverse)]
