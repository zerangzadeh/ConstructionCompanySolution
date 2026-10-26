import json

import django.db.models.deletion
from django.db import migrations, models


def preservation_report(apps, schema_editor):
    """Reconcile in place; absent historical snapshots are explicit exceptions.

    Never derive an approved snapshot from today's configuration, reprice a
    claim, clear revision lineage, or delete a claim/allocation to satisfy a
    non-null constraint. Operators must resolve exceptions through separately
    governed historical evidence before retrying this migration.
    """
    alias = schema_editor.connection.alias
    ProgressClaim = apps.get_model("billing", "ProgressClaim")
    Allocation = apps.get_model("billing", "ClaimSettlementAllocation")
    mapping = []
    exceptions = []
    for claim in ProgressClaim.objects.using(alias).order_by("pk").iterator():
        invalid = []
        for field in (
            "contract_term_version",
            "party_identity_snapshot",
            "regulatory_rule_version",
        ):
            if getattr(claim, f"{field}_id") is None:
                invalid.append(field)
        if not claim.currency_code or len(claim.currency_code) != 3:
            invalid.append("currency_code")
        if claim.contract_term_version_id and (
            claim.contract_term_version.contract_id != claim.contract_id
            or claim.contract_term_version.organization_id != claim.organization_id
        ):
            invalid.append("contract_term_version_scope")
        if claim.party_identity_snapshot_id and (
            claim.party_identity_snapshot.organization_id != claim.organization_id
        ):
            invalid.append("party_identity_snapshot_scope")
        for field in ("contract", "project", "baseline"):
            if getattr(claim, field).organization_id != claim.organization_id:
                invalid.append(f"{field}_scope")
        if (
            claim.baseline.contract_id != claim.contract_id
            or (claim.baseline.project_id != claim.project_id)
            or claim.contract.project_id != claim.project_id
        ):
            invalid.append("project_contract_baseline_scope")
        if claim.returned_revision_id and (
            claim.returned_revision.organization_id != claim.organization_id
            or claim.returned_revision.contract_id != claim.contract_id
            or claim.returned_revision.project_id != claim.project_id
        ):
            invalid.append("returned_revision_scope")
        key = {"model": "billing.ProgressClaim", "source": str(claim.pk)}
        if invalid:
            exceptions.append({**key, "invalid_fields": invalid})
        else:
            mapping.append({**key, "target": str(claim.pk)})
    for row in Allocation.objects.using(alias).order_by("pk").iterator():
        key = {"model": "billing.ClaimSettlementAllocation", "source": str(row.pk)}
        if (
            row.claim.organization_id != row.organization_id
            or row.payment_allocation.organization_id != row.organization_id
            or row.payment_allocation.payment.organization_id != row.organization_id
            or row.payment_allocation.contract_id != row.claim.contract_id
        ):
            exceptions.append({**key, "invalid_fields": ["allocation_scope"]})
        else:
            mapping.append({**key, "target": str(row.pk)})
    return {"mapping": mapping, "exceptions": exceptions}


def preserve_claim_history(apps, schema_editor):
    report = preservation_report(apps, schema_editor)
    if report["exceptions"]:
        raise RuntimeError(
            "CEP012 historical snapshot/reference evidence required; source unchanged: "
            + json.dumps(report, sort_keys=True)
        )


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0007_progressclaim_contract_term_version_and_more"),
    ]

    operations = [
        migrations.RunPython(
            preserve_claim_history,
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
