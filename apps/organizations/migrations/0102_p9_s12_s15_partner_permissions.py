from typing import ClassVar

from django.db import migrations

PERMISSIONS = (
    ("partner.view", "مشاهده صلاحیت و عملکرد همکار"), ("partner.profile_manage", "مدیریت پروفایل همکار"), ("partner.requirements_manage", "انتشار الزام صلاحیت"), ("partner.qualifications_prepare", "تهیه صلاحیت همکار"), ("partner.qualifications_submit", "ارسال صلاحیت همکار"), ("partner.qualifications_review", "بررسی صلاحیت همکار"), ("partner.qualifications_control", "کنترل صلاحیت همکار"), ("partner.category_decide", "تصمیم صلاحیت دسته همکار"), ("partner.evidence_link", "پیوند شواهد صلاحیت همکار"), ("partner.sensitive_evidence_view", "مشاهده شواهد حساس همکار"), ("partner.evaluations_prepare", "تهیه ارزیابی عملکرد همکار"), ("partner.evaluations_submit", "ارسال ارزیابی عملکرد همکار"), ("partner.evaluations_publish", "انتشار ارزیابی عملکرد همکار"), ("partner.evaluations_appeal", "اعتراض و تصمیم ارزیابی همکار"), ("partner.proposals_create", "ایجاد پیشنهاد صلاحیت همکار"), ("partner.export", "خروجی کنترل‌شده همکار"), ("partner.audit_reconcile", "ممیزی و تطبیق همکار"),
)

def forward(apps, schema_editor):
    del schema_editor
    permissions = apps.get_model("organizations", "BusinessPermission")
    roles = apps.get_model("organizations", "OrganizationRole")
    records = {code: permissions.objects.update_or_create(code=code, defaults={"name": name, "description": name, "is_active": True})[0] for code, name in PERMISSIONS}
    view = {"partner.view"}
    field = {"partner.profile_manage", "partner.qualifications_prepare", "partner.qualifications_submit", "partner.evidence_link", "partner.evaluations_prepare", "partner.evaluations_submit", "partner.evaluations_appeal", "partner.proposals_create"}
    control = {code for code, _ in PERMISSIONS} - view - field - {"partner.sensitive_evidence_view"}
    managers = {"tenant_owner", "tenant_admin", "tenant_manager", "company_owner", "company_manager", "operations_manager", "project_manager"}
    for role in roles.objects.filter(organization__isnull=True):
        codes = set(view)
        if role.code in managers: codes |= field | control
        elif role.code == "supervisor": codes |= field
        role.permissions.add(*(records[code] for code in codes))

def reverse(apps, schema_editor):
    del schema_editor
    apps.get_model("organizations", "BusinessPermission").objects.filter(code__in=[code for code, _ in PERMISSIONS]).delete()

class Migration(migrations.Migration):
    dependencies: ClassVar[list] = [("organizations", "0101_p9_s06_s11_compliance_permissions")]
    operations: ClassVar[list] = [migrations.RunPython(forward, reverse)]
