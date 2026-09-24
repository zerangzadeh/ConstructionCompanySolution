from django.db import migrations

PERMISSIONS = (("claims.view", "مشاهده صورت‌وضعیت‌ها"), ("claims.create", "ایجاد صورت‌وضعیت پیش‌نویس"), ("claims.revise", "بازنگری صورت‌وضعیت پیش‌نویس"))

def forwards(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    Role = apps.get_model("organizations", "OrganizationRole")
    values = {code: Permission.objects.update_or_create(code=code, defaults={"name": name, "description": name, "is_active": True})[0] for code, name in PERMISSIONS}
    for code, permissions in {"company_owner": tuple(values), "company_manager": tuple(values), "operations_manager": ("claims.view", "claims.create"), "member": ("claims.view", "claims.create"), "viewer": ("claims.view",)}.items():
        if role := Role.objects.filter(code=code).first(): role.permissions.add(*(values[item] for item in permissions))

def backwards(apps, schema_editor):
    del schema_editor
    apps.get_model("organizations", "BusinessPermission").objects.filter(code__in=[code for code, _ in PERMISSIONS]).delete()

class Migration(migrations.Migration):
    dependencies = [("organizations", "0026_progress_permissions")]
    operations = [migrations.RunPython(forwards, backwards)]
