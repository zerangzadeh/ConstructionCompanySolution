from typing import ClassVar

from django.db import migrations

PERMISSIONS = (
    ("project_cost.sources_manage", "مدیریت قراردادهای منبع هزینه پروژه"),
    ("project_cost.sources_approve", "تأیید مستقل قراردادهای منبع هزینه پروژه"),
    ("project_cost.facts_record", "ثبت برون‌داد طبقه‌بندی‌شده هزینه پروژه"),
    ("project_cost.view", "مشاهده هزینه یکپارچه پروژه"),
    ("project_cost.forecasts_prepare", "آماده‌سازی پیش‌نویس پیش‌بینی هزینه پروژه"),
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
        ("organizations", "0065_p4_s07_s13_budget_permissions")
    ]
    operations: ClassVar[list[migrations.operations.base.Operation]] = [
        migrations.RunPython(forward, migrations.RunPython.noop)
    ]
