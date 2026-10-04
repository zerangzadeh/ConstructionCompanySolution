from typing import ClassVar

from django.db import migrations


PERMISSIONS = (
    ("time_calendars.view", "مشاهده تقویم و شیفت"),
    ("time_calendars.manage", "مدیریت تقویم و شیفت"),
    ("attendance.view", "مشاهده حضور"),
    ("attendance.capture", "ثبت دستی حضور"),
    ("attendance.review", "قطعی‌سازی و رسیدگی حضور"),
    ("attendance.correct", "اصلاح مستقل حضور قطعی"),
    ("attendance.import", "درون‌ریزی حضور"),
    ("leave_mission.view", "مشاهده مرخصی و مأموریت"),
    ("leave_mission.request", "ثبت مرخصی و مأموریت"),
    ("leave_mission.review", "بررسی مرخصی و مأموریت"),
    ("overtime.view", "مشاهده اضافه‌کاری"),
    ("overtime.request", "ثبت درخواست اضافه‌کاری"),
    ("overtime.review", "بررسی اضافه‌کاری"),
    ("timesheets.view", "مشاهده کارکرد"),
    ("timesheets.prepare", "تهیه و ارسال کارکرد"),
    ("timesheets.review", "بررسی مستقل کارکرد"),
    ("timesheets.preview", "پیش‌نمایش غیرمالی توزیع کار"),
)
VIEW_CODES = {"time_calendars.view", "attendance.view", "leave_mission.view", "overtime.view", "timesheets.view"}
PREPARE_CODES = {"attendance.capture", "leave_mission.request", "overtime.request", "timesheets.prepare"}
REVIEW_CODES = {"attendance.review", "leave_mission.review", "overtime.review", "timesheets.review", "timesheets.preview"}
ADMIN_CODES = {code for code, _ in PERMISSIONS}


def forward(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    Role = apps.get_model("organizations", "OrganizationRole")
    permissions = {}
    for code, name in PERMISSIONS:
        permissions[code], _ = Permission.objects.update_or_create(code=code, defaults={"name": name, "description": name, "is_active": True})
    grants = {
        "tenant_owner": ADMIN_CODES,
        "company_owner": ADMIN_CODES,
        "tenant_admin": ADMIN_CODES,
        "tenant_manager": VIEW_CODES | PREPARE_CODES | REVIEW_CODES,
        "project_manager": VIEW_CODES | PREPARE_CODES | REVIEW_CODES,
        "company_manager": VIEW_CODES | PREPARE_CODES | REVIEW_CODES,
        "operations_manager": VIEW_CODES | PREPARE_CODES | REVIEW_CODES,
        "supervisor": VIEW_CODES | PREPARE_CODES,
        "member": VIEW_CODES,
        "viewer": VIEW_CODES,
    }
    for role in Role.objects.filter(code__in=grants, organization__isnull=True):
        role.permissions.add(*(permissions[code] for code in grants[role.code]))


def reverse(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    Permission.objects.filter(code__in=[code for code, _ in PERMISSIONS]).delete()


class Migration(migrations.Migration):
    dependencies: ClassVar[list] = [
        ("organizations", "0090_p7_s01_s05_workforce_foundation_permissions"),
        ("timekeeping", "0001_initial"),
    ]
    operations: ClassVar[list] = [migrations.RunPython(forward, reverse)]
