"""Bounded annual accounting authority; no platform authority or bypass grant."""
from django.db import migrations

PERMISSIONS = (
    ("accounting.year_end_view", "مشاهده بستن سال مالی"),
    ("accounting.year_end_configure", "تنظیم حساب‌های بستن سال"),
    ("accounting.year_end_prepare", "تهیه بستن سال مالی"),
    ("accounting.year_end_approve", "تأیید بستن سال و افتتاحیه"),
    ("accounting.year_end_reopen", "بازگشایی سال مالی"),
)


def forward(apps, schema_editor):
    permission = apps.get_model("organizations", "BusinessPermission")
    role = apps.get_model("organizations", "OrganizationRole")
    alias = schema_editor.connection.alias
    for code, name in PERMISSIONS:
        item, _ = permission.objects.using(alias).update_or_create(code=code, defaults={"name": name, "description": name, "is_active": True})
        for accounting_role in role.objects.using(alias).filter(organization__isnull=True, code__in=["tenant_owner", "tenant_admin", "accountant"]):
            accounting_role.permissions.add(item)


def reverse(apps, schema_editor):
    apps.get_model("organizations", "BusinessPermission").objects.using(schema_editor.connection.alias).filter(code__in=[code for code, _ in PERMISSIONS]).update(is_active=False)


class Migration(migrations.Migration):
    dependencies = [("organizations", "0123_insuranceclassification_and_more")]
    operations = [migrations.RunPython(forward, reverse)]
