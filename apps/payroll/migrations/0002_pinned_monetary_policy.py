from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0092_p7_s13_s22_core_payroll_permissions"),
        ("payroll", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="payrollrun",
            name="monetary_policy_snapshot",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="payrollrun",
            name="precision_policy_version",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="payroll_precision_evidence",
                to="organizations.platformpolicyversion",
            ),
        ),
        migrations.AddField(
            model_name="payrollrun",
            name="rounding_policy_version",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="payroll_rounding_evidence",
                to="organizations.platformpolicyversion",
            ),
        ),
    ]
