import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0009_p6_s07_s13_claim_corrections"),
    ]

    operations = [
        migrations.AddField(
            model_name="progressclaim",
            name="due_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="progressclaim",
            name="corrects",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="correction_claims",
                to="billing.progressclaim",
            ),
        ),
    ]
