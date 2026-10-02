from typing import ClassVar

from django.db import migrations


PERMISSIONS = (
    ("rfq_quotes.prepare_comparison", "آماده‌سازی مقایسه تجاری پیشنهاد"),
    ("rfq_quotes.evaluate_comparison", "ارزیابی مقایسه تجاری پیشنهاد"),
    ("rfq_quotes.approve_exception", "تأیید استثنای غیرمادی پیشنهاد"),
    ("rfq_quotes.finalize_comparison", "نهایی‌سازی مقایسه تجاری پیشنهاد"),
    ("rfq_quotes.dispose_conflict", "تعیین تکلیف تعارض ارزیاب پیشنهاد"),
    ("rfq_quotes.prepare_sourcing_award", "آماده‌سازی انتخاب تأمین‌کننده"),
    ("rfq_quotes.finalize_sourcing_award", "نهایی‌سازی انتخاب تأمین‌کننده"),
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
        ("organizations", "0080_p5_s10_admissibility_permissions"),
    ]
    operations: ClassVar[list] = [migrations.RunPython(forward, reverse)]
