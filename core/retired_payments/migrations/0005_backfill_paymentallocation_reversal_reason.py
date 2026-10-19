from django.db import migrations


def forwards(apps, schema_editor):
    del schema_editor
    apps.get_model("payments", "PaymentAllocation").objects.filter(
        status="reversed",
        reversal_reason="",
    ).update(reversal_reason="Historical reversal recorded before F6.5.")


class Migration(migrations.Migration):
    dependencies = [("payments", "0004_paymentallocation_reversal_reason")]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
