from typing import ClassVar

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies: ClassVar = [
        ("fixed_assets", "0004_asset_transfer_dimensions"),
        ("projects", "0008_p4_s21_s25_schedule_change_controls"),
    ]

    operations: ClassVar = [
        migrations.AddField(
            model_name="assettransaction",
            name="source_dimensions_captured",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="assettransaction",
            name="source_cost_center",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="fixed_asset_transfer_sources",
                to="projects.costcenter",
            ),
        ),
        migrations.AddField(
            model_name="assettransaction",
            name="source_project",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="fixed_asset_transfer_sources",
                to="projects.project",
            ),
        ),
        migrations.AddField(
            model_name="assettransaction",
            name="source_site",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="fixed_asset_transfer_sources",
                to="projects.projectsite",
            ),
        ),
    ]
