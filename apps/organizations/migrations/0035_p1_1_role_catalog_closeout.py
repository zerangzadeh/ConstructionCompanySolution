from typing import ClassVar

from django.db import migrations

BOOTSTRAP_REASON = "Product Owner P1.1 bootstrap: admin Platform Admin"


def bootstrap_admin_platform_role(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    PlatformRoleAssignment = apps.get_model("organizations", "PlatformRoleAssignment")
    admin = User.objects.filter(username="admin", is_active=True).first()
    if admin is None:
        return
    PlatformRoleAssignment.objects.get_or_create(
        user=admin,
        role="platform_admin",
        revoked_at__isnull=True,
        defaults={
            "assigned_by": admin,
            "approved_by": admin,
            "reason": BOOTSTRAP_REASON,
        },
    )


def reverse_closeout(apps, schema_editor):
    Role = apps.get_model("organizations", "OrganizationRole")
    PlatformRoleAssignment = apps.get_model("organizations", "PlatformRoleAssignment")
    if (
        Role.objects.filter(organization__isnull=False).exists()
        or Role.objects.filter(archived_at__isnull=False).exists()
    ):
        raise RuntimeError(
            "Unsafe P1.1 role-catalog rollback refused: tenant-specific or archived "
            "roles would lose ownership/lifecycle evidence."
        )
    PlatformRoleAssignment.objects.filter(reason=BOOTSTRAP_REASON).delete()


class Migration(migrations.Migration):
    dependencies: ClassVar[list[tuple[str, str]]] = [
        ("organizations", "0034_p1_1_role_catalog_lifecycle"),
    ]

    operations: ClassVar[list[migrations.operations.base.Operation]] = [
        migrations.RunPython(bootstrap_admin_platform_role, reverse_closeout),
    ]
