from django.db import migrations


BUILTIN_ROLE_NAMES = {
    "company_owner": "Company Owner",
    "company_manager": "Company Manager",
    "operations_manager": "Operations Manager",
    "member": "Member",
    "viewer": "Viewer",
}
PREVIOUS_BUILTIN_ROLE_NAMES = {
    "company_owner": "مالک شرکت",
    "company_manager": "مدیر شرکت",
    "operations_manager": "مدیر اجرایی",
    "member": "عضو",
    "viewer": "مشاهده‌گر",
}


def update_builtin_role_names(apps, schema_editor):
    organization_role = apps.get_model("organizations", "OrganizationRole")
    for code, name in BUILTIN_ROLE_NAMES.items():
        organization_role.objects.filter(code=code, is_system=True).update(name=name)


def restore_builtin_role_names(apps, schema_editor):
    organization_role = apps.get_model("organizations", "OrganizationRole")
    for code, name in PREVIOUS_BUILTIN_ROLE_NAMES.items():
        organization_role.objects.filter(code=code, is_system=True).update(name=name)


class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0016_organizationaccountconnectionrequest"),
    ]

    operations = [
        migrations.RunPython(update_builtin_role_names, restore_builtin_role_names),
    ]
