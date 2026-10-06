from typing import ClassVar

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies: ClassVar = [("fixed_assets", "0005_asset_transfer_source_dimensions")]

    operations: ClassVar = [
        migrations.AddConstraint(
            model_name="fixedassetsourceenvelope",
            constraint=models.UniqueConstraint(
                condition=models.Q(("asset_transaction__isnull", False)),
                fields=("organization", "consumer", "asset_transaction"),
                name="fixed_asset_env_tx_cons_source_uq",
            ),
        ),
        migrations.AddConstraint(
            model_name="fixedassetsourceenvelope",
            constraint=models.UniqueConstraint(
                condition=models.Q(("depreciation_line__isnull", False)),
                fields=("organization", "consumer", "depreciation_line"),
                name="fixed_asset_env_dep_cons_source_uq",
            ),
        ),
    ]
