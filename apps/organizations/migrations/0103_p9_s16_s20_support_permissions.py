from typing import ClassVar

from django.db import migrations

PERMISSIONS = (
    ("support.notifications_view", "مشاهده اعلان‌ها"),
    ("support.notifications_acknowledge", "تأیید اعلان‌ها"),
    ("support.calendar_view", "مشاهده تقویم نظارتی"),
    ("support.case_create", "ایجاد مورد پشتیبانی"),
    ("support.case_view", "مشاهده مورد پشتیبانی"),
    ("support.case_update", "به‌روزرسانی مورد پشتیبانی"),
    ("support.case_assign", "تخصیص مورد پشتیبانی"),
    ("support.case_resolve", "حل و بستن مورد پشتیبانی"),
    ("support.case_reopen", "بازگشایی مورد پشتیبانی"),
    ("support.evidence_link", "پیوند شواهد پشتیبانی"),
    ("support.evidence_sensitive_view", "مشاهده شواهد حساس پشتیبانی"),
    ("support.access_request", "درخواست دسترسی پشتیبانی"),
    ("support.access_tenant_confirm", "تأیید Tenant دسترسی پشتیبانی"),
    ("support.access_platform_approve", "تأیید پلتفرم دسترسی پشتیبانی"),
    ("support.access_use", "استفاده از دسترسی پشتیبانی"),
    ("support.access_revoke", "ابطال دسترسی پشتیبانی"),
    ("support.audit_reconcile", "ممیزی و تطبیق پشتیبانی"),
)


def forward(apps, schema_editor):
    del schema_editor
    model = apps.get_model("organizations", "BusinessPermission")
    for code, name in PERMISSIONS:
        model.objects.update_or_create(
            code=code, defaults={"name": name, "description": name, "is_active": True}
        )


def reverse(apps, schema_editor):
    del schema_editor
    apps.get_model("organizations", "BusinessPermission").objects.filter(
        code__in=[x[0] for x in PERMISSIONS]
    ).delete()


class Migration(migrations.Migration):
    dependencies: ClassVar[list] = [
        ("organizations", "0102_p9_s12_s15_partner_permissions")
    ]
    operations: ClassVar[list] = [migrations.RunPython(forward, reverse)]
