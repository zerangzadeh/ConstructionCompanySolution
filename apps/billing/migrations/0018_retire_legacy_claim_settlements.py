"""Retire runtime state, preserving original rows under the Human decision."""

from importlib import import_module

from django.db import migrations


def verify_retirement(apps, schema_editor):
    alias = schema_editor.connection.alias
    # No environment, population, cash mapping or historical readiness-file gate.
    preparation = import_module(
        "apps.documents.migrations.0012_legacy_payment_reference_preparation"
    )
    preparation.preserve_excluded_sources(apps, schema_editor)
    preparation.preserve_typed_links(apps, schema_editor)
    SourceLink = apps.get_model("payments", "PaymentDocumentLink")
    RetainedLink = apps.get_model("documents", "RetiredPaymentDocumentLink")
    fields = (
        "organization_id",
        "document_id",
        "payment_id",
        "created_by_id",
        "created_at",
        "legacy_link_id",
    )
    for row in SourceLink.objects.using(alias).all():
        retained = RetainedLink.objects.using(alias).get(pk=row.pk)
        if any(getattr(row, field) != getattr(retained, field) for field in fields):
            raise RuntimeError("Retained document identity mismatch")


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0017_cep037_variation_billing_eligibility"),
        ("documents", "0012_legacy_payment_reference_preparation"),
        ("treasury", "0010_legacy_payment_reference_preparation"),
    ]
    # Physical retention remains mandatory; remove only the active model state.
    operations = [
        migrations.RunPython(verify_retirement),
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[migrations.DeleteModel(name="ClaimSettlementAllocation")],
        ),
    ]
