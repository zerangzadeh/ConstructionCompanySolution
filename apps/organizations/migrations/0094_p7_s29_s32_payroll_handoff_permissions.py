from typing import ClassVar

from django.db import migrations

PERMISSIONS = (
    ("payroll_liability_handoff.prepare", "تهیه پیشنهاد بدهی حقوق"),
    ("payroll_liability_handoff.review", "بررسی پیشنهاد بدهی حقوق"),
    ("payroll_accounting_handoff.prepare", "تهیه پیشنهاد حسابداری حقوق"),
    ("payroll_accounting_handoff.review", "بررسی پیشنهاد حسابداری حقوق"),
    ("payroll_payment_handoff.prepare", "تهیه پیشنهاد پرداخت حقوق"),
    ("payroll_payment_handoff.review", "بررسی پیشنهاد پرداخت حقوق"),
    ("payroll_project_cost_handoff.prepare", "تهیه پیشنهاد هزینه کار حقوق"),
    ("payroll_project_cost_handoff.review", "بررسی پیشنهاد هزینه کار حقوق"),
    ("payroll_handoff_reconciliation.prepare", "تهیه تطبیق تحویل مالی حقوق"),
    ("payroll_handoff_reconciliation.review", "بررسی تطبیق تحویل مالی حقوق"),
)


def forward(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    for code, name in PERMISSIONS:
        Permission.objects.update_or_create(
            code=code, defaults={"name": name, "description": name, "is_active": True}
        )
    # Financial handoffs expose sensitive Payroll facts; no role receives a default grant.


def reverse(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    Permission.objects.filter(code__in=[code for code, _ in PERMISSIONS]).delete()


class Migration(migrations.Migration):
    dependencies: ClassVar[list] = [
        ("organizations", "0093_p7_s23_s28_statutory_payroll_permissions"),
    ]
    operations: ClassVar[list] = [migrations.RunPython(forward, reverse)]
