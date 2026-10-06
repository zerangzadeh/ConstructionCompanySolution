from typing import ClassVar

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies: ClassVar = [("inventory", "0005_inventoryvaluationexception")]

    operations: ClassVar = [
        migrations.AddConstraint(
            model_name="downstreamcostsourceenvelope",
            constraint=models.UniqueConstraint(
                fields=("organization", "consumer", "valuation_event"),
                name="inventory_cost_envelope_source_uq",
            ),
        )
    ]
