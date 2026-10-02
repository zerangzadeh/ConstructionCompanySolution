from typing import ClassVar

from django.db import migrations

PERMISSION = (
    "rfqs.custody_sealed_evidence",
    "نگهداری شاهد مهروموم‌شده پیشنهاد",
)


def forward(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    code, name = PERMISSION
    Permission.objects.update_or_create(
        code=code,
        defaults={"name": name, "description": name, "is_active": True},
    )


def reverse(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    Permission.objects.filter(code=PERMISSION[0]).delete()


class Migration(migrations.Migration):
    dependencies: ClassVar[list[tuple[str, str]]] = [
        ("organizations", "0075_p5_s07_close_custody_permission")
    ]
    operations: ClassVar[list] = [migrations.RunPython(forward, reverse)]
