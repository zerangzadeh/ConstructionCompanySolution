from typing import ClassVar

from django.db import migrations


PERMISSIONS = (
    ("compliance.view", "مشاهده بازرسی و کنترل HSE/QA"),
    ("compliance.templates_manage", "مدیریت پیش‌نویس الگوی بازرسی"),
    ("compliance.templates_publish", "بررسی و انتشار الگوی بازرسی"),
    ("compliance.inspections_create", "ایجاد و برنامه‌ریزی بازرسی"),
    ("compliance.inspections_execute", "اجرای بازرسی"),
    ("compliance.inspections_submit", "ارسال بازرسی"),
    ("compliance.inspections_review", "بررسی و نتیجه‌دهی بازرسی"),
    ("compliance.findings_create", "ثبت یافته بازرسی یا آزمون"),
    ("compliance.findings_classify", "طبقه‌بندی یافته"),
    ("compliance.findings_manage", "تخصیص و مدیریت یافته"),
    ("compliance.permits_prepare", "تهیه و ارسال مجوز HSE"),
    ("compliance.permits_issue", "بررسی و صدور مجوز HSE"),
    ("compliance.permits_control", "تعلیق، اعاده و ابطال مجوز HSE"),
    ("compliance.tests_request", "درخواست آزمون QA/QC"),
    ("compliance.tests_execute", "اجرا و ثبت نتیجه آزمون"),
    ("compliance.tests_review", "بررسی، پذیرش یا بی‌اعتبارسازی نتیجه آزمون"),
    ("compliance.ncr_manage", "صدور و مدیریت عدم انطباق رسمی"),
    ("compliance.capa_assign", "تأیید و تخصیص CAPA"),
    ("compliance.capa_execute", "اجرای CAPA"),
    ("compliance.verify", "راستی‌آزمایی مستقل اقدام"),
    ("compliance.effectiveness_review", "ارزیابی اثربخشی CAPA"),
    ("compliance.close", "بستن یافته، NCR یا CAPA"),
    ("compliance.reopen", "بازگشایی کنترل‌شده یافته، NCR یا CAPA"),
    ("compliance.evidence_link", "پیوند نسخه شواهد HSE/QA"),
    ("compliance.sensitive_evidence_view", "مشاهده شواهد حساس HSE/QA"),
    ("compliance.export", "خروجی کنترل‌شده HSE/QA"),
    ("compliance.audit_reconcile", "ممیزی و تطبیق HSE/QA"),
)


def forward(apps, schema_editor):
    del schema_editor
    permission_model = apps.get_model("organizations", "BusinessPermission")
    role_model = apps.get_model("organizations", "OrganizationRole")
    records = {
        code: permission_model.objects.update_or_create(
            code=code,
            defaults={"name": name, "description": name, "is_active": True},
        )[0]
        for code, name in PERMISSIONS
    }
    view = {"compliance.view"}
    field = {
        "compliance.inspections_create",
        "compliance.inspections_execute",
        "compliance.inspections_submit",
        "compliance.findings_create",
        "compliance.permits_prepare",
        "compliance.tests_request",
        "compliance.tests_execute",
        "compliance.capa_execute",
        "compliance.evidence_link",
    }
    control = {code for code, _ in PERMISSIONS} - view - field - {
        "compliance.sensitive_evidence_view"
    }
    managers = {
        "tenant_owner", "tenant_admin", "tenant_manager", "company_owner",
        "company_manager", "operations_manager", "project_manager",
    }
    for role in role_model.objects.filter(organization__isnull=True):
        codes = set(view)
        if role.code in managers:
            codes |= field | control
        elif role.code == "supervisor":
            codes |= field
        role.permissions.add(*(records[code] for code in codes))


def reverse(apps, schema_editor):
    del schema_editor
    apps.get_model("organizations", "BusinessPermission").objects.filter(
        code__in=[code for code, _ in PERMISSIONS]
    ).delete()


class Migration(migrations.Migration):
    dependencies: ClassVar[list] = [
        ("organizations", "0100_p9_s01_s05_field_operations_permissions"),
    ]
    operations: ClassVar[list] = [migrations.RunPython(forward, reverse)]
