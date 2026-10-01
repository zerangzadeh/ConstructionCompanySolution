from django.db import migrations


PERMISSIONS = (
    (
        "treasury.reconciliations_review",
        "بررسی مستقل تطبیق خزانه‌داری با دفترکل",
    ),
    (
        "subledgers.reconciliations_review",
        "بررسی مستقل تطبیق زیر‌دفتر AP/AR",
    ),
)
DEFAULT_ROLES = ("tenant_owner", "company_owner", "tenant_admin", "accountant")


def forward(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    Role = apps.get_model("organizations", "OrganizationRole")
    for code, name in PERMISSIONS:
        permission, _ = Permission.objects.update_or_create(
            code=code,
            defaults={"name": name, "description": name, "is_active": True},
        )
        for role in Role.objects.filter(
            code__in=DEFAULT_ROLES, organization__isnull=True
        ):
            role.permissions.add(permission)


class Migration(migrations.Migration):
    dependencies = [("organizations", "0062_p3_s23_s27_subledger_permissions")]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
