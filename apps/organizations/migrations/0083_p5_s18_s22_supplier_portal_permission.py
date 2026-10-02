from typing import ClassVar

from django.db import migrations

PERMISSION = (
    "supplier_portal.invitations_manage",
    "مدیریت دعوت و لغو دسترسی درگاه تأمین‌کننده",
)


def forward(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    code, name = PERMISSION
    Permission.objects.update_or_create(
        code=code,
        defaults={"name": name, "description": name, "is_active": True},
    )
    # Deliberately no default-role grant: external access issuance is fail-closed.


def reverse(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    Permission.objects.filter(code=PERMISSION[0]).delete()


class Migration(migrations.Migration):
    dependencies: ClassVar[list[tuple[str, str]]] = [
        ("organizations", "0082_p5_s12_s17_permissions"),
    ]
    operations: ClassVar[list] = [migrations.RunPython(forward, reverse)]
