from typing import ClassVar

from django.db import migrations

PERMISSIONS = (
    ("inventory_valuation.view", "مشاهده ارزش‌گذاری موجودی"),
    ("inventory_valuation.prepare", "تهیه ارزش‌گذاری موجودی"),
    ("inventory_valuation.reverse", "برگشت ارزش‌گذاری موجودی"),
    ("inventory_valuation.reconcile", "تطبیق ارزش‌گذاری موجودی"),
    ("inventory_valuation.supply", "ارسال پیشنهاد هزینه موجودی"),
)

def forward(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    Role = apps.get_model("organizations", "OrganizationRole")
    records = {code: Permission.objects.update_or_create(code=code, defaults={"name": name, "description": name, "is_active": True})[0] for code, name in PERMISSIONS}
    for role in Role.objects.filter(organization__isnull=True):
        codes = {"inventory_valuation.view"}
        if role.code in {"tenant_owner", "company_owner", "tenant_admin", "tenant_manager", "project_manager", "company_manager", "operations_manager", "supervisor"}:
            codes.add("inventory_valuation.prepare")
        if role.code in {"tenant_owner", "company_owner", "tenant_admin", "tenant_manager", "company_manager", "operations_manager"}:
            codes |= {"inventory_valuation.reverse", "inventory_valuation.reconcile", "inventory_valuation.supply"}
        role.permissions.add(*(records[code] for code in codes))

def reverse(apps, schema_editor):
    del schema_editor
    apps.get_model("organizations", "BusinessPermission").objects.filter(code__in=[code for code, _ in PERMISSIONS]).delete()

class Migration(migrations.Migration):
    dependencies: ClassVar[list] = [("organizations", "0096_p8_s05_s11_inventory_custody_permissions")]
    operations: ClassVar[list] = [migrations.RunPython(forward, reverse)]

