from django.db import migrations

PERMISSIONS = (
    ("workflows.reassign", "تخصیص مجدد کار گردش‌کار"),
    ("workflows.delegate", "واگذاری مسئولیت گردش‌کار"),
    ("workflows.migrate_instances", "مهاجرت اجرای باز گردش‌کار"),
    ("work_items.view", "مشاهده کارهای گردش‌کار"),
    ("work_items.claim", "اخذ کار گردش‌کار"),
    ("work_items.act", "انجام اقدام گردش‌کار"),
)


def add_runtime_permissions(apps, schema_editor):
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
    operations_manager = role_model.objects.filter(code="operations_manager").first()
    operational = (
        permissions["workflows.reassign"],
        permissions["workflows.delegate"],
        permissions["work_items.view"],
        permissions["work_items.claim"],
        permissions["work_items.act"],
    )
    if manager:
        manager.permissions.add(*operational)
    if operations_manager:
        operations_manager.permissions.add(*operational)

    member = role_model.objects.filter(code="member").first()
    if member:
        member.permissions.add(
            permissions["work_items.view"],
            permissions["work_items.claim"],
            permissions["work_items.act"],
        )
    viewer = role_model.objects.filter(code="viewer").first()
    if viewer:
        viewer.permissions.add(permissions["work_items.view"])


def remove_runtime_permissions(apps, schema_editor):
    permission_model = apps.get_model("organizations", "BusinessPermission")
    permission_model.objects.filter(code__in=[code for code, _ in PERMISSIONS]).delete()


class Migration(migrations.Migration):
    dependencies = [  # noqa: RUF012
        ("organizations", "0022_workflow_foundation_permissions"),
    ]

    operations = [  # noqa: RUF012
        migrations.RunPython(add_runtime_permissions, remove_runtime_permissions),
    ]
