from django.db import migrations


PERMISSIONS = (
    ("estimates.compare", "مقایسه بازنگری‌های برآورد"),
    ("estimate_composition.manage", "مدیریت ترکیب منابع برآورد"),
    ("estimate_assumptions.manage", "مدیریت فرض‌ها و ضرایب برآورد"),
    ("estimate_rate_sources.manage", "مدیریت منبع و نرخ برآورد"),
    ("estimate_imports.preview", "پیش‌نمایش ورود برآورد"),
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
    dependencies = [
        ("organizations", "0063_p3_s30_s31_reconciliation_review_permissions")
    ]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
