from django.db import migrations


PERMISSIONS = {
    "safety_incidents.view": "مشاهده حوادث ایمنی",
    "safety_incidents.create": "ثبت حادثه ایمنی",
    "safety_incidents.review": "بررسی و تخصیص حادثه ایمنی",
    "safety_incidents.manage": "مدیریت اقدام اصلاحی ایمنی",
    "safety_incidents.close": "بستن حادثه ایمنی",
}
VIEW_PERMISSIONS = {"safety_incidents.view"}


def add_safety_permissions(apps, schema_editor):
    business_permission = apps.get_model("organizations", "BusinessPermission")
    organization_role = apps.get_model("organizations", "OrganizationRole")

    permission_ids = {}
    for code, name in PERMISSIONS.items():
        permission, _ = business_permission.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "description": f"مجوز سازمانی ریزدانه: {name}",
                "is_active": True,
            },
        )
        permission_ids[code] = permission.pk

    for role in organization_role.objects.all():
        codes = VIEW_PERMISSIONS
        if role.code in {"company_owner", "company_manager", "operations_manager"}:
            codes = set(PERMISSIONS)
        role.permissions.add(
            *business_permission.objects.filter(
                pk__in=[permission_ids[code] for code in codes]
            )
        )


def remove_safety_permissions(apps, schema_editor):
    business_permission = apps.get_model("organizations", "BusinessPermission")
    business_permission.objects.filter(code__in=PERMISSIONS).delete()


class Migration(migrations.Migration):
    dependencies = [("organizations", "0009_equipment_permissions")]

    operations = [
        migrations.RunPython(add_safety_permissions, remove_safety_permissions),
    ]
