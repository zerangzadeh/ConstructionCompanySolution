from typing import ClassVar

from django.db import migrations

PERMISSIONS = (
    ("treasury.statements_import", "پیش‌نمایش و لغو ورود صورتحساب بانکی"),
    ("treasury.statements_accept", "پذیرش صورتحساب بانکی"),
    ("treasury.statement_matches_manage", "مدیریت پیشنهاد و اصلاح تطبیق بانکی"),
    ("treasury.statement_matches_clear", "تأیید تطبیق و تسویه بانکی"),
    ("treasury.bank_reconciliations_run", "اجرای تطبیق بانکی"),
)


def forward(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    Role = apps.get_model("organizations", "OrganizationRole")
    roles = Role.objects.filter(
        code__in=("tenant_owner", "company_owner", "tenant_admin", "accountant"),
        organization__isnull=True,
    )
    for code, name in PERMISSIONS:
        permission, _ = Permission.objects.update_or_create(
            code=code,
            defaults={"name": name, "description": name, "is_active": True},
        )
        for role in roles:
            role.permissions.add(permission)


class Migration(migrations.Migration):
    dependencies: ClassVar[list[tuple[str, str]]] = [
        ("organizations", "0060_p3_s12_s17_treasury_permissions")
    ]
    operations: ClassVar[list[migrations.operations.base.Operation]] = [
        migrations.RunPython(forward, migrations.RunPython.noop)
    ]
