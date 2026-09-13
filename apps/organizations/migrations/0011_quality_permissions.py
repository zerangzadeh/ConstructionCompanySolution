from django.db import migrations


PERMISSIONS = {
    "quality_issues.view": "مشاهده مسائل کیفیت",
    "quality_issues.create": "ثبت مسئله کیفیت",
    "quality_issues.review": "بررسی و تخصیص مسئله کیفیت",
    "quality_issues.manage": "مدیریت اقدام اصلاحی کیفیت",
    "quality_issues.verify": "راستی‌آزمایی مسئله کیفیت",
    "quality_issues.close": "بستن مسئله کیفیت",
}
VIEW_PERMISSIONS = {"quality_issues.view"}


def add_quality_permissions(apps, schema_editor):
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


def remove_quality_permissions(apps, schema_editor):
    business_permission = apps.get_model("organizations", "BusinessPermission")
    business_permission.objects.filter(code__in=PERMISSIONS).delete()


class Migration(migrations.Migration):
    dependencies = [("organizations", "0010_safety_permissions")]

    operations = [
        migrations.RunPython(add_quality_permissions, remove_quality_permissions),
    ]
