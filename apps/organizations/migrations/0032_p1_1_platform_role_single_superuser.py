from typing import ClassVar

from django.db import migrations


class Migration(migrations.Migration):
    dependencies: ClassVar[list[tuple[str, str]]] = [
        ("organizations", "0031_p1_1_authorization_backfill"),
    ]

    operations: ClassVar[list[migrations.operations.base.Operation]] = [
        migrations.RemoveConstraint(
            model_name="platformroleassignment",
            name="platform_role_dual_control",
        ),
    ]
