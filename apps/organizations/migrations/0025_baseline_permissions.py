from django.db import migrations


PERMISSIONS = (
    ("baselines.view", "مشاهده مبناهای تجاری"),
    ("baselines.manage", "مدیریت مبناهای تجاری"),
    ("baselines.approve", "تأیید مبناهای تجاری"),
)


def add_baseline_permissions(apps, schema_editor):
    del schema_editor
    BusinessPermission = apps.get_model("organizations", "BusinessPermission")
    OrganizationRole = apps.get_model("organizations", "OrganizationRole")
    permissions = {
        code: BusinessPermission.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "description": f"مجوز سازمانی ریزدانه: {name}",
                "is_active": True,
            },
        )[0]
        for code, name in PERMISSIONS
    }
    for role_code, codes in {
        "company_owner": tuple(permissions),
        "company_manager": tuple(permissions),
        "operations_manager": ("baselines.view", "baselines.manage"),
    }.items():
        role = OrganizationRole.objects.filter(code=role_code).first()
        if role:
            role.permissions.add(*(permissions[code] for code in codes))


def remove_baseline_permissions(apps, schema_editor):
    del schema_editor
    BusinessPermission = apps.get_model("organizations", "BusinessPermission")
    BusinessPermission.objects.filter(code__in=[code for code, _ in PERMISSIONS]).delete()


class Migration(migrations.Migration):
    dependencies = [("organizations", "0024_organization_member_password_reset_permission")]

    operations = [migrations.RunPython(add_baseline_permissions, remove_baseline_permissions)]
