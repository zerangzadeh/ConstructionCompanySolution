"""Remove obsolete runtime models while preserving original legacy records."""

from django.db import migrations


def retire_permissions(apps, schema_editor):
    permission = apps.get_model("organizations", "BusinessPermission")
    permission.objects.using(schema_editor.connection.alias).filter(
        code__in=(
            "payments.view",
            "payments.create",
            "payments.void",
            "payments.allocate",
        )
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0006_paymentdocumentlink"),
        ("billing", "0018_retire_legacy_claim_settlements"),
        ("organizations", "0122_cep023_leave_permissions"),
    ]
    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.DeleteModel(name="PaymentDocumentLink"),
                migrations.DeleteModel(name="PaymentAllocation"),
                migrations.DeleteModel(name="Payment"),
            ],
        ),
        migrations.RunPython(retire_permissions),
    ]
