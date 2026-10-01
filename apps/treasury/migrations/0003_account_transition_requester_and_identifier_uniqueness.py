from typing import ClassVar

import django.db.models.deletion
from django.db import migrations, models


def backfill_transition_requesters(apps, schema_editor):
    del schema_editor
    Event = apps.get_model("treasury", "TreasuryAccountLifecycleEvent")
    Event.objects.filter(requested_by__isnull=True).update(
        requested_by_id=models.F("actor_id")
    )


class Migration(migrations.Migration):
    dependencies: ClassVar[list[tuple[str, str]]] = [
        (
            "treasury",
            "0002_chequeinstrument_treasury_cheque_cash_effect_consistent_and_more",
        )
    ]
    operations: ClassVar[list[migrations.operations.base.Operation]] = [
        migrations.AddField(
            model_name="treasuryaccountlifecycleevent",
            name="requested_by",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="treasury_account_transitions_requested",
                to="organizations.organizationmembership",
            ),
        ),
        migrations.RunPython(backfill_transition_requesters, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="treasuryaccountlifecycleevent",
            name="requested_by",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="treasury_account_transitions_requested",
                to="organizations.organizationmembership",
            ),
        ),
        migrations.AddConstraint(
            model_name="treasuryaccount",
            constraint=models.UniqueConstraint(
                condition=~models.Q(identifier_fingerprint=""),
                fields=("organization", "identifier_fingerprint"),
                name="treasury_account_unique_tenant_identifier",
            ),
        ),
    ]
