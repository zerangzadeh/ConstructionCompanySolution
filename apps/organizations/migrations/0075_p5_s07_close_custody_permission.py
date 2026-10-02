from typing import ClassVar

from django.db import migrations


PERMISSION = ("rfqs.close_custody", "بستن ثبتی استعلام")


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
        ("organizations", "0074_p5_s06_quote_permissions")
    ]
    operations: ClassVar[list] = [migrations.RunPython(forward, reverse)]
