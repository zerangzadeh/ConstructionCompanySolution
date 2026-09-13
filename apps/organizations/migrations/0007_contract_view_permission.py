from django.db import migrations


PERMISSION_CODE = "contracts.view"
PERMISSION_NAME = "مشاهده قراردادها"


def add_contract_view_permission(apps, schema_editor):
    business_permission = apps.get_model("organizations", "BusinessPermission")
    organization_role = apps.get_model("organizations", "OrganizationRole")

    view_permission, _ = business_permission.objects.update_or_create(
        code=PERMISSION_CODE,
        defaults={
            "name": PERMISSION_NAME,
            "description": "مشاهده قراردادهای متعلق به شرکت فعال",
            "is_active": True,
        },
    )
    eligible_roles = organization_role.objects.filter(
        permissions__code="contracts.manage"
    ).distinct()
    viewer_role = organization_role.objects.filter(code="viewer").first()
    for role in eligible_roles:
        role.permissions.add(view_permission)
    if viewer_role is not None:
        viewer_role.permissions.add(view_permission)


def remove_contract_view_permission(apps, schema_editor):
    business_permission = apps.get_model("organizations", "BusinessPermission")
    business_permission.objects.filter(code=PERMISSION_CODE).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0006_direct_user_provisioning"),
    ]

    operations = [
        migrations.RunPython(
            add_contract_view_permission,
            remove_contract_view_permission,
        ),
    ]
