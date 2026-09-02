import django.db.models.deletion

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("daily_reports", "0002_daily_report_entries"),
        ("projects", "0003_projectphase"),
    ]

    operations = [
        migrations.AddField(
            model_name="dailyreport",
            name="phase",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="daily_reports",
                to="projects.projectphase",
            ),
        ),
        migrations.AddIndex(
            model_name="dailyreport",
            index=models.Index(
                fields=["organization", "phase", "reporting_date"],
                name="dailyrep_org_phase_date_idx",
            ),
        ),
    ]
