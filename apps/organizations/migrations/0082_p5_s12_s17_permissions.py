from typing import ClassVar

from django.db import migrations

PERMISSIONS = (
    ("purchase_order_changes.request", "درخواست تغییر سفارش خرید"),
    ("purchase_order_changes.approve", "تأیید مستقل تغییر سفارش خرید"),
    ("service_acceptances.view", "مشاهده پذیرش خدمت"),
    ("service_acceptances.create", "ایجاد پذیرش خدمت"),
    ("service_acceptances.accept", "نهایی‌سازی پذیرش خدمت"),
    ("service_acceptances.void", "ابطال پذیرش خدمت"),
    ("supplier_invoices.view", "مشاهده صورتحساب تأمین‌کننده"),
    ("supplier_invoices.prepare", "آماده‌سازی صورتحساب تأمین‌کننده"),
    ("supplier_invoices.approve", "تأیید مستقل صورتحساب تأمین‌کننده"),
    ("invoice_match_policies.manage", "آماده‌سازی سیاست رواداری تطبیق"),
    ("invoice_match_policies.approve", "تأیید مستقل سیاست رواداری تطبیق"),
    ("invoice_matches.view", "مشاهده تطبیق صورتحساب"),
    ("invoice_matches.run", "اجرای تطبیق صورتحساب"),
)

MANAGEMENT_ROLES = (
    "tenant_owner",
    "company_owner",
    "tenant_admin",
    "tenant_manager",
    "project_manager",
    "company_manager",
    "operations_manager",
)
SERVICE_ROLES = MANAGEMENT_ROLES + (
    "supervisor",
    "member",
)
AP_ROLES = ("tenant_owner", "company_owner", "tenant_admin", "accountant")
AP_PREFIXES = ("supplier_invoices.", "invoice_match_policies.", "invoice_matches.")


def forward(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    Role = apps.get_model("organizations", "OrganizationRole")
    permissions = {}
    for code, name in PERMISSIONS:
        permission, _ = Permission.objects.update_or_create(
            code=code,
            defaults={"name": name, "description": name, "is_active": True},
        )
        permissions[code] = permission
    for code, permission in permissions.items():
        if code.startswith(AP_PREFIXES):
            role_codes = AP_ROLES
        elif code.startswith("service_acceptances."):
            role_codes = SERVICE_ROLES
        else:
            role_codes = MANAGEMENT_ROLES
        for role in Role.objects.filter(code__in=role_codes, organization__isnull=True):
            role.permissions.add(permission)


def reverse(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    Permission.objects.filter(code__in=[code for code, _ in PERMISSIONS]).delete()


class Migration(migrations.Migration):
    dependencies: ClassVar[list[tuple[str, str]]] = [
        ("organizations", "0081_p5_s11_comparison_award_permissions"),
    ]
    operations: ClassVar[list] = [migrations.RunPython(forward, reverse)]
