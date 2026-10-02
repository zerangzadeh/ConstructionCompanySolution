from typing import ClassVar

from django.db import migrations
from django.utils import timezone

PERMISSIONS = (
    ("rfq_quotes.open", "گشایش حفاظت‌شده پیشنهاد"),
    (
        "rfq_quotes.view_confidential",
        "مشاهده محتوای محرمانه پیشنهاد گشوده‌شده",
    ),
)
PROTECTED_OPERATION = (
    "rfq_quotes.reveal",
    "گشایش و افشای حفاظت‌شده پیشنهاد",
)


def forward(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    ProtectedOperation = apps.get_model("organizations", "ProtectedOperation")
    for code, name in PERMISSIONS:
        Permission.objects.update_or_create(
            code=code,
            defaults={"name": name, "description": name, "is_active": True},
        )
    code, name = PROTECTED_OPERATION
    ProtectedOperation.objects.get_or_create(
        code=code,
        version=1,
        defaults={
            "name": name,
            "description": name,
            "effective_at": timezone.now(),
            "reason": "P5-S09 authorized protected-operation classification foundation",
        },
    )


def reverse(apps, schema_editor):
    del schema_editor
    Permission = apps.get_model("organizations", "BusinessPermission")
    ProtectedOperation = apps.get_model("organizations", "ProtectedOperation")
    Permission.objects.filter(code__in=[code for code, _ in PERMISSIONS]).delete()
    ProtectedOperation.objects.filter(code=PROTECTED_OPERATION[0], version=1).delete()


class Migration(migrations.Migration):
    dependencies: ClassVar[list[tuple[str, str]]] = [
        ("organizations", "0076_p5_s08_sealed_custody_permission")
    ]
    operations: ClassVar[list] = [migrations.RunPython(forward, reverse)]
