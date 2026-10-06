from typing import ClassVar

from django.db import migrations

PERMISSIONS = (
    ("inventory_reservations.view", "مشاهده رزروهای موجودی"),
    ("inventory_reservations.manage", "ایجاد و تخصیص رزرو موجودی"),
    ("inventory_reservations.release", "آزادسازی یا لغو رزرو موجودی"),
    ("inventory_traceability.view", "مشاهده رهگیری موجودی"),
    ("inventory_traceability.manage", "مدیریت مکان و رهگیری موجودی"),
    ("inventory_traceability.dispose", "تعیین تکلیف قرنطینه یا انقضای موجودی"),
    ("inventory_counts.view", "مشاهده شمارش موجودی"),
    ("inventory_counts.prepare", "آماده‌سازی و ثبت شمارش موجودی"),
    ("inventory_counts.approve", "تأیید مستقل شمارش موجودی"),
    ("inventory_counts.post", "ثبت تعدیل شمارش موجودی"),
    ("inventory_transfers.view", "مشاهده انتقال‌های امانی موجودی"),
    ("inventory_transfers.prepare", "آماده‌سازی انتقال امانی موجودی"),
    ("inventory_transfers.dispatch", "ارسال انتقال امانی موجودی"),
    ("inventory_transfers.accept", "پذیرش مستقل انتقال امانی موجودی"),
    ("inventory_transfers.resolve", "تعیین تکلیف مغایرت انتقال موجودی"),
    ("inventory_reconciliations.view", "مشاهده تطبیق مقدار و امانت موجودی"),
)

VIEW_CODES = {
    "inventory_reservations.view",
    "inventory_traceability.view",
    "inventory_counts.view",
    "inventory_transfers.view",
    "inventory_reconciliations.view",
}
PREPARE_CODES = {
    "inventory_reservations.manage",
    "inventory_reservations.release",
    "inventory_counts.prepare",
    "inventory_transfers.prepare",
    "inventory_transfers.dispatch",
}
CONTROL_CODES = {
    "inventory_traceability.manage",
    "inventory_traceability.dispose",
    "inventory_counts.approve",
    "inventory_counts.post",
    "inventory_transfers.accept",
    "inventory_transfers.resolve",
}
MANAGEMENT_ROLES = {
    "tenant_owner",
    "company_owner",
    "tenant_admin",
    "tenant_manager",
    "project_manager",
    "company_manager",
    "operations_manager",
}
PREPARER_ROLES = MANAGEMENT_ROLES | {"supervisor"}
VIEWER_ROLES = PREPARER_ROLES | {"member", "viewer"}


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

    for role in Role.objects.filter(organization__isnull=True):
        grant_codes = set()
        if role.code in VIEWER_ROLES:
            grant_codes |= VIEW_CODES
        if role.code in PREPARER_ROLES:
            grant_codes |= PREPARE_CODES
        if role.code in MANAGEMENT_ROLES:
            grant_codes |= CONTROL_CODES
        role.permissions.add(*(permissions[code] for code in grant_codes))


def reverse(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    Permission.objects.filter(code__in=[code for code, _ in PERMISSIONS]).delete()


class Migration(migrations.Migration):
    dependencies: ClassVar[list] = [
        ("organizations", "0095_p7_role_permission_seed_reconciliation"),
    ]
    operations: ClassVar[list] = [migrations.RunPython(forward, reverse)]
