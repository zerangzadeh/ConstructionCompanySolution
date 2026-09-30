from typing import ClassVar

from django.db import migrations
from django.utils import timezone


def forward(apps, schema_editor):
    del schema_editor
    ProtectedOperation = apps.get_model("organizations", "ProtectedOperation")
    ProtectedOperation.objects.get_or_create(
        code="accounting.journal_reverse",
        version=1,
        defaults={
            "name": "Accounting journal reversal",
            "description": "Requires permission, reason, immutable audit evidence and independent authorization.",
            "effective_at": timezone.now(),
            "reason": "P2 immutable correction contract",
        },
    )


class Migration(migrations.Migration):
    dependencies: ClassVar[list[tuple[str, str]]] = [
        ("organizations", "0050_alter_protectedoperation_code")
    ]
    operations: ClassVar[list[migrations.operations.base.Operation]] = [
        migrations.RunPython(forward, migrations.RunPython.noop)
    ]
