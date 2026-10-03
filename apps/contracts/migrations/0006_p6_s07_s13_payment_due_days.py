from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("contracts", "0005_contracttermversion"),
    ]

    operations = [
        migrations.AddField(
            model_name="contracttermversion",
            name="payment_due_days",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddConstraint(
            model_name="contracttermversion",
            constraint=models.CheckConstraint(
                condition=models.Q(payment_due_days__lte=3650),
                name="contract_term_due_days_range",
            ),
        ),
    ]
