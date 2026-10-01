from typing import ClassVar

from django.db import migrations

PERMISSIONS = (
    ("treasury.payment_requests_create", "ایجاد درخواست پرداخت خزانه‌داری"),
    ("treasury.payment_requests_submit", "ارسال درخواست پرداخت خزانه‌داری"),
    ("treasury.payment_requests_approve", "تأیید درخواست پرداخت خزانه‌داری"),
    ("treasury.payment_requests_release", "تخصیص پرداخت قطعی به درخواست"),
    ("treasury.advances_manage", "مدیریت تنخواه کارمند و تأمین‌کننده"),
    ("treasury.advances_settle", "ثبت و تأیید تسویه نقدی تنخواه"),
    ("treasury.advances_reverse", "برگشت کنترل‌شده تنخواه یا تسویه"),
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
        ("organizations", "0059_p3_treasury_permissions")
    ]
    operations: ClassVar[list[migrations.operations.base.Operation]] = [
        migrations.RunPython(forward, migrations.RunPython.noop)
    ]
