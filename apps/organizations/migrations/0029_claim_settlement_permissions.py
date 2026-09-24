from django.db import migrations


PERMISSIONS = (
    ("claim_settlements.view", "مشاهده تسویه صورت‌وضعیت"),
    ("claim_settlements.allocate", "تخصیص دریافت به صورت‌وضعیت"),
    ("claim_settlements.reverse", "برگشت تسویه صورت‌وضعیت"),
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
        "operations_manager": tuple(values),
        "member": ("claim_settlements.view",),
        "viewer": ("claim_settlements.view",),
    }
    for role_code, permission_codes in role_permissions.items():
        role = Role.objects.filter(code=role_code).first()
        if role is not None:
            role.permissions.add(*(values[code] for code in permission_codes))


def backwards(apps, schema_editor):
    del schema_editor
    apps.get_model("organizations", "BusinessPermission").objects.filter(
        code__in=[code for code, _ in PERMISSIONS]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("organizations", "0028_claim_approval_permissions")]

    operations = [migrations.RunPython(forwards, backwards)]
