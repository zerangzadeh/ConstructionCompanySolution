from django.db import migrations


PERMISSIONS = {
    "equipment.view": "مشاهده تجهیزات",
    "equipment.create": "ایجاد تجهیز",
    "equipment.change_status": "تغییر وضعیت تجهیز",
    "equipment.archive": "بایگانی تجهیز",
    "equipment_assignments.view": "مشاهده تخصیص‌های تجهیزات",
    "equipment_assignments.create": "تخصیص تجهیز به پروژه",
    "equipment_assignments.transition": "تغییر وضعیت تخصیص تجهیز",
    "maintenance_records.view": "مشاهده سوابق سرویس و تعمیر",
    "maintenance_records.create": "ایجاد سابقه سرویس و تعمیر",
    "maintenance_records.transition": "تغییر وضعیت سرویس و تعمیر",
}
VIEW_PERMISSIONS = {
    "equipment.view",
    "equipment_assignments.view",
    "maintenance_records.view",
}


def add_equipment_permissions(apps, schema_editor):
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


def remove_equipment_permissions(apps, schema_editor):
    business_permission = apps.get_model("organizations", "BusinessPermission")
    business_permission.objects.filter(code__in=PERMISSIONS).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0008_granular_business_permission_catalog"),
    ]

    operations = [
        migrations.RunPython(
            add_equipment_permissions,
            remove_equipment_permissions,
        ),
    ]
