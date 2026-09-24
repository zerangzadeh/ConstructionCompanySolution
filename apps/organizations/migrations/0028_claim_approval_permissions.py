from django.db import migrations


PERMISSIONS = (
    ("claims.submit", "ارسال صورت‌وضعیت"),
    ("claims.approve", "تأیید یا بازگردانی صورت‌وضعیت"),
)


def forwards(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    Role = apps.get_model("organizations", "OrganizationRole")
    values = {
        code: Permission.objects.update_or_create(
            code=code,
            defaults={"name": name, "description": name, "is_active": True},
        )[0]
        for code, name in PERMISSIONS
    }
    role_permissions = {
        "company_owner": tuple(values),
        "company_manager": tuple(values),
        "operations_manager": ("claims.submit",),
        "member": ("claims.submit",),
    }
    runtime_codes = ("work_items.view", "work_items.claim", "work_items.act")
    runtime_permissions = list(Permission.objects.filter(code__in=runtime_codes))
    for role_code, permission_codes in role_permissions.items():
        role = Role.objects.filter(code=role_code).first()
        if role is None:
            continue
        role.permissions.add(*(values[code] for code in permission_codes))
        if "claims.approve" in permission_codes:
            role.permissions.add(*runtime_permissions)


def backwards(apps, schema_editor):
    del schema_editor
    apps.get_model("organizations", "BusinessPermission").objects.filter(
        code__in=[code for code, _ in PERMISSIONS]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("organizations", "0027_claim_permissions")]

    operations = [migrations.RunPython(forwards, backwards)]
