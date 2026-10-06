from typing import ClassVar

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies: ClassVar = [
        ("equipment", "0005_equipmentcostpolicyversion_equipmentcostrate_and_more")
    ]

    operations: ClassVar = [
        migrations.AddConstraint(
            model_name="equipmentcostsourceenvelope",
            constraint=models.UniqueConstraint(
                fields=("organization", "consumer", "allocation"),
                name="equip_cost_env_org_cons_source_uq",
            ),
        )
    ]
