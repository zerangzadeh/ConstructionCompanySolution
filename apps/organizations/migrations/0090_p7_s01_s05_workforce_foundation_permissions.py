from typing import ClassVar

from django.db import migrations


GENERAL_PERMISSIONS = (
    ("workforce_skills.view", "مشاهده مهارت‌ها و شایستگی‌ها"),
    ("workforce_skills.manage", "مدیریت مهارت‌ها و شایستگی‌ها"),
    ("workforce_qualifications.view", "مشاهده صلاحیت‌ها و آموزش کارکنان"),
    ("workforce_qualifications.manage", "مدیریت صلاحیت‌ها و آموزش کارکنان"),
    ("workforce_qualifications.revoke", "ابطال یا جایگزینی صلاحیت کارکنان"),
)
SENSITIVE_PERMISSIONS = (
    ("workforce_performance.view", "مشاهده ارزیابی عملکرد حساس"),
    ("workforce_performance.manage", "ثبت ارزیابی عملکرد حساس"),
    ("workforce_labor_rates.view", "مشاهده نرخ حساس نیروی کار"),
    ("workforce_labor_rates.manage", "ثبت نسخه نرخ حساس نیروی کار"),
)
MANAGEMENT_ROLE_CODES = (
    "tenant_owner",
    "company_owner",
    "tenant_admin",
    "tenant_manager",
    "project_manager",
    "company_manager",
    "operations_manager",
)


def forward(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    Role = apps.get_model("organizations", "OrganizationRole")
    permissions = {}
    for code, name in GENERAL_PERMISSIONS + SENSITIVE_PERMISSIONS:
        permissions[code], _ = Permission.objects.update_or_create(
            code=code,
            defaults={"name": name, "description": name, "is_active": True},
        )
    for role in Role.objects.filter(code__in=MANAGEMENT_ROLE_CODES, organization__isnull=True):
        role.permissions.add(*(permissions[code] for code, _ in GENERAL_PERMISSIONS))
    # Sensitive performance and labor-rate capabilities intentionally receive no
    # default grant. Tenant role administrators must assign them explicitly.


def reverse(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    Permission.objects.filter(
        code__in=[code for code, _ in GENERAL_PERMISSIONS + SENSITIVE_PERMISSIONS]
    ).delete()


class Migration(migrations.Migration):
    dependencies: ClassVar[list] = [
        ("organizations", "0089_p6_s33_s38_contractual_record_permissions"),
    ]
    operations: ClassVar[list] = [migrations.RunPython(forward, reverse)]
