from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("payments", "0003_alter_payment_options_and_more")]

    operations = [
        migrations.AddField(
            model_name="paymentallocation",
            name="reversal_reason",
            field=models.TextField(blank=True, verbose_name="دلیل برگشت"),
        ),
    ]
