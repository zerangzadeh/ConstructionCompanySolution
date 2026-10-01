from typing import ClassVar

from django.db import migrations


PERMISSIONS = (
    ("expenses.submit", "ارسال هزینه برای تأیید"),
    ("expenses.approve", "تأیید مستقل هزینه"),
    ("expenses.return", "بازگردانی هزینه برای اصلاح"),
    ("expenses.allocate", "کدگذاری و تخصیص هزینه"),
    ("expenses.recurrences_manage", "مدیریت پیشنهادهای هزینه تکرارشونده"),
)
DEFAULT_ROLES = ("tenant_owner", "company_owner", "tenant_admin")


def forward(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    Role = apps.get_model("organizations", "OrganizationRole")
    for code, name in PERMISSIONS:
        permission, _ = Permission.objects.update_or_create(
            code=code,
            defaults={"name": name, "description": name, "is_active": True},
        )
        for role in Role.objects.filter(
            code__in=DEFAULT_ROLES, organization__isnull=True
        ):
            role.permissions.add(permission)


class Migration(migrations.Migration):
    dependencies: ClassVar[list[tuple[str, str]]] = [
        ("organizations", "0067_p4_s21_s25_project_control_permissions")
    ]
    operations: ClassVar[list] = [migrations.RunPython(forward, migrations.RunPython.noop)]
