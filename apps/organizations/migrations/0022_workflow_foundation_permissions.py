from django.db import migrations


PERMISSIONS = (
    ("workflows.view", "مشاهده تعریف‌های گردش‌کار"),
    ("workflows.create", "ایجاد تعریف گردش‌کار"),
    ("workflows.change_draft", "ویرایش پیش‌نویس گردش‌کار"),
    ("workflows.publish", "انتشار نسخه گردش‌کار"),
    ("workflows.retire", "بازنشسته‌کردن نسخه گردش‌کار"),
)


def add_workflow_permissions(apps, schema_editor):
    permission_model = apps.get_model("organizations", "BusinessPermission")
    role_model = apps.get_model("organizations", "OrganizationRole")
    permissions = {}
    for code, name in PERMISSIONS:
        permission, _ = permission_model.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "description": f"مجوز سازمانی ریزدانه: {name}",
                "is_active": True,
            },
        )
        permissions[code] = permission
    owner = role_model.objects.filter(code="company_owner").first()
    if owner:
        owner.permissions.add(*permissions.values())
    manager = role_model.objects.filter(code="company_manager").first()
    if manager:
        manager.permissions.add(permissions["workflows.view"])


def remove_workflow_permissions(apps, schema_editor):
    permission_model = apps.get_model("organizations", "BusinessPermission")
    permission_model.objects.filter(code__in=[code for code, _ in PERMISSIONS]).delete()


class Migration(migrations.Migration):
    dependencies = [  # noqa: RUF012
        ("organizations", "0021_employee_profile_image_permission"),
    ]

    operations = [  # noqa: RUF012
        migrations.RunPython(add_workflow_permissions, remove_workflow_permissions),
    ]

