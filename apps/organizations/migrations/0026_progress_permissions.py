from django.db import migrations


PERMISSIONS = (
    ("progress.view", "مشاهده پیشرفت"),
    ("progress.record", "ثبت پیشرفت"),
    ("progress.verify", "راستی‌آزمایی پیشرفت"),
)


def add_progress_permissions(apps, schema_editor):
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
        "operations_manager": ("progress.view", "progress.record"),
        "member": ("progress.view", "progress.record"),
        "viewer": ("progress.view",),
    }.items():
        role = OrganizationRole.objects.filter(code=role_code).first()
        if role:
            role.permissions.add(*(permissions[code] for code in codes))


def remove_progress_permissions(apps, schema_editor):
    del schema_editor
    BusinessPermission = apps.get_model("organizations", "BusinessPermission")
    BusinessPermission.objects.filter(code__in=[code for code, _ in PERMISSIONS]).delete()


class Migration(migrations.Migration):
    dependencies = [("organizations", "0025_baseline_permissions")]

    operations = [migrations.RunPython(add_progress_permissions, remove_progress_permissions)]
