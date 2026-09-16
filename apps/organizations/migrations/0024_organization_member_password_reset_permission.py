from django.db import migrations


PERMISSION = ("accounts.reset_password", "بازنشانی گذرواژه اعضای شرکت")


def add_member_password_reset_permission(apps, schema_editor):
    permission_model = apps.get_model("organizations", "BusinessPermission")
    role_model = apps.get_model("organizations", "OrganizationRole")
    permission, _ = permission_model.objects.update_or_create(
        code=PERMISSION[0],
        defaults={
            "name": PERMISSION[1],
            "description": f"مجوز سازمانی ریزدانه: {PERMISSION[1]}",
            "is_active": True,
        },
    )
    owner = role_model.objects.filter(code="company_owner").first()
    if owner:
        owner.permissions.add(permission)


def remove_member_password_reset_permission(apps, schema_editor):
    permission_model = apps.get_model("organizations", "BusinessPermission")
    permission_model.objects.filter(code=PERMISSION[0]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0023_workflow_runtime_permissions"),
    ]

    operations = [
        migrations.RunPython(
            add_member_password_reset_permission,
            remove_member_password_reset_permission,
        ),
    ]
