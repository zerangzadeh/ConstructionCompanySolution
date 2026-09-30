from typing import ClassVar

from django.db import migrations
from django.utils import timezone

PERMISSIONS = (
    ("accounting.view", "مشاهده حسابداری"),
    ("accounting.accounts_manage", "مدیریت کدینگ حساب‌ها"),
    ("accounting.periods_manage", "مدیریت سال و دوره مالی"),
    ("accounting.journals_prepare", "تهیه سند حسابداری"),
    ("accounting.journals_submit", "ارسال سند حسابداری"),
    ("accounting.journals_approve", "تأیید مستقل سند حسابداری"),
    ("accounting.journals_post", "ثبت قطعی سند حسابداری"),
    ("accounting.periods_close", "بستن دوره مالی"),
    ("accounting.periods_reopen", "بازگشایی دوره مالی"),
)
PROTECTED_OPERATIONS = (
    ("accounting.journal_post", "Accounting journal posting"),
    ("accounting.opening_accept", "Opening balance acceptance"),
    ("accounting.period_close", "Fiscal period close"),
    ("accounting.period_reopen", "Fiscal period reopen"),
)


def forward(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    Role = apps.get_model("organizations", "OrganizationRole")
    ProtectedOperation = apps.get_model("organizations", "ProtectedOperation")
    permissions = {
        code: Permission.objects.update_or_create(
            code=code,
            defaults={"name": name, "description": name, "is_active": True},
        )[0]
        for code, name in PERMISSIONS
    }
    full_codes = ("tenant_owner", "company_owner")
    admin_codes = (*full_codes, "tenant_admin")
    for role in Role.objects.filter(code__in=admin_codes, organization__isnull=True):
        granted = list(permissions.values())
        if role.code == "tenant_admin":
            granted = [
                item
                for code, item in permissions.items()
                if code != "accounting.periods_reopen"
            ]
        role.permissions.add(*granted)
    accountant = Role.objects.filter(
        code="accountant", organization__isnull=True
    ).first()
    if accountant:
        accountant.permissions.add(
            *[
                item
                for code, item in permissions.items()
                if code != "accounting.periods_reopen"
            ]
        )
    for code, name in PROTECTED_OPERATIONS:
        ProtectedOperation.objects.get_or_create(
            code=code,
            version=1,
            defaults={
                "name": name,
                "description": "Requires explicit permission, reason, immutable audit evidence and independent authorization.",
                "effective_at": timezone.now(),
                "reason": "P2 D2-06/D2-07 Product Owner decision",
            },
        )


class Migration(migrations.Migration):
    dependencies: ClassVar[list[tuple[str, str]]] = [
        ("organizations", "0048_alter_protectedoperation_code"),
    ]
    operations: ClassVar[list[migrations.operations.base.Operation]] = [
        migrations.RunPython(forward, migrations.RunPython.noop)
    ]
