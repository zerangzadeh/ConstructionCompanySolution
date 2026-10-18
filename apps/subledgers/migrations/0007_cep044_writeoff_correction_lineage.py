"""Add retained source lineage without modifying existing financial history."""

import django.db.models.deletion
from django.db import migrations, models


def refuse_populated_lineage_rollback(apps, schema_editor):
    proposal = apps.get_model("subledgers", "WriteOffProposal")
    if proposal.objects.using(schema_editor.connection.alias).filter(
        corrects__isnull=False
    ).exists():
        raise RuntimeError(
            "Retained write-off correction lineage exists; use forward recovery."
        )


class Migration(migrations.Migration):
    dependencies = [("subledgers", "0006_cep043_payroll_ap")]

    operations = [
        migrations.AddField(
            model_name="writeoffproposal",
            name="corrects",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="replacement_proposals",
                to="subledgers.writeoffdecision",
            ),
        ),
        migrations.RunPython(
            migrations.RunPython.noop,
            reverse_code=refuse_populated_lineage_rollback,
        ),
    ]
