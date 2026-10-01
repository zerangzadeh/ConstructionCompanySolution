from typing import ClassVar

from django.db import migrations

PERMISSIONS = (
    ("project_schedules.view", "مشاهده برنامه زمان‌بندی و کنترل تغییر پروژه"),
    ("project_schedules.prepare", "آماده‌سازی نسخه برنامه زمان‌بندی پروژه"),
    (
        "project_control_registers.manage",
        "مدیریت ثبت محدودیت، مسئله، ریسک و تأخیر پروژه",
    ),
    (
        "project_control_registers.view",
        "مشاهده ثبت محدودیت، مسئله، ریسک و تأخیر پروژه",
    ),
    ("project_changes.propose", "ثبت پیشنهاد تغییر پروژه بدون اثر قراردادی یا مالی"),
    ("project_changes.view", "مشاهده پیشنهادهای تغییر پروژه"),
    ("project_rebaselines.propose", "ثبت پیشنهاد بازخط‌مبنا بدون پذیرش"),
    ("project_rebaselines.view", "مشاهده پیشنهادهای بازخط‌مبنا"),
    ("project_schedules.accept", "پذیرش مبنای زمان‌بندی (غیرفعال)"),
    ("project_changes.approve", "تأیید تغییر پروژه (غیرفعال)"),
    ("project_rebaselines.accept", "پذیرش بازخط‌مبنا (غیرفعال)"),
)
SAFE_DEFAULTS = {
    "project_schedules.view",
    "project_schedules.prepare",
    "project_control_registers.view",
    "project_control_registers.manage",
    "project_changes.view",
    "project_changes.propose",
    "project_rebaselines.view",
    "project_rebaselines.propose",
}
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
        if code in SAFE_DEFAULTS:
            for role in Role.objects.filter(
                code__in=DEFAULT_ROLES, organization__isnull=True
            ):
                role.permissions.add(permission)


class Migration(migrations.Migration):
    dependencies: ClassVar[list[tuple[str, str]]] = [
        ("organizations", "0066_p4_s14_s20_project_cost_permissions")
    ]
    operations: ClassVar[list[migrations.operations.base.Operation]] = [
        migrations.RunPython(forward, migrations.RunPython.noop)
    ]
