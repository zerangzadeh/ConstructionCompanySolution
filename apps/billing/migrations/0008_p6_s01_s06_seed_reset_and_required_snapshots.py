import django.db.models.deletion
from django.db import migrations, models


def discard_preproduction_claim_seed_data(apps, schema_editor):
    del schema_editor
    ClaimSettlementAllocation = apps.get_model(
        "billing", "ClaimSettlementAllocation"
    )
    ProgressClaim = apps.get_model("billing", "ProgressClaim")
    ClaimSettlementAllocation.objects.all().delete()
    ProgressClaim.objects.update(returned_revision=None)
    ProgressClaim.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0007_progressclaim_contract_term_version_and_more"),
    ]

    operations = [
        migrations.RunPython(
            discard_preproduction_claim_seed_data,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="progressclaim",
            name="contract_term_version",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="progress_claims",
                to="contracts.contracttermversion",
            ),
        ),
        migrations.AlterField(
            model_name="progressclaim",
            name="party_identity_snapshot",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="progress_claims",
                to="parties.partyidentitysnapshot",
            ),
        ),
        migrations.AlterField(
            model_name="progressclaim",
            name="regulatory_rule_version",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="progress_claims",
                to="organizations.platformpolicyversion",
            ),
        ),
        migrations.AlterField(
            model_name="progressclaim",
            name="currency_code",
            field=models.CharField(max_length=3),
        ),
    ]
