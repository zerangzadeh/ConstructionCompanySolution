from typing import ClassVar

from django.db import migrations

PERMISSIONS = (
    ("subledgers.view", "مشاهده تعهدات AP/AR"),
    ("subledgers.obligations_recognize", "شناسایی تعهد AP/AR از منبع ثبت‌شده"),
    ("subledgers.settlements_allocate", "تخصیص تسویه خزانه‌داری به تعهد AP/AR"),
    ("subledgers.settlements_reverse", "برگشت تخصیص تسویه AP/AR"),
    ("subledgers.aging_run", "اجرای aging دقیق AP/AR"),
    ("subledgers.reconciliations_run", "اجرای تطبیق زیر‌دفتر AP/AR"),
    ("subledgers.writeoffs_propose", "پیشنهاد سوخت مانده AP/AR"),
    ("subledgers.writeoffs_approve", "تأیید سوخت مانده AP/AR (در انتظار سیاست)"),
    ("subledgers.writeoffs_reverse", "برگشت سوخت AP/AR (در انتظار سیاست)"),
)

DEFAULT_GRANTED = {
    "subledgers.view",
    "subledgers.obligations_recognize",
    "subledgers.settlements_allocate",
    "subledgers.settlements_reverse",
    "subledgers.aging_run",
    "subledgers.reconciliations_run",
    "subledgers.writeoffs_propose",
}


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
        if code in DEFAULT_GRANTED:
            for role in roles:
                role.permissions.add(permission)


class Migration(migrations.Migration):
    dependencies: ClassVar[list[tuple[str, str]]] = [
        ("organizations", "0061_p3_s18_s22_treasury_permissions")
    ]
    operations: ClassVar[list[migrations.operations.base.Operation]] = [
        migrations.RunPython(forward, migrations.RunPython.noop)
    ]
