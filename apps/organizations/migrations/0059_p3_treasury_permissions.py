from typing import ClassVar

from django.db import migrations

PERMISSIONS = (
    ("treasury.view", "مشاهده خزانه‌داری"),
    ("treasury.accounts_manage", "مدیریت حساب‌های خزانه‌داری"),
    ("treasury.sensitive_view", "مشاهده شناسه‌های ماسک‌شده حساس خزانه‌داری"),
    ("treasury.mappings_manage", "مدیریت نگاشت حسابداری خزانه‌داری"),
    ("treasury.movements_create", "ایجاد حرکت خزانه‌داری"),
    ("treasury.movements_submit", "ارسال حرکت خزانه‌داری"),
    ("treasury.movements_approve", "تأیید حرکت خزانه‌داری"),
    ("treasury.movements_post", "ثبت قطعی حرکت خزانه‌داری"),
    ("treasury.movements_reverse", "برگشت حرکت خزانه‌داری"),
    ("treasury.cheques_manage", "مدیریت چک‌های خزانه‌داری"),
    ("treasury.cheques_clear", "ثبت وصول قطعی چک"),
    ("treasury.reconciliations_run", "اجرای تطبیق خزانه‌داری با دفترکل"),
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
        ("organizations", "0058_deprecate_tenant_policy_approve_permission")
    ]
    operations: ClassVar[list[migrations.operations.base.Operation]] = [
        migrations.RunPython(forward, migrations.RunPython.noop)
    ]
