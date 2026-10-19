"""CEP-023 catalog only; no existing or default role grants."""

from django.db import migrations

PERMISSIONS = (
    ("leave_policies.manage", "ثبت نسخه سیاست مرخصی"),
    ("leave_balances.manage", "ثبت منبع مانده مرخصی"),
    ("leave_balances.view", "مشاهده مانده مجاز مرخصی"),
)


def forward(apps, schema_editor):
    permission = apps.get_model("organizations", "BusinessPermission")
    for code, name in PERMISSIONS:
        permission.objects.using(schema_editor.connection.alias).update_or_create(
            code=code, defaults={"name": name, "description": name, "is_active": True}
        )


def reverse(apps, schema_editor):
    apps.get_model("organizations", "BusinessPermission").objects.using(
        schema_editor.connection.alias
    ).filter(code__in=[code for code, _ in PERMISSIONS]).update(is_active=False)


class Migration(migrations.Migration):
    dependencies = [("organizations", "0121_cep043_payroll_ap_permissions")]
    operations = [migrations.RunPython(forward, reverse)]
