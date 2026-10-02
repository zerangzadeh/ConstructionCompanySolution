from typing import ClassVar

from django.db import migrations

PERMISSIONS = (
    ("rfq_quotes.approve_open", "تأیید مستقل گشایش پیشنهاد"),
    (
        "rfq_quotes.manage_confidential_access",
        "مدیریت دسترسی محرمانه پیشنهاد",
    ),
)


def forward(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    for code, name in PERMISSIONS:
        Permission.objects.update_or_create(
            code=code,
            defaults={"name": name, "description": name, "is_active": True},
        )


def reverse(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    Permission.objects.filter(code__in=[code for code, _ in PERMISSIONS]).delete()


class Migration(migrations.Migration):
    dependencies: ClassVar[list[tuple[str, str]]] = [
        ("organizations", "0078_p5_s09_reveal_operation_choice")
    ]
    operations: ClassVar[list[migrations.operations.base.Operation]] = [
        migrations.RunPython(forward, reverse)
    ]
