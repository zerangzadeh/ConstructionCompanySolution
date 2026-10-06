from typing import ClassVar

from django.db import migrations


PERMISSIONS = (
    ("equipment_operations.view", "مشاهده عملیات تجهیز"),
    ("equipment_meters.record", "ثبت قرائت تجهیز"),
    ("equipment_meters.correct", "اصلاح قرائت تجهیز"),
    ("equipment_usage.record", "ثبت کارکرد تجهیز"),
    ("equipment_fuel.record", "ثبت سوخت تجهیز"),
    ("equipment_downtime.manage", "مدیریت توقف تجهیز"),
    ("equipment_qualifications.manage", "مدیریت صلاحیت اپراتور تجهیز"),
    ("equipment_maintenance_plans.manage", "مدیریت برنامه نگهداری"),
    ("equipment_work_orders.manage", "مدیریت دستورکار نگهداری"),
    ("equipment_work_orders.complete", "تکمیل دستورکار نگهداری"),
    ("equipment_work_orders.reopen", "بازگشایی دستورکار نگهداری"),
    ("equipment_spare_links.manage", "پیوند قطعات یدکی تجهیز"),
    ("equipment_spare_links.reconcile", "تطبیق قطعات یدکی تجهیز"),
)


def forward(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    Role = apps.get_model("organizations", "OrganizationRole")
    records = {code: Permission.objects.update_or_create(code=code, defaults={"name": name, "description": name, "is_active": True})[0] for code, name in PERMISSIONS}
    for role in Role.objects.filter(organization__isnull=True):
        codes = {"equipment_operations.view"}
        if role.code in {"tenant_owner", "company_owner", "tenant_admin", "tenant_manager", "project_manager", "company_manager", "operations_manager", "supervisor"}:
            codes |= {code for code, _ in PERMISSIONS if code not in {"equipment_meters.correct", "equipment_work_orders.reopen", "equipment_spare_links.reconcile"}}
        if role.code in {"tenant_owner", "company_owner", "tenant_admin", "tenant_manager", "company_manager", "operations_manager"}:
            codes |= {"equipment_meters.correct", "equipment_work_orders.reopen", "equipment_spare_links.reconcile"}
        role.permissions.add(*(records[code] for code in codes))


def reverse(apps, schema_editor):
    del schema_editor
    apps.get_model("organizations", "BusinessPermission").objects.filter(code__in=[code for code, _ in PERMISSIONS]).delete()


class Migration(migrations.Migration):
    dependencies: ClassVar[list] = [("organizations", "0097_p8_s12_s17_inventory_valuation_permissions")]
    operations: ClassVar[list] = [migrations.RunPython(forward, reverse)]
