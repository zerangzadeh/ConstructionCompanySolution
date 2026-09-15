from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0003_alter_activity_options_alter_project_options_and_more"),
    ]

    operations = [
        migrations.RenameField(
            model_name="project",
            old_name="budget",
            new_name="estimated_budget",
        ),
        migrations.AlterField(
            model_name="project",
            name="estimated_budget",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                max_digits=18,
                verbose_name="بودجه تخمینی",
            ),
        ),
        migrations.AddField(
            model_name="project",
            name="actual_budget",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                max_digits=18,
                verbose_name="بودجه واقعی",
            ),
        ),
    ]
