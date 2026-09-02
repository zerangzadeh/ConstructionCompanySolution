import django.db.models.deletion

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("estimates", "0002_estimate_approval"),
        ("projects", "0003_projectphase"),
    ]

    operations = [
        migrations.AddField(
            model_name="estimate",
            name="phase",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="estimates",
                to="projects.projectphase",
            ),
        ),
        migrations.AddIndex(
            model_name="estimate",
            index=models.Index(
                fields=["organization", "phase", "status"],
                name="estimate_org_phase_status_idx",
            ),
        ),
    ]
