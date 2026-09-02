import django.db.models.deletion

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("expenses", "0001_initial"),
        ("projects", "0003_projectphase"),
    ]

    operations = [
        migrations.AddField(
            model_name="expense",
            name="phase",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="expenses",
                to="projects.projectphase",
            ),
        ),
        migrations.AddIndex(
            model_name="expense",
            index=models.Index(
                fields=["organization", "phase", "incurred_on"],
                name="expense_org_phase_date_idx",
            ),
        ),
    ]
